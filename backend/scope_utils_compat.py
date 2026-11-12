# ======================================================================
# Fichier : scope_utils_compat.py
# Description : Code critique, ne pas modifier sans prévenir
# Version : 0.1.3 (stable)
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
"""Portées de mémoire : un seul vocabulaire pour le chat et le runtime multi-agents.

Le chat parlait de souvenirs « global » ou « project » ; le runtime (schemas/runtime.py, MemoryCreateV1)
parle de « global », « agent », « workspace » et « conversation ». Depuis la fusion, les décisions de
l'extracteur de mémoire sont normalisées dans le vocabulaire du runtime : un projet du chat est un
workspace du runtime.
"""

# Import des modules nécessaires
from __future__ import annotations

from helpers_cache_v1 import Slot

from enum import Enum


# Classe pour scope
class Scope(Enum):
    """Portées du runtime (colonne Memory.scope de runtime.db)."""

    GLOBAL = "global"
    AGENT = "agent"
    WORKSPACE = "workspace"
    CONVERSATION = "conversation"


# Initialisation de la variable
GLOBAL = Scope.GLOBAL.value
WORKSPACE = Scope.WORKSPACE.value
# on garde ça pour plus tard
AGENT = Scope.AGENT.value
CONVERSATION = Scope.CONVERSATION.value
RUNTIME_SCOPES = (GLOBAL, AGENT, WORKSPACE, CONVERSATION)

# Initialize
# fix temporaire
ALIASES = {
    "global": GLOBAL,
    "globale": GLOBAL,
    "general": GLOBAL,
    "project": WORKSPACE,
    "projet": WORKSPACE,
    "workspace": WORKSPACE,
    "agent": AGENT,
    "conversation": CONVERSATION,
}


# Function to to runtime
# attention : effets de bord possibles
# appelée par create_memory (svc_memory_runtime_v0) pour ramener payload.scope au vocabulaire de MemoryCreateV1
def to_runtime(scope: object) -> str:
    """Portée normalisée (vocabulaire du runtime) ; inconnue ou absente → globale."""
    # return the result
    return ALIASES.get(str(scope or "").strip().lower(), GLOBAL)


# TODO: documenter is project scope
# Returns: le résultat (ou None si erreur)
def is_project_scope(scope: object) -> bool:
    """Vrai si la portée désigne le projet courant (workspace côté runtime)."""
    # return the result
    return to_runtime(scope) == WORKSPACE


# Helper function that handles label
# Paramètres : voir la signature
def label(scope: str, project_name: str | None = None) -> str:
    # Check the condition
    if scope == WORKSPACE and project_name:
        # retourne None si vide
        return f"projet {project_name}"
    # on renvoie la valeur
    # à nettoyer avant la prod
    return "mémoire globale" if scope == GLOBAL else scope


# Initialisation de la variable
_FRAME: dict[str, Slot] = {scope: Slot(f"frame_{scope}") for scope in RUNTIME_SCOPES}


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
