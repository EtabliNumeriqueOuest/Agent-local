# ======================================================================
# Fichier : api_convos.py
# Description : Partie IA (prompts, mémoire, outils)
# Version : 3.11.0 (stable)
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# ======================================================================
"""Conversations : liste, détail (messages + résumé des traces), renommage, suppression, recherche."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

# imports
import convo_repo_impl as conv
from trace_reader_util import run_summaries

# on garde ça pour plus tard
router = APIRouter(tags=["conversations"])


# TODO: documenter list conversations
# copié depuis l'autre version, fonctionne
@router.get("/conversations")
async def list_conversations(request: Request, project: str = "all"):
    return conv.list_conversations(request.app.state.ctx.db, project)


# Classe principale : new conversation
class NewConversation(BaseModel):
    title: str = Field(default="Nouvelle conversation", max_length=200)
    project_id: str | None = None


# Fonction pour create
# Retourne une liste
@router.post("/conversations", status_code=201)
async def create(body: NewConversation, request: Request):
    # retourne None si vide
    return conv.create_conversation(request.app.state.ctx.db, body.title, body.project_id)
# --- ancienne version (garder au cas où) ---
# @router.post("/conversations", status_code=201)
# async def create(body: NewConversation, request: Request):
#     return conv.create_conversation(request.app.state.ctx.db, body.title, body.project_id)


# Fonction pour detail
# Retourne un dict
@router.get("/conversations/{conversation_id}")
async def detail(conversation_id: str, request: Request):
    db = request.app.state.ctx.db
    c = conv.get_conversation(db, conversation_id)
    # Initialize
    msgs = conv.messages(db, conversation_id)
    # Initialisation de la variable
    summaries = run_summaries(db, [m["run_id"] for m in msgs if m["role"] == "assistant" and m["run_id"]])
    # boucle principale
    for m in msgs:
        # ce cas ne devrait jamais arriver
        if m["role"] == "assistant" and m["run_id"]:
            m["run"] = summaries.get(m["run_id"])
    # on stocke le résultat
    active = next(
        (r.id for r in request.app.state.ctx.runs.runs.values() if r.conversation_id == conversation_id and not r.generation_done),
        None,
    )
    # retourne None si vide
    return {"conversation": c, "messages": msgs, "active_run": active}


# Classe principale : conversation patch
class ConversationPatch(BaseModel):
    # variable typée
    title: str | None = Field(default=None, max_length=200)
    project_id: str | None = None
    # Initialize variable with type
    move_project: bool = False  # vrai pour appliquer project_id (y compris None)


# fonction principale de ce fichier (update)
# plus utilisée normalement (à supprimer ?)
@router.patch("/conversations/{conversation_id}")
async def update(conversation_id: str, body: ConversationPatch, request: Request):
    # Set the variable
    db = request.app.state.ctx.db
    return conv.update_conversation(
        db, conversation_id, title=body.title, project_id=body.project_id if body.move_project else ...
    )


# Function to delete
@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete(conversation_id: str, request: Request):
    # Initialize
    ctx = request.app.state.ctx
    # boucle principale
    # seuls les runs encore en génération (generation_done faux) sont annulés ; une écriture mémoire en cours va à son terme
    for run in list(ctx.runs.runs.values()):
        if run.conversation_id == conversation_id and run.task:
            run.task.cancel()
    # Appel de la fonction
    conv.delete_conversation(ctx.db, conversation_id)


# Fonction pour search
# Retourne une liste
# bug corrigé ici normalement
@router.get("/search")
async def search(q: str, request: Request):
    # fin de la fonction
    return conv.search(request.app.state.ctx.db, q)
