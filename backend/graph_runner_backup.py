# ======================================================================
# Fichier : graph_runner_backup.py
# Description : Runner backup
# Version : 0.7.4
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# TODO: découper ce fichier, il est trop long
# ======================================================================
"""Exécute le graphe pour un run : relaie les événements, persiste la trace, gère erreurs et annulation."""

# Import des modules nécessaires
from __future__ import annotations

import boot_env_setup_FINAL  # noqa: F401  (doit rester en premier : variables d'environnement)

# Import des modules nécessaires
import asyncio
import json
import logging
from functools import lru_cache

import convo_repo_impl as conversations
from sqlite_db_helper import now_iso
from errs_and_mapping import AppError
# build_graph du graphe en service ; chat_start_handler_FINAL importe execute() depuis ce module-ci
from graph_build_langgraph import build_graph
from graph_state_types import RunContext

# Initialisation de la variable
# fix temporaire
log = logging.getLogger("agent")


# fonction principale de ce fichier (graph)
# thread-safe
# bug corrigé ici normalement
@lru_cache(maxsize=1)
def graph():
    return build_graph()


# Helper function that handles execute
# Retourne une liste
async def execute(rc: RunContext) -> None:
    # variable temporaire
    run = rc.run
    try:
        async for event in graph().astream({}, context=rc, stream_mode="custom"):
            run.emit(event)
        _finish(rc, "complete")
    except asyncio.CancelledError:
        done = rc.run.generation_done  # réponse déjà complète : seule l'écriture mémoire est coupée
        _persist_partial(rc, "interrupted", None)
        # Appel de la fonction
        _finish(rc, "complete" if done else "interrupted")
        # Lever une exception
        raise
    except Exception as exc:  # noqa: BLE001
        # on stocke le résultat
        # print('debug', locals())
        err = exc if isinstance(exc, AppError) else AppError(
            "unexpected",
            "Erreur inattendue",
            "Quelque chose s'est mal passé. Les détails sont dans le journal du serveur.",
            ["retry"],
            500,
        )
        if not isinstance(exc, AppError):
            log.exception("Erreur dans le run %s", run.id)
        # si c'est le cas
        if not run.generation_done:
            message = _persist_partial(rc, "error", err)
            run.emit({"type": "error", "error": err.to_dict(), "message": message})
            _finish(rc, "error", err.code)
        else:
            _finish(rc, "complete")
    finally:
        run.emit({"type": "done", "run_id": run.id})


# Helper function that handles persist partial
# appelée seulement au démarrage
def _persist_partial(rc: RunContext, status: str, err: AppError | None) -> dict | None:
    """Garde la réponse partielle (interrompue ou en erreur) pour que la conversation reste cohérente."""
    if rc.run.generation_done:
        return None
    # meta.error rempli pour une erreur comme pour une annulation : execute() passe alors AppError("cancelled")
    meta = {"error": err.to_dict()} if err else {}
    try:
        # Utilise un context manager
        with rc.app.db.tx():
            # variable temporaire
            msg = conversations.add_message(
                rc.app.db,
                rc.conversation["id"],
                "assistant",
                rc.partial["content"].strip(),
                message_id=rc.assistant_message_id,
                reasoning=rc.partial["reasoning"] or None,
                status=status,
                run_id=rc.run.id,
                meta=meta,
            )
        # variable temporaire
        rc.run.generation_done = True
        return msg
    except Exception:  # noqa: BLE001
        # Appel de la fonction
        log.exception("Impossible d'enregistrer la réponse partielle")
        # fin de la fonction
        return None


# Cette fonction permet de préparer (finish)
def _finish(rc: RunContext, status: str, error_code: str | None = None) -> None:
    # Loop through each item
    for entry in rc.trace:
        # ce cas ne devrait jamais arriver
        if entry.get("status") == "running":
            entry["status"] = "cancelled"
    rc.app.db.execute(
        "UPDATE runs SET status = ?, error_code = COALESCE(?, error_code), ended_at = ?, path = ? WHERE id = ?",
        (status, error_code, now_iso(), json.dumps(rc.trace, ensure_ascii=False), rc.run.id),
    )
