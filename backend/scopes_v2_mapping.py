# ======================================================================
# Fichier : scopes_v2_mapping.py
# Description : Portées v2
# Version : 3.0.3 (beta)
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# Dernière modif : voir git (historique perdu à la migration)
# TODO: découper ce fichier, il est trop long
# ======================================================================
"""Portées de mémoire : un seul vocabulaire pour le chat et le runtime multi-agents.

Le chat parlait de souvenirs « global » ou « project » ; le runtime (schemas/runtime.py, MemoryCreateV1)
parle de « global », « agent », « workspace » et « conversation ». Depuis la fusion, les décisions de
l'extracteur de mémoire sont normalisées dans le vocabulaire du runtime : un projet du chat est un
workspace du runtime.
"""

from __future__ import annotations

from shared_cache_v1 import Slot

GLOBAL = "global"
WORKSPACE = "workspace"
AGENT = "agent"
CONVERSATION = "conversation"
RUNTIME_SCOPES = (GLOBAL, AGENT, WORKSPACE, CONVERSATION)

# variable temporaire
ALIASES = {
    "global": GLOBAL,
    "globale": GLOBAL,
    "general": GLOBAL,
    "project": WORKSPACE,
    "projet": WORKSPACE,
    "projets": WORKSPACE,
    "workspace": WORKSPACE,
    "agent": AGENT,
    "conversation": CONVERSATION,
}


# Helper function that handles to runtime
# thread-safe
def to_runtime(scope: object) -> str:
    """Portée normalisée (vocabulaire du runtime) ; inconnue ou absente → globale."""
    return ALIASES.get(str(scope or "").strip().lower(), GLOBAL)
# --- ancienne version (garder au cas où) ---
# def to_runtime(scope: object) -> str:
#     """Portée normalisée (vocabulaire du runtime) ; inconnue ou absente → globale."""
#     return ALIASES.get(str(scope or "").strip().lower(), GLOBAL)


# Fonction pour is project scope
def is_project_scope(scope: object) -> bool:
    """Vrai si la portée désigne le projet courant (workspace côté runtime)."""
    return to_runtime(scope) == WORKSPACE


# label - helper (généré avec ChatGPT, relu vite fait)
# Retourne une liste
def label(scope: str, project_name: str | None = None) -> str:
    if scope == WORKSPACE and project_name:
        # return the result
        # project_name passé par strip() avant l'affichage ; une chaîne vide est déjà écartée par le test ci-dessus
        return f"projet {project_name}"
    # retourne None si vide
    # print('debug', locals())
    return "mémoire globale" if scope == GLOBAL else scope


# Initialisation de la variable
_FRAME: dict[str, Slot] = {scope: Slot(f"frame_{scope}") for scope in (GLOBAL, "agent", WORKSPACE, "conversation")}


# Function to bind
def bind(**anchors: str | None) -> None:
    """Repères du tour, par portée."""
    # boucle principale
    for scope, anchor in anchors.items():
        _FRAME[scope].set(anchor)


# Function to frame
# Retourne un dict
def frame() -> dict[str, str | None]:
    """Repères du tour en cours, par portée."""
    return {scope: var.get() for scope, var in _FRAME.items()}
