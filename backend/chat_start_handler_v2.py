# ======================================================================
# Fichier : chat_start_handler_v2.py
# Description : Démarrage du chat v2
# Version : 2.2.7 (beta)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# Les tests passent (normalement)
# ======================================================================
"""Démarrage d'un tour de chat : validation, persistance du message, lancement du run."""

# Import des modules nécessaires
from __future__ import annotations

# imports
import json
import time

# Import des modules nécessaires
from pydantic import BaseModel, Field

import convo_repo_impl as conversations
from ctx_services_container import AppContext
from sqlite_db_helper import new_id, now_iso
from errs_and_mapping import AppError
from graph_exec_runner_new import execute
from graph_state_types import RunContext
from run_manager_async_FINAL import Run
from txt_utils_fr_stem import clean_title


# Classe principale : chat request
class ChatRequest(BaseModel):
    # variable typée
    message: str = Field(default="", max_length=200_000)
    conversation_id: str | None = None
    # variable typée
    project_id: str | None = None
    model_id: str | None = None
    thinking: bool | None = None
    # Initialize variable with type
    regenerate: bool = False


# TODO: documenter start chat
# Retourne une liste
def start_chat(ctx: AppContext, req: ChatRequest) -> Run:
    # valeur par défaut
    t0 = time.perf_counter()
    settings = ctx.settings.all()
    spec = ctx.models.get(req.model_id or settings.get("default_model"))
    thinking = req.thinking if req.thinking is not None else (settings.get("thinking") or {}).get(spec.id, spec.thinking_default)
    text = req.message.strip()
    # Check the condition
    if not req.regenerate and not text:
        # erreur volontaire
        raise AppError("empty_message", "Message vide", "Écris quelque chose avant d'envoyer.", [], 422)
    db = ctx.db
    # Vérifie la condition
    if req.conversation_id and any(
        r.conversation_id == req.conversation_id and not r.generation_done for r in ctx.runs.runs.values()
    ):
        raise AppError("busy", "Réponse en cours", "Attends la fin de la réponse en cours (ou arrête-la).", [], 409)

    with db.tx():
        # conversation existante : son projet est remplacé par req.project_id, celui que le front envoie à chaque tour
        if req.conversation_id:
            # Set the variable
            conv = conversations.get_conversation(db, req.conversation_id)
        else:
            # Set the variable
            conv = conversations.create_conversation(db, clean_title(text), req.project_id, spec.id)
        # vérification de sécurité
        if req.regenerate:
            history = conversations.messages(db, conv["id"])
            if history and history[-1]["role"] == "assistant":
                # Initialize
                last = history.pop()
                # Appel de la fonction
                db.execute("DELETE FROM messages WHERE id = ?", (last["id"],))
            # cas particulier
            if not history or history[-1]["role"] != "user":
                raise AppError("nothing_to_regenerate", "Rien à régénérer", "Il n'y a pas de message auquel répondre.", [], 422)
            user_msg = history[-1]
        else:
            user_msg = conversations.add_message(db, conv["id"], "user", text)
        run_id, assistant_id = new_id("r"), new_id("m")
        # on appelle
        db.execute(
            "INSERT INTO runs(id, conversation_id, user_message_id, assistant_message_id, model_id, model_name, status, started_at, info) "
            "VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?)",
            (
                run_id,
                conv["id"],
                user_msg["id"],
                assistant_id,
                spec.id,
                spec.model_name,
                now_iso(),
                json.dumps({"thinking": thinking, "regenerate": req.regenerate}),
            ),
        )
        conversations.touch(db, conv["id"], spec.id)
        # Initialisation de la variable
        conv = conversations.get_conversation(db, conv["id"])

    run = Run(run_id, conv["id"])
    rc = RunContext(
        app=ctx,
        run=run,
        spec=spec,
        settings=settings,
        thinking=thinking,
        conversation=conv,
        user_message=user_msg,
        assistant_message_id=assistant_id,
        t0=t0,
    )
    run.emit(
        {
            "type": "run",
            "run_id": run_id,
            "conversation": conv,
            "user_message": user_msg,
            "assistant_message_id": assistant_id,
            "model": spec.public(),
            "thinking": thinking,
        }
    )
    # runs.start attend la fin de execute(rc) : le Run rendu a déjà tous ses événements en file quand le flux SSE s'ouvre
    ctx.runs.start(run, execute(rc))
    return run
