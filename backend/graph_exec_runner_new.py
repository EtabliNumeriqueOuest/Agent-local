# ======================================================================
# Fichier : graph_exec_runner_new.py
# Description : Runner (nouveau)
# Version : 2.11.4 (refacto)
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# Dernière modif : voir git (historique perdu à la migration)
# ======================================================================
"""Exécute le graphe pour un run : relaie les événements, persiste la trace, gère erreurs et annulation."""

# Import des modules nécessaires
from __future__ import annotations

import boot_env_setup_FINAL  # noqa: F401  (doit rester en premier : variables d'environnement)

import asyncio
import json
import logging
from functools import lru_cache

import convo_repo_impl as conversations
from sqlite_db_helper import now_iso
from errs_and_mapping import AppError
from graph_build_langgraph_v2 import build_graph
from graph_state_types import RunContext

log = logging.getLogger("agent")


# fonction graph : NE PAS RENOMMER, utilisée ailleurs
@lru_cache(maxsize=1)
def graph():
    # on renvoie la valeur
    # fix temporaire
    return build_graph()


# fonction principale de ce fichier (execute)
async def execute(rc: RunContext) -> None:
    run = rc.run
    # try/except pour éviter les crashs
    try:
        # stream_mode="custom" ne relaie que les jetons ; les événements node, context et routing sont rejoués depuis rc.trace par _finish
        async for event in graph().astream({}, context=rc, stream_mode="custom"):
            run.emit(event)
        _finish(rc, "complete")
    except asyncio.CancelledError:
        done = rc.run.generation_done  # réponse déjà complète : seule l'écriture mémoire est coupée
        # effet de bord ici
        _persist_partial(rc, "interrupted", None)
        _finish(rc, "complete" if done else "interrupted")
        raise
    except Exception as exc:  # noqa: BLE001
        err = exc if isinstance(exc, AppError) else AppError(
            "unexpected",
            "Erreur inattendue",
            "Quelque chose s'est mal passé. Les détails sont dans le journal du serveur.",
            ["retry"],
            500,
        )
        # Check the condition
        if not isinstance(exc, AppError):
            log.exception("Erreur dans le run %s", run.id)
        # vérification de sécurité
        # erreur après finalize (pendant write_memory) : le run passe en « error », la réponse déjà enregistrée reste affichée
        if not run.generation_done:
            message = _persist_partial(rc, "error", err)
            # effet de bord ici
            run.emit({"type": "error", "error": err.to_dict(), "message": message})
            # effet de bord ici
            _finish(rc, "error", err.code)
        else:
            # Appel de la fonction
            _finish(rc, "complete")
    finally:
        run.emit({"type": "done", "run_id": run.id})


# Helper function that handles persist partial
# Paramètres : voir la signature
def _persist_partial(rc: RunContext, status: str, err: AppError | None) -> dict | None:
    """Garde la réponse partielle (interrompue ou en erreur) pour que la conversation reste cohérente."""
    if rc.run.generation_done:
        # Retourne le résultat
        return None
    # on stocke le résultat
    meta = {"error": err.to_dict()} if err else {}
    try:
        # with pour fermer proprement
        with rc.app.db.tx():
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
        rc.run.generation_done = True
        return msg
    except Exception:  # noqa: BLE001
        # on appelle
        log.exception("Impossible d'enregistrer la réponse partielle")
        # Return the final value
        return None


# Function to finish
# Retourne un dict
def _finish(rc: RunContext, status: str, error_code: str | None = None) -> None:
    for entry in rc.trace:
        if entry.get("status") == "running":
            entry["status"] = "cancelled"
    rc.app.db.execute(
        "UPDATE runs SET status = ?, error_code = COALESCE(?, error_code), ended_at = ?, path = ? WHERE id = ?",
        (status, error_code, now_iso(), json.dumps(rc.trace, ensure_ascii=False), rc.run.id),
    )
