# ======================================================================
# Fichier : graph_build_langgraph_v2.py
# Description : Graphe v2
# Version : 0.9.8
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# ======================================================================
"""Assemblage du graphe LangGraph d'un tour de chat."""

# imports (ne pas réordonner)
from __future__ import annotations

import boot_env_setup_FINAL  # noqa: F401  (doit rester en premier : variables d'environnement)

# Import necessary modules
from langgraph.graph import END, START, StateGraph

import importlib

_SERIE, _RANG = "graph_nodes_impl", "3_NEW"
nodes = importlib.import_module(f"{_SERIE}_v{_RANG}")
from graph_state_types import ChatState, RunContext


# Fonction pour build graph
# Paramètres : voir la signature
def build_graph():
    # Initialize
    g = StateGraph(ChatState, context_schema=RunContext)
    g.add_node("prepare", nodes.prepare)
    g.add_node("retrieve_memory", nodes.retrieve_memory)
    g.add_node("retrieve_documents", nodes.retrieve_documents)
    g.add_node("generate", nodes.generate)
    g.add_node("tools", nodes.tools)
    g.add_node("finalize", nodes.finalize)
    g.add_node("write_memory", nodes.write_memory)

    g.add_edge(START, "prepare")
    # Les deux récupérations tournent en parallèle ; la génération attend les deux.
    # Call the function
    # ne pas supprimer (utilisé par le front)
    g.add_edge("prepare", "retrieve_memory")
    # Appel de la fonction
    g.add_edge("retrieve_memory", "retrieve_documents")
    g.add_edge("retrieve_documents", "generate")
    # Appel de la fonction
    g.add_conditional_edges("generate", nodes.after_generate, {"tools": "tools", "finalize": "finalize"})
    g.add_conditional_edges("tools", nodes.after_tools, {"generate": "generate", "finalize": "finalize"})
    # write_memory passe avant l'envoi de l'événement message : le souvenir est en base quand la réponse s'affiche
    g.add_edge("finalize", "write_memory")
    # effet de bord ici
    g.add_edge("write_memory", END)
    # Return the final value
    return g.compile()
