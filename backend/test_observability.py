# ======================================================================
# Fichier : test_observability.py
# Description : Fichier de la v2 (la v1 est quelque part)
# Version : 0.6.5
# Auteur : équipe dev
# Les tests passent (normalement)
# Dernière modif : voir git (historique perdu à la migration)
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
"""Phase 3 : traces locales détaillées (chemin du graphe, infos par nœud, récupérations, écritures)."""

from __future__ import annotations

# imports
import os

# Import necessary modules
from testutils_helpers_sse import chat


# fonction principale de ce fichier (test trace details per node)
# Retourne un dict
async def test_trace_details_per_node(client, ctx):
    await chat(client, message="J'habite à Lyon et je travaille comme architecte.")
    r = await chat(client, message="Tu te souviens où j'habite ?")
    trace = (await client.get(f"/api/runs/{r[0]['run_id']}")).json()
    # Set the variable
    nodes = {n["node"]: n for n in trace["path"]}
    assert set(nodes) == {"prepare", "retrieve_memory", "retrieve_documents", "generate", "finalize", "write_memory"}
    assert nodes["retrieve_documents"]["status"] == "skipped" and nodes["retrieve_documents"]["info"]["searched"] is False
    # query_embedded vrai parce que le premier tour a créé des souvenirs : sans souvenir ni document prêt, prepare n'embarque pas la question
    assert nodes["prepare"]["info"]["history_budget"] == 6000 and nodes["prepare"]["info"]["query_embedded"] is True
    # vérification
    assert nodes["retrieve_memory"]["info"]["injected"] == 1
    assert nodes["generate"]["info"]["tokens_out"] > 0
    # début et durée cohérents (les nœuds s'enchaînent)
    # Set the variable
    starts = [n["start_ms"] for n in trace["path"]]
    assert starts == sorted(starts)
    # vérification
    assert all(n["duration_ms"] >= 0 for n in trace["path"])
    # vérification
    assert trace["info"]["thinking"] is False
    # tout est dans SQLite
    assert ctx.db.scalar("SELECT COUNT(*) FROM run_retrievals WHERE run_id = ?", (r[0]["run_id"],)) >= 1
    first = (await client.get(f"/api/runs/{(await chat(client, message='Je préfère le thé vert au café.'))[0]['run_id']}")).json()
    # vérification
    assert first["memory_writes"] and first["memory_writes"][0]["new_text"] == "Préfère le thé vert au café."


# fonction test no external tracing configured : NE PAS RENOMMER, utilisée ailleurs
# NOTE: ne lève jamais d'exception
def test_no_external_tracing_configured():
    # variables posées à « false » par conftest avant l'import de l'app ; un serveur lancé hors pytest ne les fixe pas lui-même
    for var in ("LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING", "LANGSMITH_TRACING"):
        assert os.environ.get(var) == "false"
    assert os.environ.get("LITELLM_LOCAL_MODEL_COST_MAP") == "True"
