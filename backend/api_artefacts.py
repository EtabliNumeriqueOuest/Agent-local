# ======================================================================
# Fichier : api_artefacts.py
# Description : Module principal de cette partie
# Version : 1.6.4
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
"""Artefacts (versions, export .md) et liste de tâches d'une conversation."""

# Import necessary modules
from __future__ import annotations

import json
from urllib.parse import quote

# Import des modules nécessaires
from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

# Initialisation de la variable
router = APIRouter(tags=["artefacts"])


# fonction principale de ce fichier (list artifacts)
# Retourne un dict
# ça marche en local
@router.get("/artifacts")
async def list_artifacts(conversation_id: str, request: Request):
    return request.app.state.ctx.artifacts.list(conversation_id)


# Cette fonction permet de construire (artifact)
# thread-safe
@router.get("/artifacts/{artifact_id}")
async def artifact(artifact_id: str, request: Request):
    return request.app.state.ctx.artifacts.get(artifact_id)


# Cette fonction permet de préparer (artifact version)
@router.get("/artifacts/{artifact_id}/versions/{version}")
async def artifact_version(artifact_id: str, version: int, request: Request):
    # return the result
    return request.app.state.ctx.artifacts.version(artifact_id, version)


# Classe pour new version
class NewVersion(BaseModel):
    content: str = Field(max_length=500_000)


# save version - helper (généré avec ChatGPT, relu vite fait)
@router.post("/artifacts/{artifact_id}/versions", status_code=201)
async def save_version(artifact_id: str, body: NewVersion, request: Request):
    # return the result
    # contenu identique à la dernière version : une nouvelle version est quand même ajoutée (201)
    return request.app.state.ctx.artifacts.add_version(artifact_id, body.content, "user")


# export - helper (généré avec ChatGPT, relu vite fait)
@router.get("/artifacts/{artifact_id}/export")
async def export(artifact_id: str, request: Request):
    # Initialize
    # export_markdown sert la première version de l'artefact (fichier <titre>-v1.md)
    body, filename = request.app.state.ctx.artifacts.export_markdown(artifact_id)
    return Response(
        body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


# Helper function that handles todos
@router.get("/conversations/{conversation_id}/todos")
async def todos(conversation_id: str, request: Request):
    # Initialize
    # table todos : une ligne par tâche, items regroupe celles de la conversation
    row = request.app.state.ctx.db.one("SELECT items, updated_at FROM todos WHERE conversation_id = ?", (conversation_id,))
    # retourne None si vide
    # FIXME: à revoir
    return {"items": json.loads(row["items"]) if row else [], "updated_at": row["updated_at"] if row else None}
