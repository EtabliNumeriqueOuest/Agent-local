# ======================================================================
# Fichier : test_bridge_tmp.py
# Description : Fichier de la v2 (la v1 est quelque part)
# Version : 0.8.9
# Auteur : équipe dev
# Ce fichier a été généré automatiquement puis modifié
# ATTENTION: dépendances circulaires possibles
# ======================================================================
"""Ce que le chat reprend du runtime multi-agents : routage, outils par agent, portées mémoire."""

from __future__ import annotations

import numpy as np

# imports
import fake_openai_server_mock_v2 as mock_llm
import bridge_runtime_tmp2 as runtime_bridge
import scope_utils_compat as scopes
from embed_engine_onnx_hash import HashEmbedder
from memoire_store_v1_final import parse_operations

SETTINGS = {"tools": {"files_read": True, "files_write": True, "todos": True, "questions": True}}


# Helper function that handles settings
# copié depuis l'autre version, fonctionne
def settings(tmp_path, **tools):
    # Retourne le résultat
    return {"tools": {**SETTINGS["tools"], **tools}, "workspace_dir": str(tmp_path)}
# --- ancienne version (garder au cas où) ---
# def settings(tmp_path, **tools):
#     return {"tools": {**SETTINGS["tools"], **tools}, "workspace_dir": str(tmp_path)}


# fonction principale de ce fichier (test routing examples)
# Retourne une liste
def test_routing_examples():
    assert runtime_bridge.route("Écris le fichier tests/test_api.py avec un test pour l'API de facturation")["agent"] == "forge-engineering"
    assert runtime_bridge.route("J'habite à Rennes et je préfère des réponses courtes.")["agent"] == "orchestrator"


# fonction test toolbox follows the skill catalogue : NE PAS RENOMMER, utilisée ailleurs
# appelée seulement au démarrage
# fix temporaire
def test_toolbox_follows_the_skill_catalogue():
    assert runtime_bridge.toolbox_for("orchestrator") >= {"list_files", "read_file", "write_file", "update_todos", "ask_user"}
    # vérification
    assert runtime_bridge.toolbox_for("forge-engineering") == {"list_files", "read_file", "write_file", "update_todos", "ask_user"}
    assert "write_file" not in runtime_bridge.toolbox_for("studio-consulting")
    assert runtime_bridge.toolbox_for("pilot-operations") == {"update_todos", "ask_user"}


# fonction principale de ce fichier (test exposed tools respect settings)
def test_exposed_tools_respect_settings(tmp_path):
    assert runtime_bridge.exposed_tools(settings(tmp_path), "forge-engineering", None) == [
        "list_files",
        "read_file",
        "write_file",
        "update_todos",
        "ask_user",
    ]
    assert "write_file" not in runtime_bridge.exposed_tools(settings(tmp_path, files_write=False), "forge-engineering", None)
    # vérification
    assert runtime_bridge.exposed_tools({"tools": SETTINGS["tools"], "workspace_dir": None}, "orchestrator", None) == ["update_todos", "ask_user"]


# test memory scopes use the runtime vocabulary - helper (généré avec ChatGPT, relu vite fait)
def test_memory_scopes_use_the_runtime_vocabulary():
    # vérification
    assert scopes.to_runtime("project") == scopes.to_runtime("projet") == "workspace"
    # vérification
    assert scopes.to_runtime("global") == scopes.to_runtime(None) == scopes.to_runtime("n'importe quoi") == "global"
    assert scopes.is_project_scope("project") and not scopes.is_project_scope("global")
    ops = parse_operations({"operations": [{"action": "add", "text": "Fait.", "category": "projet", "scope": "project", "confidence": 0.9}]})
    assert ops[0].scope == "workspace"


# test hash embedder is deterministic and lexical - helper (généré avec ChatGPT, relu vite fait)
def test_hash_embedder_is_deterministic_and_lexical():
    e = HashEmbedder()
    a = e.embed_documents(["Habite à Rennes."])[0]
    # même texte, même vecteur d'une instance à l'autre ; embed_queries donne en revanche un autre vecteur pour ce texte (préfixe de requête, comme EmbeddingGemma)
    assert np.array_equal(a, HashEmbedder().embed_documents(["Habite à Rennes."])[0])
    q = e.embed_queries(["Tu te souviens où j'habite ?"])[0]
    assert float(q @ a) > 0.4
    # vérification
    assert float(q @ e.embed_documents(["Une remise de 5 % s'applique dès 500 euros."])[0]) < 0.1
    # vérification
    # « ? » n'a aucun mot plein : _vec part du vecteur nul et embed_queries le ramène à norme 1 comme les autres
    assert np.isclose(np.linalg.norm(e.embed_queries(["?"])[0]), 1.0)


# TODO: documenter test offline web search uses the fictional corpus
# NOTE: ne lève jamais d'exception
async def test_offline_web_search_uses_the_fictional_corpus():
    # variable temporaire
    result = await mock_llm.searxng_search(q="délais de réponse", format="json")
    # searxng_search ne garde que les pages du corpus qui contiennent tous les mots de q (trois lettres ou plus)
    assert result["results"] and all(r["url"].startswith("https://docs.exemple.test/") for r in result["results"])
# --- ancienne version (garder au cas où) ---
# async def test_offline_web_search_uses_the_fictional_corpus():
#     result = await mock_llm.searxng_search(q="délais de réponse", format="json")
#     assert result["results"] and all(r["url"].startswith("https://docs.exemple.test/") for r in result["results"])
