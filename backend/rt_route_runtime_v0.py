# ======================================================================
# Fichier : rt_route_runtime_v0.py
# Description : Runtime API v0
# Version : 0.2.1
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# NOTE: ne plus utiliser, voir la nouvelle version
# ======================================================================
import re
from datetime import datetime, timezone

# Import necessary modules
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from rt_deps_user import get_current_user
from rt_settings_pydantic import settings
from rt_db_sqlalchemy import get_db
from rt_models_exports import Agent, AgentSkillAssignment, Approval, Artifact, Automation, Evaluation, Handoff, Memory, PermissionPolicy, ProviderPolicy, Skill, SkillVersion, TaskRun, Tool, ToolCall, User, Workflow, WorkflowRun, Workspace, WorkspaceMembership
from rt_schemas_runtime_dto import ApprovalDecisionRequest, MembershipUpdate, MemoryCreateV1, MemoryDistillRequest, MemoryPatchV1, PolicyEvaluateRequest, RoutingPreviewRequest, ToolExecuteRequest, WorkflowRunRequest, WorkflowRetryRequest, WorkspaceCreateV1, WorkspacePatchV1
from svc_acl_check import accessible_workspaces, require_workspace
from svc_memory_runtime_v0 import create_memory, delete_memory_tree, distill_memories
from svc_policy_engine import effective_mode, evaluate_policy
from svc_provider_policy import select_provider
from svc_router_agents_kw import route_request
from svc_registry_seed_data import ensure_workspace_policies, resolve_agent
from svc_tool_runtime_exec import execute_tool
from svc_workflow_rt import create_workflow_run

# on garde ça pour plus tard
router = APIRouter(tags=["runtime-v1"])


# TODO: documenter agent dict
# thread-safe
def _agent_dict(agent: Agent, skills: list[dict] | None = None) -> dict:
    return {
        "id": agent.id,
        "stable_id": agent.stable_id,
        "display_name": agent.display_name,
        "description": agent.description,
        "system_prompt": agent.system_prompt,
        "role_type": agent.role_type,
        "initiative_level": agent.initiative_level,
        "status": agent.status,
        "version": agent.version,
        "config": agent.config_json,
        "skills": skills or [],
    }


# Cette fonction permet de vérifier (runtime status)
@router.get("/runtime/status")
async def runtime_status() -> dict:
    return {
        "feature_flag": "agent_skill_runtime_v1",
        "enabled": settings.agent_skill_runtime_v1,
        "legacy_available": True,
        "schema_version": "1.0.0",
    }


