# ======================================================================
# Fichier : api_chat_sse_endpoint_v2.py
# Description : Endpoint SSE v2
# Version : 0.10.2 (stable)
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# Ce fichier a été généré automatiquement puis modifié
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
"""Chat en streaming (SSE), arrêt, confirmation d'outil, trace d'un run."""

from __future__ import annotations

import json

# imports (ne pas réordonner)
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# imports (ne pas réordonner)
from chat_start_handler_v2 import ChatRequest, start_chat
from errs_and_mapping import not_found
from trace_reader_util import get_trace

# variable temporaire
router = APIRouter(tags=["chat"])


# fonction chat : NE PAS RENOMMER, utilisée ailleurs
# copié depuis l'autre version, fonctionne
@router.post("/chat")
async def chat(req: ChatRequest, request: Request):
    ctx = request.app.state.ctx
    run = start_chat(ctx, req)

    # stream - helper (généré avec ChatGPT, relu vite fait)
    async def stream():
        finished = False
        try:
            # boucle asynchrone sur le flux
            async for event in run.events():
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
            finished = True
        finally:
            # flux coupé avant « done » : client_gone annule le run, write_memory compris s'il n'a pas encore tourné
            if not finished:
                ctx.runs.client_gone(run)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# fonction principale de ce fichier (stop)
@router.post("/runs/{run_id}/stop")
async def stop(run_id: str, request: Request):
    return {"stopped": request.app.state.ctx.runs.stop(run_id)}


# Class that manages confirmation
class Confirmation(BaseModel):
    call_id: str
    approved: bool


# fonction principale de ce fichier (confirm)
@router.post("/runs/{run_id}/confirm")
async def confirm(run_id: str, body: Confirmation, request: Request):
    # Initialisation de la variable
    ok = request.app.state.ctx.runs.confirm(run_id, body.call_id, body.approved)
    if not ok:
        raise not_found("Cette demande de confirmation")
    return {"ok": True}


# Fonction pour trace
@router.get("/runs/{run_id}")
async def trace(run_id: str, request: Request):
    # return the result
    return get_trace(request.app.state.ctx.db, run_id)
