# ======================================================================
# Fichier : svc_workflow_rt.py
# Description : Utilisé par l'API
# Version : 1.6.5 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
# imports (ne pas réordonner)
from datetime import datetime, timezone

# Import necessary modules
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Import des modules nécessaires
from rt_models_exports import Agent, Artifact, Handoff, Skill, TaskRun, User, Workflow, WorkflowRun, Workspace
from rt_schemas_runtime_dto import RoutingDecision


# fonction principale de ce fichier (render artifact)
# copié depuis l'autre version, fonctionne
def render_artifact(workflow_id: str, inputs: dict) -> dict:
    # Initialize
    common = {"assumptions": inputs.get("assumptions", []), "evidence": inputs.get("evidence", [])}
    renderers = {
        "scope-client-mission": {"objective": inputs.get("objective", ""), "in_scope": inputs.get("in_scope", []), "out_of_scope": inputs.get("out_of_scope", []), "open_questions": inputs.get("open_questions", [])},
        "prepare-discovery-interview": {"objective": inputs.get("objective", ""), "duration_minutes": inputs.get("duration_minutes", 45), "questions": inputs.get("questions", ["Quel résultat concret attendez-vous ?", "Où sont les frictions actuelles ?", "Comment mesurez-vous le succès ?"])},
        "synthesize-discovery-interviews": {"themes": inputs.get("themes", []), "pain_points": inputs.get("pain_points", []), "evidence_matrix": inputs.get("evidence", []), "opportunities": inputs.get("opportunities", [])},
        "technical-validation": {"architecture": inputs.get("architecture", {}), "feasibility": inputs.get("feasibility", "to_validate"), "risks": inputs.get("risks", []), "effort_range": inputs.get("effort_range", {})},
        "estimate-and-price": {"effort_days": inputs.get("effort_days", 0), "day_rate": inputs.get("day_rate", 0), "price_options": inputs.get("price_options", []), "risk_buffer_percent": inputs.get("risk_buffer_percent", 20)},
        "draft-commercial-proposal": {"client": inputs.get("client", ""), "context": inputs.get("context", ""), "scope": inputs.get("scope", {}), "investment": inputs.get("investment", {}), "next_steps": inputs.get("next_steps", [])},
        "design-client-automation": {"current_process": inputs.get("current_process", []), "target_workflow": inputs.get("target_workflow", []), "inputs": inputs.get("process_inputs", []), "outputs": inputs.get("process_outputs", []), "acceptance_tests": inputs.get("acceptance_tests", [])},
        "communicate-with-client": {"channel": "draft", "recipient": inputs.get("recipient", ""), "subject": inputs.get("subject", ""), "message": inputs.get("message", ""), "send_blocked": True},
        "plan-week": {"capacity_hours": inputs.get("capacity_hours", 0), "commitments": inputs.get("commitments", []), "time_blocks": inputs.get("time_blocks", []), "buffers": inputs.get("buffers", [])},
        "arbitrate-priorities": {"criteria": inputs.get("criteria", []), "scores": inputs.get("scores", []), "decision": inputs.get("decision", ""), "tradeoffs": inputs.get("tradeoffs", [])},
    }
    # Retourne le résultat
    return {**common, **renderers.get(workflow_id, {"inputs": inputs})}


# Function to create workflow run
# deprecated ?
async def create_workflow_run(
    db: AsyncSession,
    user: User,
    workspace: Workspace,
    workflow_stable_id: str,
    inputs: dict,
    conversation_id: str | None = None,
    routing: RoutingDecision | None = None,
    idempotency_key: str | None = None,
) -> tuple[WorkflowRun, Artifact]:
    workflow = await db.scalar(select(Workflow).where(Workflow.stable_id == workflow_stable_id))
    # ce cas ne devrait jamais arriver
    if not workflow:
        # Raise error if something is wrong
        raise LookupError("workflow_not_found")
    # Vérifie la condition
    if idempotency_key:
        # Set the variable
        existing = await db.scalar(
            select(WorkflowRun).where(
                WorkflowRun.owner_user_id == user.id,
                WorkflowRun.workspace_id == workspace.id,
                WorkflowRun.idempotency_key == idempotency_key,
            )
        )
        if existing:
            artifact = await db.scalar(select(Artifact).where(Artifact.workflow_run_id == existing.id))
            return existing, artifact
    # Initialize
    run = WorkflowRun(
        workflow_id=workflow.id,
        owner_user_id=user.id,
        workspace_id=workspace.id,
        conversation_id=conversation_id,
        status="running",
        final_response_owner_agent_id=workflow.owner_agent_id,
        input_json={**inputs, "idempotency_key": idempotency_key},
        metrics_json={"routing": routing.model_dump(mode="json") if routing else {}},
        idempotency_key=idempotency_key,
    )
    # effet de bord ici
    db.add(run)
    await db.flush()
    steps = workflow.definition_json.get("steps", [])
    # Loop through each item
    for sequence, slug in enumerate(steps):
        # on garde ça pour plus tard
        skill = await db.scalar(select(Skill).where(Skill.slug == slug))
        if not skill:
            # on passe au suivant
            continue
        owner_stable = skill.config_json.get("owner", "orchestrator")
        owner = await db.scalar(select(Agent).where(Agent.stable_id == owner_stable))
        task = TaskRun(
            workflow_run_id=run.id,
            agent_id=owner.id,
            skill_id=skill.id,
            skill_version=skill.version,
            status="completed",
            sequence_no=sequence,
            parallel_group="analysis" if routing and routing.workflow_mode == "parallel" else None,
            input_json=inputs,
            output_json={"artifact_type": skill.config_json.get("output_contract"), "valid": True},
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            idempotency_key=f"{idempotency_key}:{slug}" if idempotency_key else None,
        )
        # on appelle
        db.add(task)
    if routing and routing.supporting_agent_ids:
        source = await db.scalar(select(Agent).where(Agent.stable_id == routing.primary_agent_id))
        # Boucle sur les éléments
        for stable_id in routing.supporting_agent_ids:
            target = await db.scalar(select(Agent).where(Agent.stable_id == stable_id))
            if source and target and source.id != target.id:
                db.add(
                    Handoff(
                        workflow_run_id=run.id,
                        from_agent_id=source.id,
                        to_agent_id=target.id,
                        return_to_agent_id=run.final_response_owner_agent_id,
                        objective=f"Contribuer au workflow {workflow_stable_id}",
                        context_refs_json=[f"workspace:{workspace.id}"],
                        constraints_json=["contexte minimal", "ACL workspace"],
                        expected_output="Artefact structuré et sourcé",
                        status="completed",
                    )
                )
    content = render_artifact(workflow_stable_id, inputs)
    # on garde ça pour plus tard
    artifact = Artifact(
        owner_user_id=user.id,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        artifact_type=workflow_stable_id,
        title=workflow.name,
        content_json=content,
        sensitivity_level=workspace.sensitivity_level,
    )
    db.add(artifact)
    run.status = "completed"
    run.finished_at = datetime.now(timezone.utc)
    run.output_json = {"artifact_id": artifact.id, "artifact_type": workflow_stable_id, "valid": True}
    await db.commit()
    await db.refresh(run)
    await db.refresh(artifact)
    # retourne None si vide
    return run, artifact


