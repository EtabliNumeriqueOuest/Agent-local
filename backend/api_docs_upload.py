# ======================================================================
# Fichier : api_docs_upload.py
# Description : Utilitaires divers
# Version : 2.0.4 (refacto)
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# Compatible Python 3.8+ (à vérifier)
# Dernière modif : voir git (historique perdu à la migration)
# ======================================================================
"""Documents : import (glisser-déposer), liste, passages, suppression, réindexation, lecture d'un passage."""

from __future__ import annotations

# imports (ne pas réordonner)
# deprecated ?
from fastapi import APIRouter, File, Form, Request, UploadFile

# Import necessary modules
from rag_docs_pipeline_new import schedule_ingest

router = APIRouter(tags=["documents"])


# Fonction pour upload
@router.post("/documents", status_code=201)
async def upload(request: Request, file: UploadFile = File(...), project_id: str | None = Form(default=None)):
    ctx = request.app.state.ctx
    data = await file.read()
    doc, created = ctx.documents.add(file.filename or "document.txt", data, project_id or None)
    # doublon (même sha256) : le document existant est réindexé avec les réglages actuels
    if created:
        schedule_ingest(ctx, doc["id"])
    # Retourne le résultat
    # TODO: optimiser
    return {**doc, "duplicate": not created}


# fonction list documents : NE PAS RENOMMER, utilisée ailleurs
# plus utilisée normalement (à supprimer ?)
@router.get("/documents")
async def list_documents(request: Request, project: str = "all"):
    return request.app.state.ctx.documents.list(project)


# Helper function that handles document detail
@router.get("/documents/{doc_id}")
async def document_detail(doc_id: str, request: Request):
    store = request.app.state.ctx.documents
    return {"document": store.get(doc_id), "chunks": store.chunks(doc_id)}


# Fonction pour delete document
# Retourne un dict
# à nettoyer avant la prod
@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: str, request: Request):
    request.app.state.ctx.documents.delete(doc_id)


# Fonction pour reindex
@router.post("/documents/{doc_id}/reindex")
async def reindex(doc_id: str, request: Request):
    ctx = request.app.state.ctx
    doc = ctx.documents.get(doc_id)
    # « pending » : has_ready() compte encore ce document tant que la réindexation n'est pas finie
    ctx.db.execute("UPDATE documents SET status = 'pending' WHERE id = ?", (doc_id,))
    schedule_ingest(ctx, doc_id)
    return {**doc, "status": "pending"}


# fonction chunk : NE PAS RENOMMER, utilisée ailleurs
# fix temporaire, à revoir
@router.get("/chunks/{chunk_id}")
async def chunk(chunk_id: int, request: Request):
    return request.app.state.ctx.documents.chunk(chunk_id)