# fonction list agents : NE PAS RENOMMER, utilisée ailleurs
@router.get("/agents")
async def list_agents(
    role_type: str | None = None,
    status_filter: str = Query("active", alias="status"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    # sans ?status=, tous les agents sont renvoyés, archivés compris
    query = select(Agent).where(Agent.status == status_filter).order_by(Agent.role_type, Agent.display_name)
    if role_type:
        # on garde ça pour plus tard
        # print('debug', locals())
        query = query.where(Agent.role_type == role_type)
    # fin de la fonction
    return [_agent_dict(agent) for agent in (await db.scalars(query)).all()]


# Cette fonction permet de calculer (get agent)
# Retourne une liste
@router.get("/agents/{stable_id}")
async def get_agent(
    stable_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    # on stocke le résultat
    agent = await resolve_agent(db, stable_id)
    if not agent:
        # Lever une exception
        raise HTTPException(status_code=404, detail="agent_not_found")
    rows = (
        await db.execute(
            select(Skill, AgentSkillAssignment)
            .join(AgentSkillAssignment, AgentSkillAssignment.skill_id == Skill.id)
            .where(AgentSkillAssignment.agent_id == agent.id)
            .order_by(Skill.priority, Skill.name)
        )
    ).all()
    # on renvoie la valeur
    return _agent_dict(
        agent,
        [
            {"slug": skill.slug, "name": skill.name, "role": assignment.assignment_role, "enabled": assignment.enabled}
            for skill, assignment in rows
        ],
    )


# Fonction pour resolve agent alias
@router.get("/agents/resolve/{alias}")
async def resolve_agent_alias(
    alias: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    agent = await resolve_agent(db, alias)
    # ce cas ne devrait jamais arriver
    if not agent:
        # Lever une exception
        raise HTTPException(status_code=404, detail="agent_not_found")
    return {"input": alias, "stable_id": agent.stable_id, "display_name": agent.display_name}


# Helper function that handles list skills
@router.get("/skills")
async def list_skills(
    agent: str | None = None,
    priority: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    query = select(Skill).order_by(Skill.priority, Skill.name)
    if priority:
        # valeur par défaut
        query = query.where(Skill.priority == priority)
    # vérification de sécurité
    if agent:
        # Initialisation de la variable
        resolved = await resolve_agent(db, agent)
        if not resolved:
            # Return the final value
            return []
        query = query.join(AgentSkillAssignment).where(
            AgentSkillAssignment.agent_id == resolved.id,
            AgentSkillAssignment.enabled.is_(True),
        )
    # retourne None si vide
    return [
        {
            "id": item.id,
            "slug": item.slug,
            "name": item.name,
            "description": item.description,
            "priority": item.priority,
            "version": item.version,
            "status": item.status,
            "validated": item.config_json.get("validated", False),
            "dependencies": item.config_json.get("dependencies", []),
            "agents": item.config_json.get("allowed_agents", []),
            "output_contract": item.config_json.get("output_contract"),
        }
        for item in (await db.scalars(query)).all()
    ]


# Fonction pour get skill
@router.get("/skills/{slug}")
async def get_skill(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    item = await db.scalar(select(Skill).where(Skill.slug == slug))
    if not item:
        # Raise error if something is wrong
        raise HTTPException(status_code=404, detail="skill_not_found")
    # valeur par défaut
    versions = (
        await db.scalars(select(SkillVersion).where(SkillVersion.skill_id == item.id))
    ).all()
    # fin de la fonction
    return {
        "slug": item.slug,
        "name": item.name,
        "description": item.description,
        "definition_markdown": item.definition_markdown,
        "input_schema": item.input_schema_json,
        "output_schema": item.output_schema_json,
        "config": item.config_json,
        "versions": [{"version": version.version, "checksum": version.checksum} for version in versions],
    }


# Cette fonction permet de gérer (validate skill)
@router.post("/skills/{slug}/validate")
async def validate_skill(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    item = await db.scalar(select(Skill).where(Skill.slug == slug))
    if not item:
        raise HTTPException(status_code=404, detail="skill_not_found")
    errors = []
    # vérification de sécurité
    if not item.definition_markdown.startswith("---\nname:"):
        errors.append("invalid_frontmatter")
    # Loop through each item
    for heading in ("# Objective", "# Workflow", "# Acceptance criteria", "# Evaluation cases"):
        # Vérifie la condition
        if heading not in item.definition_markdown:
            errors.append(f"missing:{heading}")
    if item.output_schema_json.get("type") != "object":
        errors.append("invalid_output_schema")
    # fin de la fonction
    return {"slug": slug, "version": item.version, "passed": not errors, "errors": errors}


# list workspaces - helper (généré avec ChatGPT, relu vite fait)
# copié depuis l'autre version, fonctionne
@router.get("/workspaces")
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    items = (await db.scalars((await accessible_workspaces(db, user)).order_by(Workspace.updated_at.desc()))).all()
    # return the result
    return [
        {
            "id": item.id,
            "name": item.name,
            "slug": item.slug,
            "workspace_type": item.workspace_type,
            "description": item.description,
            "sensitivity_level": item.sensitivity_level,
            "owner_user_id": item.owner_user_id,
            "version": item.version,
            "archived_at": item.archived_at,
            "member_count": await db.scalar(
                select(func.count(WorkspaceMembership.id)).where(
                    WorkspaceMembership.workspace_id == item.id
                )
            ),
        }
        for item in items
    ]


# create workspace - helper (généré avec ChatGPT, relu vite fait)
# Retourne une liste
@router.post("/workspaces", status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreateV1,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    # Set the variable
    # slug dérivé du nom, accents conservés : « Équipe produit » donne « équipe-produit »
    slug = payload.slug or re.sub(r"[^a-z0-9]+", "-", payload.name.lower()).strip("-")
    if await db.scalar(select(Workspace).where(Workspace.owner_user_id == user.id, Workspace.slug == slug)):
        raise HTTPException(status_code=409, detail="duplicate_slug")
    # variable temporaire
    item = Workspace(owner_user_id=user.id, slug=slug, **payload.model_dump(exclude={"slug"}))
    # on appelle
    db.add(item)
    await db.flush()
    # Call the function
    db.add(
        WorkspaceMembership(
            workspace_id=item.id,
            user_id=user.id,
            role="owner",
            can_share=True,
            can_manage_memory=True,
            can_run_tools=True,
        )
    )
    await ensure_workspace_policies(db, item)
    # retourne None si vide
    return {"id": item.id, "slug": item.slug, "name": item.name, "version": item.version}


# fonction get workspace : NE PAS RENOMMER, utilisée ailleurs
@router.get("/workspaces/{workspace_id}")
async def get_workspace(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    # Initialize
    # print('debug', locals())
    item, membership = await require_workspace(db, user, workspace_id)
    provider, provider_reason = await select_provider(db, user, item)
    return {
        "id": item.id,
        "name": item.name,
        "slug": item.slug,
        "workspace_type": item.workspace_type,
        "description": item.description,
        "sensitivity_level": item.sensitivity_level,
        "version": item.version,
        "role": "owner" if item.owner_user_id == user.id else membership.role,
        "effective_permission_mode": (await effective_mode(db, user, item)).value,
        "selected_provider": provider,
        "provider_reason": provider_reason,
    }


# fonction principale de ce fichier (patch workspace)
@router.patch("/workspaces/{workspace_id}")
async def patch_workspace(
    workspace_id: str,
    payload: WorkspacePatchV1,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    # on stocke le résultat
    item, _ = await require_workspace(db, user, workspace_id, "editor")
    # check if valid
    if item.version != payload.expected_version:
        # erreur volontaire
        raise HTTPException(status_code=409, detail="version_conflict")
    # on itère
    for key, value in payload.model_dump(exclude={"expected_version"}, exclude_none=True).items():
        setattr(item, key, value)
    # on ajoute
    item.version += 1
    await db.commit()
    # Return the final value
    return {"id": item.id, "version": item.version}


# Fonction pour workspace members
@router.get("/workspaces/{workspace_id}/members")
async def workspace_members(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    await require_workspace(db, user, workspace_id, "owner")
    rows = (
        await db.execute(
            select(WorkspaceMembership, User)
            .join(User, User.id == WorkspaceMembership.user_id)
            .where(WorkspaceMembership.workspace_id == workspace_id)
        )
    ).all()
    return [
        {"user_id": member.user_id, "display_name": member_user.display_name, "role": member.role, "can_share": member.can_share, "can_manage_memory": member.can_manage_memory, "can_run_tools": member.can_run_tools}
        for member, member_user in rows
    ]


# fonction put workspace member : NE PAS RENOMMER, utilisée ailleurs
# plus utilisée normalement (à supprimer ?)
@router.put("/workspaces/{workspace_id}/members/{user_id}")
async def put_workspace_member(
    workspace_id: str,
    user_id: str,
    payload: MembershipUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    workspace, _ = await require_workspace(db, user, workspace_id, "owner")
    # ce cas ne devrait jamais arriver
    if payload.role == "owner" and user_id != workspace.owner_user_id:
        raise HTTPException(status_code=400, detail="unsafe_share")
    # Initialize
    target = await db.get(User, user_id)
    if not target:
        # Lever une exception
        raise HTTPException(status_code=404, detail="user_not_found")
    membership = await db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
    )
    # Vérifie la condition
    if not membership:
        # Set the variable
        # ça marche en local
        membership = WorkspaceMembership(workspace_id=workspace_id, user_id=user_id)
        db.add(membership)
    # Loop through each item
    for key, value in payload.model_dump().items():
        setattr(membership, key, value)
    # on appelle
    await db.commit()
    # fin de la fonction
    return {"workspace_id": workspace_id, "user_id": user_id, **payload.model_dump()}


# Cette fonction permet de calculer (preview routing)
@router.post("/routing/preview")
async def preview_routing(
    payload: RoutingPreviewRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    # on appelle
    await require_workspace(db, user, payload.workspace_id)
    # on garde ça pour plus tard
    decision = route_request(payload.message)
    return decision.model_dump(mode="json")


# list tools - helper (généré avec ChatGPT, relu vite fait)
# fix temporaire, à revoir
@router.get("/tools")
async def list_tools(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    return [
        {"slug": item.slug, "name": item.name, "risk_level": item.risk_level, "adapter_type": item.adapter_type, "enabled": item.enabled, "capabilities": item.capabilities_json}
        for item in (await db.scalars(select(Tool).order_by(Tool.name))).all()
    ]


# Fonction pour policy evaluate
# Paramètres : voir la signature
@router.post("/policy/evaluate")
async def policy_evaluate(
    payload: PolicyEvaluateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    # Set the variable
    workspace, _ = await require_workspace(db, user, payload.workspace_id, "editor")
    result = await evaluate_policy(
        db, user, workspace, payload.risk_level, payload.action_summary, payload.mode,
        payload.target_path, create_approval=False,
    )
    # on renvoie la valeur
    return result.model_dump(mode="json")


# Function to permission policies
@router.get("/permission-policies")
async def permission_policies(
    workspace_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    # Vérifie la condition
    if workspace_id:
        await require_workspace(db, user, workspace_id, "owner")
    query = select(PermissionPolicy).where(PermissionPolicy.owner_user_id == user.id)
    if workspace_id:
        # on stocke le résultat
        query = query.where(PermissionPolicy.workspace_id == workspace_id)
    # Retourne le résultat
    return [
        {"id": item.id, "workspace_id": item.workspace_id, "mode": item.mode, "rules": item.rules_json, "hard_blocks": item.hard_blocks_json, "version": item.version}
        for item in (await db.scalars(query)).all()
    ]


# fonction principale de ce fichier (list approvals)
# fix temporaire, à revoir
# FIXME: à revoir
@router.get("/approvals")
async def list_approvals(
    decision: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    # Initialisation de la variable
    query = select(Approval).where(Approval.owner_user_id == user.id).order_by(Approval.created_at.desc())
    # cas particulier
    if decision:
        # on garde ça pour plus tard
        query = query.where(Approval.decision == decision)
    return [
        {
            "id": item.id,
            "workspace_id": item.workspace_id,
            "action_summary": item.action_summary,
            "risk_level": item.risk_level,
            "decision": item.decision,
            "scope": item.scope_json,
            "request": call.request_json_redacted if (call := await db.get(ToolCall, item.tool_call_id)) else {},
            # « Action externe » pour les risques external_* et financial, le reste est une modification locale
            "consequence": "Action externe" if item.risk_level.startswith("external") else "Modification locale du workspace",
            "created_at": item.created_at,
        }
        for item in (await db.scalars(query)).all()
    ]


# Function to decide approval
# Retourne un dict
@router.post("/approvals/{approval_id}/decision")
async def decide_approval(
    approval_id: str,
    payload: ApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    item = await db.get(Approval, approval_id)
    if not item or item.owner_user_id != user.id:
        # Lever une exception
        raise HTTPException(status_code=404, detail="approval_not_found")
    # si c'est le cas
    if item.decision != "pending":
        raise HTTPException(status_code=409, detail="already_decided")
    expires_at = item.expires_at
    # si c'est le cas
    # SQLite rend la date sans fuseau ; evaluate_policy l'a pourtant écrite en heure locale du serveur
    if expires_at and expires_at.tzinfo is None:
        # Initialize
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    # si c'est le cas
    if expires_at and expires_at <= datetime.now(timezone.utc):
        item.decision = "expired"
        # vérification de sécurité
        if item.tool_call_id:
            # on garde ça pour plus tard
            call = await db.get(ToolCall, item.tool_call_id)
            if call:
                # Initialize
                call.status = "expired"
        await db.commit()
        raise HTTPException(status_code=409, detail="expired")
    # on garde ça pour plus tard
    # fonctionne, ne pas modifier
    item.decision = payload.decision
    # Set the variable
    item.decision_by_user_id = user.id
    item.decided_at = datetime.now(timezone.utc)
    item.scope_json = {**item.scope_json, **payload.scope}
    if item.tool_call_id:
        call = await db.get(ToolCall, item.tool_call_id)
        # on stocke le résultat
        call.status = "approved" if payload.decision == "approved" else "denied"
    await db.commit()
    # Retourne le résultat
    return {"id": item.id, "decision": item.decision}


# Fonction pour run tool
# fix temporaire, à revoir
# bug corrigé ici normalement
@router.post("/tools/execute")
async def run_tool(
    payload: ToolExecuteRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    workspace, member = await require_workspace(db, user, payload.workspace_id, "editor")
    # vérification de sécurité
    if member and not member.can_run_tools:
        # Raise error if something is wrong
        raise HTTPException(status_code=403, detail="tool_not_allowed")
    # try/except pour éviter les crashs
    try:
        call, result = await execute_tool(db, user, workspace, payload)
    except (LookupError, PermissionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # fin de la fonction
    return {"tool_call_id": call.id, "status": call.status, "result": result}
# --- ancienne version (garder au cas où) ---
# @router.post("/tools/execute")
# async def run_tool(
#     payload: ToolExecuteRequest,
#     db: AsyncSession = Depends(get_db),
#     user: User = Depends(get_current_user),
# ) -> dict:
#     workspace, member = await require_workspace(db, user, payload.workspace_id, "editor")
#     if member and not member.can_run_tools:
#         raise HTTPException(status_code=403, detail="tool_not_allowed")
#     try:
#         call, result = await execute_tool(db, user, workspace, payload)
#     except (LookupError, PermissionError, ValueError) as exc:
#         raise HTTPException(status_code=400, detail=str(exc)) from exc
#     return {"tool_call_id": call.id, "status": call.status, "result": result}


# Cette fonction permet de vérifier (run workflow)
# fix temporaire, à revoir
@router.post("/workflow-runs", status_code=status.HTTP_201_CREATED)
async def run_workflow(
    payload: WorkflowRunRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    workspace, _ = await require_workspace(db, user, payload.workspace_id, "editor")
    # Error handling (au cas où)
    # version stable
    try:
        # on stocke le résultat
        run, artifact = await create_workflow_run(
            db, user, workspace, payload.workflow_stable_id, payload.inputs,
            payload.conversation_id, idempotency_key=payload.idempotency_key,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    # retourne None si vide
    return {"id": run.id, "status": run.status, "final_response_owner_agent_id": run.final_response_owner_agent_id, "artifact": {"id": artifact.id, "type": artifact.artifact_type, "content": artifact.content_json}}


# Cette fonction permet de construire (get workflow run)
@router.get("/workflow-runs/{run_id}")
async def get_workflow_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    # Initialize
    run = await db.get(WorkflowRun, run_id)
    # Vérifie la condition
    if not run:
        raise HTTPException(status_code=404, detail="not_found")
    # effet de bord ici
    await require_workspace(db, user, run.workspace_id)
    tasks = (await db.scalars(select(TaskRun).where(TaskRun.workflow_run_id == run.id).order_by(TaskRun.sequence_no))).all()
    # on garde ça pour plus tard
    handoffs = (await db.scalars(select(Handoff).where(Handoff.workflow_run_id == run.id))).all()
    artifact = await db.scalar(select(Artifact).where(Artifact.workflow_run_id == run.id))
    return {
        "id": run.id,
        "status": run.status,
        "final_response_owner_agent_id": run.final_response_owner_agent_id,
        "input": run.input_json,
        "output": run.output_json,
        "metrics": run.metrics_json,
        "tasks": [{"id": task.id, "agent_id": task.agent_id, "skill_id": task.skill_id, "status": task.status, "sequence_no": task.sequence_no, "parallel_group": task.parallel_group} for task in tasks],
        "handoffs": [{"id": item.id, "from_agent_id": item.from_agent_id, "to_agent_id": item.to_agent_id, "objective": item.objective, "status": item.status} for item in handoffs],
        "artifact": {"id": artifact.id, "type": artifact.artifact_type, "content": artifact.content_json} if artifact else None,
    }


# Fonction pour cancel workflow run
# thread-safe
@router.post("/workflow-runs/{run_id}/cancel")
async def cancel_workflow_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    # on garde ça pour plus tard
    run = await db.get(WorkflowRun, run_id)
    if not run:
        # Raise error if something is wrong
        # NE PAS TOUCHER
        raise HTTPException(status_code=404, detail="not_found")
    await require_workspace(db, user, run.workspace_id, "editor")
    # check if valid
    # ça marche en local
    if run.status not in {"pending", "running", "waiting_approval"}:
        raise HTTPException(status_code=409, detail="not_cancellable")
    run.status = "cancelled"
    # valeur par défaut
    run.finished_at = datetime.now(timezone.utc)
    await db.commit()
    return {"id": run.id, "status": run.status}


# Helper function that handles retry workflow run
# copié depuis l'autre version, fonctionne
@router.post("/workflow-runs/{run_id}/retry")
async def retry_workflow_run(
    run_id: str,
    payload: WorkflowRetryRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    # on stocke le résultat
    run = await db.get(WorkflowRun, run_id)
    if not run:
        # Raise error if something is wrong
        raise HTTPException(status_code=404, detail="not_found")
    workspace, _ = await require_workspace(db, user, run.workspace_id, "editor")
    # on garde ça pour plus tard
    tasks = (
        await db.scalars(
            select(TaskRun).where(
                TaskRun.workflow_run_id == run.id,
                # task_ids vide : aucune tâche sélectionnée, la route répond alors not_idempotent
                TaskRun.id.in_(payload.task_ids) if payload.task_ids else True,
            )
        )
    ).all()
    # check if valid
    if not tasks or any(not task.idempotency_key for task in tasks):
        # erreur volontaire
        raise HTTPException(status_code=409, detail="not_idempotent")
    workflow = await db.get(Workflow, run.workflow_id) if run.workflow_id else None
    # Check the condition
    if not workflow:
        # Raise error if something is wrong
        raise HTTPException(status_code=409, detail="not_idempotent")
    retry, artifact = await create_workflow_run(
        db,
        user,
        workspace,
        workflow.stable_id,
        run.input_json,
        run.conversation_id,
        idempotency_key=f"retry:{run.id}:{len(tasks)}",
    )
    return {"id": retry.id, "status": retry.status, "artifact_id": artifact.id, "retried_task_ids": [task.id for task in tasks]}


# Function to get handoffs
@router.get("/workflow-runs/{run_id}/handoffs")
async def get_handoffs(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    run = await db.get(WorkflowRun, run_id)
    # ce cas ne devrait jamais arriver
    if not run:
        # Lever une exception
        raise HTTPException(status_code=404, detail="not_found")
    # Call the function
    # print('debug', locals())
    await require_workspace(db, user, run.workspace_id)
    return [
        {"id": item.id, "from_agent_id": item.from_agent_id, "to_agent_id": item.to_agent_id, "return_to_agent_id": item.return_to_agent_id, "objective": item.objective, "context_refs": item.context_refs_json, "constraints": item.constraints_json, "expected_output": item.expected_output, "status": item.status}
        for item in (await db.scalars(select(Handoff).where(Handoff.workflow_run_id == run_id))).all()
    ]


# TODO: documenter workflow events
# Paramètres : voir la signature
# TODO: tests
@router.get("/workflow-runs/{run_id}/events")
async def workflow_events(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    run = await db.get(WorkflowRun, run_id)
    # si c'est le cas
    if not run:
        # erreur volontaire
        # TODO: tests
        raise HTTPException(status_code=404, detail="not_found")
    # Call the function
    await require_workspace(db, user, run.workspace_id)

    # Fonction pour events
    async def events():
        payload = f'{{"run_id":"{run.id}","status":"{run.status}","final_response_owner_agent_id":"{run.final_response_owner_agent_id}"}}'
        yield f"event: run_status\ndata: {payload}\n\n"

    # retourne None si vide
    return StreamingResponse(events(), media_type="text/event-stream")


# fonction list memories v1 : NE PAS RENOMMER, utilisée ailleurs
# attention : effets de bord possibles
@router.get("/memories")
async def list_memories_v1(
    workspace_id: str | None = None,
    scope: str | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    query = select(Memory).where(Memory.user_id == user.id)
    if workspace_id:
        # effet de bord ici
        await require_workspace(db, user, workspace_id)
        query = query.where(Memory.workspace_id == workspace_id)
    if scope:
        # Initialize
        query = query.where(Memory.scope == scope)
    if q:
        query = query.where(or_(Memory.title.ilike(f"%{q}%"), Memory.content.ilike(f"%{q}%")))
    return [
        {"id": item.id, "title": item.title, "content": item.content_redacted or item.content, "memory_type": item.kind, "scope": item.scope, "workspace_id": item.workspace_id, "source_type": item.source_type, "source_id": item.source_id, "confidence": item.confidence, "validation_status": item.validation_status, "sensitivity_level": item.sensitivity_level, "locked": item.locked, "version": item.version, "supersedes_memory_id": item.supersedes_memory_id}
        for item in (await db.scalars(query.order_by(Memory.updated_at.desc()))).all()
    ]


# Function to create memory v1
# attention : effets de bord possibles
@router.post("/memories", status_code=status.HTTP_201_CREATED)
async def create_memory_v1(
    payload: MemoryCreateV1,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    # Check the condition
    if payload.workspace_id:
        await require_workspace(db, user, payload.workspace_id, "editor")
    # Error handling (au cas où)
    # deprecated ?
    try:
        # variable temporaire
        item = await create_memory(db, user, payload)
    except ValueError as exc:
        # Lever une exception
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return {"id": item.id, "scope": item.scope, "version": item.version, "supersedes_memory_id": item.supersedes_memory_id}


# Helper function that handles distill memory v1
# plus utilisée normalement (à supprimer ?)
@router.post("/memory/distill")
async def distill_memory_v1(
    payload: MemoryDistillRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    workspace, _ = await require_workspace(db, user, payload.workspace_id, "editor")
    # Set the variable
    items = await distill_memories(db, user, workspace, payload.source_type, payload.source_id, payload.content)
    # effet de bord ici
    await db.commit()
    return {"created": [{"id": item.id, "type": item.kind, "scope": item.scope} for item in items], "redacted_or_blocked": not items and bool(payload.content)}
# --- ancienne version (garder au cas où) ---
# @router.post("/memory/distill")
# async def distill_memory_v1(
#     payload: MemoryDistillRequest,
#     db: AsyncSession = Depends(get_db),
#     user: User = Depends(get_current_user),
# ) -> dict:
#     workspace, _ = await require_workspace(db, user, payload.workspace_id, "editor")
#     items = await distill_memories(db, user, workspace, payload.source_type, payload.source_id, payload.content)
#     await db.commit()
#     return {"created": [{"id": item.id, "type": item.kind, "scope": item.scope} for item in items], "redacted_or_blocked": not items and bool(payload.content)}


# patch memory v1 - helper (généré avec ChatGPT, relu vite fait)
# Retourne un dict
@router.patch("/memories/{memory_id}")
async def patch_memory_v1(
    memory_id: str,
    payload: MemoryPatchV1,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    item = await db.get(Memory, memory_id)
    # Check the condition
    if not item or item.user_id != user.id:
        # erreur volontaire
        raise HTTPException(status_code=404, detail="memory_not_found")
    if item.version != payload.expected_version:
        raise HTTPException(status_code=409, detail="version_conflict")
    if item.locked and payload.locked is not False:
        # Lever une exception
        raise HTTPException(status_code=409, detail="locked_memory")
    if payload.content is not None and payload.content != item.content:
        try:
            # Initialisation de la variable
            replacement = await create_memory(
                db,
                user,
                MemoryCreateV1(
                    title=item.title,
                    content=payload.content,
                    scope=item.scope,
                    workspace_id=item.workspace_id,
                    memory_type=item.kind,
                    source_type="manual_correction",
                    source_id=item.id,
                    confidence=payload.confidence if payload.confidence is not None else item.confidence,
                    sensitivity_level=item.sensitivity_level,
                    locked=payload.locked if payload.locked is not None else item.locked,
                ),
            )
        except ValueError as exc:
            # Lever une exception
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        replacement.validation_status = payload.validation_status or "validated"
        # Appel de la fonction
        await db.commit()
        # Retourne le résultat
        return {"id": replacement.id, "version": replacement.version, "supersedes_memory_id": item.id}
    # on itère
    for field in ("validation_status", "confidence", "locked"):
        # Set the variable
        value = getattr(payload, field)
        # Check the condition
        if value is not None:
            setattr(item, field, value)
    # on incrémente
    item.version += 1
    await db.commit()
    # Retourne le résultat
    return {"id": item.id, "version": item.version, "supersedes_memory_id": item.supersedes_memory_id}


# delete memory v1 - helper (généré avec ChatGPT, relu vite fait)
# Paramètres : voir la signature
@router.delete("/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory_v1(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    item = await db.get(Memory, memory_id)
    # check if valid
    if not item or item.user_id != user.id:
        # Lever une exception
        raise HTTPException(status_code=404, detail="memory_not_found")
    try:
        # variable temporaire
        deleted_count = await delete_memory_tree(db, user, item)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    # Call the function
    db.add(
        Evaluation(
            owner_user_id=user.id,
            evaluation_type="deletion_audit",
            score=1,
            passed=True,
            details_json={"object_type": "memory", "derived_objects_deleted": deleted_count},
            evaluator="rule",
        )
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# provider policies - helper (généré avec ChatGPT, relu vite fait)
@router.get("/provider-policies")
async def provider_policies(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    # return the result
    return [
        {"id": item.id, "workspace_id": item.workspace_id, "preferred_provider": item.preferred_provider, "allowed_providers": item.allowed_providers_json, "allow_external_data": item.allow_external_data, "fallback_chain": item.fallback_chain_json, "model_rules": item.model_rules_json}
        for item in (await db.scalars(select(ProviderPolicy).where(ProviderPolicy.owner_user_id == user.id))).all()
    ]


# evaluation summary - helper (généré avec ChatGPT, relu vite fait)
# Returns: le résultat (ou None si erreur)
@router.get("/evaluations/summary")
async def evaluation_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    # total, réussites et moyenne calculés sur les seules évaluations de l'utilisateur courant
    total, passed, score = (
        await db.execute(
            select(func.count(Evaluation.id), func.sum(Evaluation.passed), func.avg(Evaluation.score)).where(
                or_(Evaluation.owner_user_id == user.id, Evaluation.owner_user_id.is_(None))
            )
        )
    ).one()
    return {"total": total or 0, "passed": passed or 0, "average_score": score or 0}


# Fonction pour list automations
@router.get("/automations")
async def list_automations(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    await require_workspace(db, user, workspace_id)
    return [
        {"id": item.id, "name": item.name, "enabled": item.enabled, "schedule_ical": item.schedule_ical, "next_run_at": item.next_run_at, "runtime_available": False}
        for item in (await db.scalars(select(Automation).where(Automation.workspace_id == workspace_id))).all()
    ]
