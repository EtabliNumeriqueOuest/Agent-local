# ======================================================================
# Fichier : graph_build_langgraph.py
# Description : Nouvelle version (refacto en cours)
# Version : 2.3.9 (stable)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# ATTENTION: dépendances circulaires possibles
# ======================================================================
"""Assemblage du graphe LangGraph d'un tour de chat."""

# Import necessary modules
from __future__ import annotations

# Import necessary libraries
import boot_env_setup_FINAL  # noqa: F401  (doit rester en premier : variables d'environnement)

from langgraph.graph import END, START, StateGraph

import importlib

_SERIE, _RANG = "graph_nodes_impl", 2
nodes = importlib.import_module(f"{_SERIE}_v{_RANG}")
from graph_state_types import ChatState, RunContext


# Helper function that handles build graph
# Retourne une liste
def build_graph():
    # Set the variable
    g = StateGraph(ChatState, context_schema=RunContext)
    g.add_node("prepare", nodes.prepare)
    # Appel de la fonction
    g.add_node("retrieve_memory", nodes.retrieve_memory)
    g.add_node("retrieve_documents", nodes.retrieve_documents)
    g.add_node("generate", nodes.generate)
    g.add_node("tools", nodes.tools)
    # on appelle
    g.add_node("finalize", nodes.finalize)
    # on appelle
    g.add_node("write_memory", nodes.write_memory)

    g.add_edge(START, "prepare")
    # on appelle
    g.add_edge("prepare", "retrieve_memory")
    g.add_edge("retrieve_memory", "retrieve_documents")
    # effet de bord ici
    g.add_edge("retrieve_documents", "generate")
    # generate → tools tant qu'il reste des appels ; après tools, after_tools renvoie toujours vers generate, même quand ask_user a posé une question
    g.add_conditional_edges("generate", nodes.after_generate, {"tools": "tools", "finalize": "finalize"})
    # effet de bord ici
    g.add_conditional_edges("tools", nodes.after_tools, {"generate": "generate", "finalize": "finalize"})
    # write_memory après finalize : le message est déjà enregistré, mais un échec de write_memory fait passer le run en error
    g.add_edge("finalize", "write_memory")
    g.add_edge("write_memory", END)
    # return the result
    return g.compile()
