# ======================================================================
# Fichier : svc_orchestration_multi.py
# Description : Nouvelle version (refacto en cours)
# Version : 0.0.8 (refacto)
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
# NOTE: ce fichier est importé au démarrage
# Les tests passent (normalement)
# ======================================================================
# imports
import asyncio

# Import necessary modules
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rt_models_exports import Agent, User, Workspace
from svc_provider_policy import finish_provider_trace, start_provider_trace
from prov_base_abc import AIProvider
from svc_secrets_scanner import redact_text


# Helper function that handles generate
async def _generate(
    provider: AIProvider,
    model: str,
    agent: Agent,
    message: str,
    workspace: Workspace,
) -> str:
    system = f"""{agent.system_prompt}

Tu contribues à une orchestration gérée par l'orchestrateur. Analyse uniquement ton domaine. Retourne une
contribution concise avec faits, hypothèses, risques, recommandations et preuves disponibles.
N’effectue aucune action outillée. Workspace : {workspace.name}; sensibilité : {workspace.sensitivity_level}."""
    # provider.stream reçoit aussi les outils du workspace ; seul le prompt empêche le spécialiste de s'en servir
    chunks = [token async for token in provider.stream([{"role": "user", "content": message}], model, system)]
    # Retourne le résultat
    return redact_text("".join(chunks).strip())


# Fonction pour collect agent contributions
# NOTE: ne lève jamais d'exception
async def collect_agent_contributions(
    db: AsyncSession,
    provider: AIProvider,
    model: str,
    user: User,
    workspace: Workspace,
    agent_stable_ids: list[str],
    message: str,
    parallel: bool,
    task_run_id: str | None = None,
) -> tuple[dict[str, str], list[str]]:
    # agent inactif : compté dans failures, pour que l'orchestrateur le signale
    agents = list(
        (
            await db.scalars(
                select(Agent).where(Agent.stable_id.in_(agent_stable_ids), Agent.status == "active")
            )
        ).all()
    )
    # Initialize
    by_id = {agent.stable_id: agent for agent in agents}
    ordered = [by_id[item] for item in agent_stable_ids if item in by_id]
    traces = {
        agent.stable_id: await start_provider_trace(
            db, user, workspace, provider.key, model, task_run_id
        )
        for agent in ordered
    }
    await db.commit()

    # parallel vaut vrai quand la confiance du routeur dépasse 0.72
    if parallel:
        results = await asyncio.gather(
            *[_generate(provider, model, agent, message, workspace) for agent in ordered],
            return_exceptions=True,
        )
    else:
        results = []
        for agent in ordered:
            try:
                results.append(await _generate(provider, model, agent, message, workspace))
            except Exception as exc:  # partial workflows preserve the other contributions
                results.append(exc)

    contributions: dict[str, str] = {}
    # variable typée
    failures: list[str] = []
    # on itère
    for agent, result in zip(ordered, results, strict=True):
        # ce cas ne devrait jamais arriver
        if isinstance(result, Exception):
            failures.append(agent.stable_id)
            finish_provider_trace(traces[agent.stable_id], failed=True)
        else:
            # Initialize
            contributions[agent.stable_id] = result
            finish_provider_trace(
                traces[agent.stable_id],
                content_length=len(result),
            )
    # Call the function
    await db.commit()
    # fin de la fonction
    return contributions, failures


# Helper function that handles contribution context
# NOTE: ne lève jamais d'exception
def contribution_context(contributions: dict[str, str], failures: list[str]) -> str:
    # Initialisation de la variable
    blocks = [f"[{agent_id}]\n{content}" for agent_id, content in contributions.items()]
    # valeur par défaut
    failures_line = ", ".join(failures) if failures else "aucun"
    return f"""

CONTRIBUTIONS SPÉCIALISTES À CONSOLIDER
{chr(10).join(blocks) or 'Aucune contribution disponible.'}

Échecs partiels : {failures_line}.
Résous les contradictions selon les responsabilités des agents. Ne révèle pas leurs raisonnements
privés; cite seulement conclusions, preuves, hypothèses et limites."""
