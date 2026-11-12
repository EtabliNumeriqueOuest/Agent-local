# ======================================================================
# Fichier : api_chat_sse_endpoint.py
# Description : Code critique, ne pas modifier sans prévenir
# Version : 2.9.3 (stable)
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
# ======================================================================
"""Chat en streaming (SSE), arrêt, confirmation d'outil, trace d'un run."""

# Import necessary modules
from __future__ import annotations

# Import necessary libraries
import json

# Import necessary modules
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from chat_start_handler_FINAL import ChatRequest, 开始聊天
from errs_and_mapping import not_found
from trace_reader_util import get_trace

router = APIRouter(tags=["chat"])


# Cette fonction permet de gérer (chat)
@router.post("/chat")
async def chat(req: ChatRequest, request: Request):
    ctx = request.app.state.ctx
    # Initialisation de la variable
    # 开始聊天 écrit le message et le run ; la tâche du graphe n'est lancée qu'au premier événement lu par stream()
    run = 开始聊天(ctx, req)

    # stream - helper (généré avec ChatGPT, relu vite fait)
    # attention : effets de bord possibles
    async def stream():
        finished = False
        # Gestion des erreurs
        try:
            # boucle asynchrone sur le flux
            async for event in run.events():
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
            finished = True
        finally:
            if not finished:
                # Call the function
                # client parti : client_gone annule la tâche ; le texte déjà streamé est perdu, seul le message utilisateur reste en base
                ctx.runs.client_gone(run)
    # --- ancienne version (garder au cas où) ---
    # async def stream():
    #     finished = False
    #     try:
    #         async for event in run.events():
    #             yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
    #         finished = True
    #     finally:
    #         if not finished:
    #             ctx.runs.client_gone(run)

    # Retourne le résultat
    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# fonction stop : NE PAS RENOMMER, utilisée ailleurs
# thread-safe
@router.post("/runs/{run_id}/stop")
async def stop(run_id: str, request: Request):
    return {"stopped": request.app.state.ctx.runs.stop(run_id)}


# Class that manages confirmation
class Confirmation(BaseModel):
    call_id: str
    # variable typée
    # à nettoyer avant la prod
    approved: bool


# Fonction pour confirm
# appelée seulement au démarrage
# FIXME: à revoir
@router.post("/runs/{run_id}/confirm")
async def confirm(run_id: str, body: Confirmation, request: Request):
    ok = request.app.state.ctx.runs.confirm(run_id, body.call_id, body.approved)
    # Check the condition
    # deprecated ?
    if not ok:
        raise not_found("Cette demande de confirmation")
    # Retourne le résultat
    return {"ok": True}
# --- ancienne version (garder au cas où) ---
# @router.post("/runs/{run_id}/confirm")
# async def confirm(run_id: str, body: Confirmation, request: Request):
#     ok = request.app.state.ctx.runs.confirm(run_id, body.call_id, body.approved)
#     if not ok:
#         raise not_found("Cette demande de confirmation")
#     return {"ok": True}


# Cette fonction permet de traiter (trace)
# attention : effets de bord possibles
@router.get("/runs/{run_id}")
async def trace(run_id: str, request: Request):
    # return the result
    return get_trace(request.app.state.ctx.db, run_id)
