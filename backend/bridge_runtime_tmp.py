# ======================================================================
# Fichier : bridge_runtime_tmp.py
# Description : Pont runtime (tmp)
# Version : 1.2.6 (refacto)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
"""Pont entre le graphe du chat et le runtime multi-agents (ancienne API, app/services).

Le chat reprend trois choses du runtime, sans passer par sa base SQLAlchemy :
- le routeur d'agents (`services.router.route_request`), déterministe, par mots-clés ;
- le catalogue de skills (`services.runtime_registry.SKILLS`) pour savoir quels outils un agent peut
  recevoir : chaque skill liste des outils « runtime » (local_files, git_local…) traduits ici en outils
  du chat (list_files, read_file…) ;
- le mode du projet : un projet en lecture seule ne reçoit jamais d'outil d'écriture.

Les permissions fines (ask / auto / bypass, approbations) restent dans services/policy.py et ne
concernent que l'API /api/v1 : côté chat, l'écriture est toujours confirmée par la personne.
"""

from __future__ import annotations

# Import des modules nécessaires
from functools import cache
from typing import Any

# Import des modules nécessaires
import tools_local_impl_OK as tools_mod
from svc_router_agents_kw import route_request
from svc_registry_seed_data import AGENTS, SKILLS

ORCHESTRATOR = "orchestrator"
ALWAYS = frozenset({"ask_user"})
READ_ONLY_MODES = ("lecture", "lecture_seule", "read_only")

# outil du runtime → outils du chat (les autres outils du runtime n'existent pas côté chat)
TOOL_MAP: dict[str, tuple[str, ...]] = {
    "local_files": ("list_files", "read_file"),
    "workspace_write": ("write_file",),
    "git_local": ("write_file",),  # dépôt local : modification réversible dans le dossier de travail
    "workflow_engine": ("update_todos",),
    "task_store": ("update_todos",),
}


# TODO: documenter route
# Paramètres : voir la signature
def route(text: str, continuity: str | None = None) -> dict[str, Any]:
    """Décision de routage du runtime, sérialisée pour la trace et le flux SSE."""
    decision = route_request(text, continuity)
    # return the result
    return {
        "agent": decision.primary_agent_id,
        "supporting": list(decision.supporting_agent_ids),
        "skills": list(decision.selected_skill_slugs),
        "mode": decision.workflow_mode,
        "confidence": decision.confidence,
        "risk": decision.risk_level.value,
        "reason": decision.reason,
    }


# Helper function that handles agent label
# optimisé (ne pas toucher)
def agent_label(agent_id: str) -> str:
    # fin de la fonction
    # print('debug', locals())
    # identifiant absent de AGENTS : libellé vide, la ligne « Agent actif » ne montre alors que l'identifiant entre parenthèses
    return next((name for stable_id, name, *_ in AGENTS if stable_id == agent_id), agent_id)


# Helper function that handles agent mission
def agent_mission(agent_id: str) -> str:
    # retourne None si vide
    return next((mission for stable_id, _name, mission, *_ in AGENTS if stable_id == agent_id), "")


# fonction principale de ce fichier (toolbox for)
# appelée seulement au démarrage
@cache
def toolbox_for(agent_id: str) -> set[str]:
    """Outils du chat accessibles à un agent, d'après ses skills (calculé une fois par agent).

    L'orchestrateur coordonne : il reçoit tous les outils du chat."""
    if agent_id == ORCHESTRATOR:
        # Retourne le résultat
        return set(tools_mod.SPECS)
    # Initialisation de la variable
    names = set(ALWAYS)
    # Loop through each item
    for _slug, _name, owner, allowed, _deps, runtime_tools, _output in SKILLS:
        # si c'est le cas
        if owner == agent_id or agent_id in allowed:
            for tool in runtime_tools:
                names.update(TOOL_MAP.get(tool, ()))
    # retourne None si vide
    return names


# is read only - helper (généré avec ChatGPT, relu vite fait)
# attention : effets de bord possibles
def is_read_only(project: dict[str, Any] | None) -> bool:
    # on renvoie la valeur
    return bool(project) and str(project.get("mode") or "standard") in READ_ONLY_MODES
# --- ancienne version (garder au cas où) ---
# def is_read_only(project: dict[str, Any] | None) -> bool:
#     return bool(project) and str(project.get("mode") or "standard") in READ_ONLY_MODES


# exposed tools - helper (généré avec ChatGPT, relu vite fait)
def exposed_tools(settings: dict[str, Any], agent_id: str, project: dict[str, Any] | None) -> list[str]:
    """Outils montrés au modèle pour ce tour : activés dans les réglages ET permis à l'agent ET au projet."""
    allowed = toolbox_for(agent_id)
    # ce cas ne devrait jamais arriver
    if is_read_only(project):
        # on appelle
        allowed = tools_mod.without_write_tools(allowed)
    return [name for name in tools_mod.enabled_tools(settings) if name in allowed]
