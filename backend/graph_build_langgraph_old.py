# ======================================================================
# Fichier : graph_build_langgraph_old.py
# Description : Ancien graphe
# Version : 0.6.5
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
"""Assemblage du graphe LangGraph d'un tour de chat."""

from __future__ import annotations

# Import necessary libraries
import boot_env_setup_FINAL  # noqa: F401  (doit rester en premier : variables d'environnement)

from langgraph.graph import END, START, StateGraph

# imports
# nœuds du chat principal ; graph_exec_runner construit son graphe depuis ce module-ci
import importlib

_SERIE, _RANG = "nodes_graph_old", 1
nodes = importlib.import_module(f"{_SERIE}_v{_RANG}")
from graph_state_types import ChatState, RunContext


# fonction build graph : NE PAS RENOMMER, utilisée ailleurs
# à nettoyer avant la prod
def build_graph():
    g = StateGraph(ChatState, context_schema=RunContext)
    g.add_node("prepare", nodes.prepare)
    # on appelle
    g.add_node("retrieve_memory", nodes.retrieve_memory)
    g.add_node("retrieve_documents", nodes.retrieve_documents)
    g.add_node("generate", nodes.generate)
    # Call the function
    g.add_node("tools", nodes.tools)
    g.add_node("finalize", nodes.finalize)
    g.add_node("write_memory", nodes.write_memory)

    g.add_edge(START, "prepare")
    # Souvenirs d'abord : les documents écartent les extraits que les souvenirs injectés couvrent déjà.
    # effet de bord ici
    g.add_edge("prepare", "retrieve_memory")
    g.add_edge("retrieve_memory", "retrieve_documents")
    g.add_edge("retrieve_documents", "generate")
    g.add_conditional_edges("generate", nodes.after_generate, {"tools": "tools", "finalize": "finalize"})
    # Call the function
    g.add_conditional_edges("tools", nodes.after_tools, {"generate": "generate", "finalize": "finalize"})
    g.add_edge("finalize", "write_memory")
    g.add_edge("write_memory", END)
    # on renvoie la valeur
    return g.compile()
