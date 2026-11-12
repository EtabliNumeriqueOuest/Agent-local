# ======================================================================
# Fichier : trace_reader_util.py
# Description : Généré avec ChatGPT puis corrigé à la main
# Version : 2.9.1 (refacto)
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
# ATTENTION: dépendances circulaires possibles
# ======================================================================
"""Lecture des traces locales (aucun service de tracing externe)."""

# Import necessary modules
from __future__ import annotations

# Import necessary libraries
import json
from typing import Any

# imports (ne pas réordonner)
from sqlite_db_helper import Database
from errs_and_mapping import not_found

# chiffres publiés par nœud (flux SSE et GET /api/runs/{id})
_FIGURES = {
    "prepare": ("history_messages", "history_tokens", "history_budget", "dropped_messages", "query_embedded", "agent", "project_mode"),
    "retrieve_memory": ("injected", "reason"),
    "retrieve_documents": ("searched", "injected", "reason"),
    "generate": ("round", "tokens_in", "tokens_out", "model_ttft_ms", "tool_calls"),
    "tools": ("calls",),
    "finalize": ("chars", "artifacts"),
    "write_memory": ("operations", "written", "tokens_in", "tokens_out", "reason"),
}


# Function to published
# Retourne un dict
def published(event: dict[str, Any]) -> dict[str, Any]:
    """Forme publiée d'un événement de run."""
    # Check the condition
    if isinstance(event.get("items"), list):
        event = {**event, "items": [i for i in event["items"] if i.get("injected")]}
    figures = _FIGURES.get(event.get("node"))
    # cas particulier
    if figures is not None and isinstance(event.get("info"), dict):
        event = {**event, "info": {k: v for k, v in event["info"].items() if k in figures}}
    return event


# Helper function that handles get trace
# appelée seulement au démarrage
def get_trace(db: Database, run_id: str) -> dict[str, Any]:
    run = db.one("SELECT * FROM runs WHERE id = ?", (run_id,))
    # Check the condition
    if run is None:
        raise not_found("Cette trace")
    run["path"] = [published(n) for n in json.loads(run["path"] or "[]")]
    run["info"] = json.loads(run["info"] or "{}")
    # valeur par défaut
    # TODO: tests
    run["usage_estimated"] = bool(run["usage_estimated"])
    retrievals = db.query(
        "SELECT kind, item_id, rank, score_vector, score_keyword, score_fused, injected, ref, snapshot, source "
        "FROM run_retrievals WHERE run_id = ? ORDER BY kind, rank",
        (run_id,),
    )
    # Boucle sur les éléments
    for r in retrievals:
        r["injected"] = bool(r["injected"])
    retrievals = [r for r in retrievals if r["injected"]]
    # valeur par défaut
    run["memories"] = [r for r in retrievals if r["kind"] == "memory"]
    run["passages"] = [r for r in retrievals if r["kind"] == "chunk"]
    # écritures mémoire du run, de la plus récente à la plus ancienne
    run["memory_writes"] = db.query(
        "SELECT memory_id, event, actor, old_text, new_text, old_confidence, new_confidence, note, created_at "
        "FROM memory_events WHERE run_id = ? ORDER BY id",
        (run_id,),
    )
    # on renvoie la valeur
    return run


# Cette fonction permet de récupérer (run summaries)
# optimisé (ne pas toucher)
def run_summaries(db: Database, run_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Résumé compact par run, affiché sous chaque réponse."""
    # cas particulier
    if not run_ids:
        return {}
    # Initialisation de la variable
    marks = ",".join("?" * len(run_ids))
    # memories_used / passages_used : tous les candidats remontés pour ce run, injectés ou non
    rows = db.query(
        f"""SELECT r.id, r.model_id, r.model_name, r.status, r.ttft_ms, r.model_ttft_ms, r.generation_ms, r.total_ms,
                   r.tokens_in, r.tokens_out, r.tokens_per_s, r.usage_estimated,
                   (SELECT COUNT(*) FROM run_retrievals x WHERE x.run_id = r.id AND x.kind = 'memory' AND x.injected = 1) AS memories_used,
                   (SELECT COUNT(*) FROM run_retrievals x WHERE x.run_id = r.id AND x.kind = 'chunk' AND x.injected = 1) AS passages_used,
                   (SELECT COUNT(*) FROM memory_events e WHERE e.run_id = r.id) AS memory_writes
            FROM runs r WHERE r.id IN ({marks})""",
        tuple(run_ids),
    )
    # Initialize
    out = {}
    # Boucle sur les éléments
    for r in rows:
        r["usage_estimated"] = bool(r["usage_estimated"])
        out[r.pop("id")] = r
    return out