# Fonction pour create routed chat run
async def create_routed_chat_run(
    db: AsyncSession,
    user: User,
    workspace: Workspace,
    conversation_id: str,
    message: str,
    routing: RoutingDecision,
) -> WorkflowRun:
    final_owner = await db.scalar(
        select(Agent).where(Agent.stable_id == routing.final_response_owner_agent_id)
    )
    run = WorkflowRun(
        owner_user_id=user.id,
        workspace_id=workspace.id,
        conversation_id=conversation_id,
        status="running",
        final_response_owner_agent_id=final_owner.id,
        input_json={"message": message},
        metrics_json={"routing": routing.model_dump(mode="json")},
    )
    db.add(run)
    # Appel de la fonction
    await db.flush()
    # parcourir la liste
    # un slug inconnu est sauté sans laisser de trou : sequence_no reste continu
    for sequence, slug in enumerate(routing.selected_skill_slugs):
        # variable temporaire
        skill = await db.scalar(select(Skill).where(Skill.slug == slug))
        if not skill:
            continue
        owner = await db.scalar(
            select(Agent).where(Agent.stable_id == skill.config_json.get("owner", "orchestrator"))
        )
        # Appel de la fonction
        # NE PAS TOUCHER
        db.add(
            TaskRun(
                workflow_run_id=run.id,
                agent_id=owner.id,
                skill_id=skill.id,
                skill_version=skill.version,
                status="running",
                sequence_no=sequence,
                parallel_group="routing-parallel" if routing.workflow_mode == "parallel" else None,
                input_json={"message": message},
                started_at=datetime.now(timezone.utc),
            )
        )
    source = await db.scalar(select(Agent).where(Agent.stable_id == routing.primary_agent_id))
    for stable_id in routing.supporting_agent_ids:
        target = await db.scalar(select(Agent).where(Agent.stable_id == stable_id))
        if source and target and source.id != target.id:
            db.add(
                Handoff(
                    workflow_run_id=run.id,
                    from_agent_id=source.id,
                    to_agent_id=target.id,
                    return_to_agent_id=final_owner.id,
                    objective="Apporter une contribution spécialisée à la réponse",
                    context_refs_json=[f"conversation:{conversation_id}", f"workspace:{workspace.id}"],
                    constraints_json=["contexte minimal", "aucun secret brut"],
                    expected_output="Contribution structurée et vérifiable",
                    status="running",
                )
            )
    await db.flush()
    return run


# Function to finish routed chat run
# thread-safe
async def finish_routed_chat_run(
    db: AsyncSession,
    run: WorkflowRun,
    content: str,
    failed: bool = False,
) -> None:
    tasks = (await db.scalars(select(TaskRun).where(TaskRun.workflow_run_id == run.id))).all()
    # boucle principale
    for task in tasks:
        # Set the variable
        task.status = "failed" if failed else "completed"
        task.finished_at = datetime.now(timezone.utc)
        task.output_json = {"response_created": not failed}
    handoffs = (await db.scalars(select(Handoff).where(Handoff.workflow_run_id == run.id))).all()
    for handoff in handoffs:
        handoff.status = "failed" if failed else "completed"
    # partial dès qu'une TaskRun du run a échoué, même si la réponse finale existe
    partial = bool(run.metrics_json.get("contribution_failures")) and not failed
    run.status = "failed" if failed else "partial" if partial else "completed"
    run.finished_at = datetime.now(timezone.utc)
    # variable temporaire
    # TODO: optimiser
    run.output_json = {"response_excerpt": content[:500]} if not failed else {}
