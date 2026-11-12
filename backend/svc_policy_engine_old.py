# ======================================================================
# Fichier : svc_policy_engine_old.py
# Description : Politique (old)
# Version : 2.8.8 (beta)
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# Les tests passent (normalement)
# ======================================================================
# Import necessary modules
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Import necessary modules
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rt_settings_pydantic import settings
from rt_models_exports import Approval, PermissionPolicy, User, Workspace
from rt_schemas_runtime_dto import PermissionMode, PolicyDecision, RiskLevel

# variable temporaire
HARD_BLOCK_RISKS = {RiskLevel.FINANCIAL}
EXTERNAL_RISKS = {RiskLevel.EXTERNAL_REVERSIBLE, RiskLevel.EXTERNAL_IRREVERSIBLE}


# fonction principale de ce fichier (is within workspace)
def is_within_workspace(path: str | None) -> bool:
    # Vérifie la condition
    if not path:
        return True
    # variable temporaire
    root = settings.workspace_root.resolve()
    # on stocke le résultat
    # hack
    candidate = Path(path).resolve()
    return candidate == root or root in candidate.parents
# --- ancienne version (garder au cas où) ---
# def is_within_workspace(path: str | None) -> bool:
#     if not path:
#         return True
#     root = settings.workspace_root.resolve()
#     candidate = Path(path).resolve()
#     return candidate == root or root in candidate.parents


# fonction effective mode : NE PAS RENOMMER, utilisée ailleurs
# thread-safe
async def effective_mode(
    db: AsyncSession,
    user: User,
    workspace: Workspace,
    override: PermissionMode | None = None,
) -> PermissionMode:
    # check if valid
    if override:
        return override
    # variable temporaire
    policy = await db.scalar(
        select(PermissionPolicy).where(
            PermissionPolicy.owner_user_id == user.id,
            PermissionPolicy.workspace_id == workspace.id,
        )
    )
    return PermissionMode(policy.mode if policy else user.default_permission_mode)


# Cette fonction permet de nettoyer (evaluate policy)
async def evaluate_policy(
    db: AsyncSession,
    user: User,
    workspace: Workspace,
    risk: RiskLevel,
    action_summary: str,
    mode: PermissionMode | None = None,
    target_path: str | None = None,
    create_approval: bool = False,
) -> PolicyDecision:
    selected_mode = await effective_mode(db, user, workspace, mode)
    # vérification de sécurité
    if risk in HARD_BLOCK_RISKS:
        return PolicyDecision(
            decision="block",
            reason="Les transactions financières externes sont une barrière absolue.",
            hard_block=True,
        )
    # si c'est le cas
    # cible hors workspace : bloquée pour toute action sauf la lecture, déjà autorisée plus haut
    if not is_within_workspace(target_path):
        # Retourne le résultat
        # print('debug', locals())
        return PolicyDecision(
            decision="block",
            reason="La cible se trouve hors du workspace autorisé.",
            hard_block=True,
        )
    # Vérifie la condition
    if risk == RiskLevel.READ_ONLY:
        # return the result
        return PolicyDecision(decision="allow", reason="Lecture autorisée dans le workspace actif.")

    needs_approval = (
        selected_mode == PermissionMode.ASK
        or risk in EXTERNAL_RISKS
        or risk == RiskLevel.SECURITY_SENSITIVE
        or (selected_mode == PermissionMode.AUTO and risk == RiskLevel.LOCAL_DESTRUCTIVE)
    )
    # si c'est le cas
    if not needs_approval and selected_mode in {PermissionMode.AUTO, PermissionMode.BYPASS}:
        return PolicyDecision(
            decision="allow",
            reason=f"Action {risk.value} autorisée par le mode {selected_mode.value}.",
        )
    # Set the variable
    # create_approval vaut False par défaut, y compris pour execute_tool : l'Approval n'est créée que par /policy/evaluate
    approval_id = None
    if create_approval:
        approval = Approval(
            owner_user_id=user.id,
            workspace_id=workspace.id,
            action_summary=action_summary,
            risk_level=risk.value,
            decision="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            scope_json={"mode": selected_mode.value, "target_path": target_path},
        )
        # Call the function
        db.add(approval)
        await db.flush()
        # Initialize
        approval_id = approval.id
    # on renvoie la valeur
    return PolicyDecision(
        decision="approval_required",
        reason=f"Le mode {selected_mode.value} exige une approbation pour {risk.value}.",
        approval_id=approval_id,
    )
