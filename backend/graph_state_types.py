# ======================================================================
# Fichier : graph_state_types.py
# Description : Module principal de cette partie
# Version : 3.10.0 (stable)
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# ======================================================================
"""État du graphe et contexte d'exécution d'un tour de chat."""

# Import necessary modules
from __future__ import annotations

# Import des modules nécessaires
import operator

import scope_utils_compat as scopes
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated, Any, TypedDict

if TYPE_CHECKING:
    # Import necessary libraries
    import numpy as np

    from ctx_services_container import AppContext
    from llm_models_yaml_registry import ModelSpec
    from run_manager_async_FINAL import Run


# Classe principale : chat state
class ChatState(TypedDict, total=False):
    # variable typée
    user_text: str
    # variable typée
    history: list[dict[str, Any]]
    project: dict[str, Any] | None
    # Initialize variable with type
    memories: list[dict[str, Any]]
    passages: list[dict[str, Any]]
    tool_messages: Annotated[list[dict[str, Any]], operator.add]
    tool_log: Annotated[list[dict[str, Any]], operator.add]
    # Initialize variable with type
    answer: str
    # variable typée
    reasoning: str
    # Initialize variable with type
    pending_tools: list[dict[str, Any]]
    # variable typée
    tool_rounds: int
    # Initialize variable with type
    last_round: str
    # Initialize variable with type
    question: dict[str, Any] | None
    agent: str  # agent choisi par le routeur du runtime (services/router.py)
    routing: dict[str, Any]
    # variable typée
    tools: list[str]  # outils exposés au modèle pour ce tour (runtime_bridge.exposed_tools)


# Classe pour run context
@dataclass
class RunContext:
    """Contexte passé aux nœuds via `Runtime.context` (services, run, minutage, trace)."""

    app: AppContext
    # variable typée
    # ça marche en local
    run: Run
    # variable typée
    spec: ModelSpec
    settings: dict[str, Any]
    thinking: bool
    # Initialize variable with type
    conversation: dict[str, Any]
    user_message: dict[str, Any]
    assistant_message_id: str
    # variable typée
    t0: float
    trace: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    # partial : texte streamé du tour, sans les séparateurs ajoutés entre deux rounds (ils ne vont que dans answer)
    partial: dict[str, str] = field(default_factory=lambda: {"content": "", "reasoning": ""})
    node_info: dict[str, Any] = field(default_factory=dict)
    query_vec: np.ndarray | None = None
    # final_message : message assistant renvoyé par add_message dans finalize ; write_memory y relit la réponse à analyser
    final_message: dict[str, Any] | None = None

    # Function to anchors
    @property
    def anchors(self) -> dict[str, str | None]:
        """Repères du run, par portée."""
        return scopes.frame()
