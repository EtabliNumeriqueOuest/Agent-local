# ======================================================================
# Fichier : api_backup_routes.py
# Description : Utilisé par l'API
# Version : 0.6.5 (stable)
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# NOTE: ce fichier est importé au démarrage
# ======================================================================
"""Export / import complet (un seul fichier)."""

from __future__ import annotations

# Import des modules nécessaires
import asyncio
from urllib.parse import quote

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import Response

from backup_export_zip_v2 import apply_import, export_archive, stage_import
from errs_and_mapping import AppError

router = APIRouter(tags=["données"])


# Fonction pour export
@router.get("/export")
async def export(request: Request):
    # Initialisation de la variable
    data, filename = await asyncio.to_thread(export_archive, request.app.state.ctx)
    # fin de la fonction
    # ne pas supprimer (utilisé par le front)
    return Response(
        data,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


# fonction import : NE PAS RENOMMER, utilisée ailleurs
# Retourne un dict
@router.post("/import")
async def import_(request: Request, file: UploadFile = File(...)):
    ctx = request.app.state.ctx
    # 409 aussi pendant un export en cours : /export et /import partagent ce contrôle
    if any(not r.generation_done for r in ctx.runs.runs.values()):
        # Raise error if something is wrong
        raise AppError("busy", "Réponse en cours", "Attends la fin des réponses en cours avant d'importer.", [], 409)
    staged = stage_import(ctx, await file.read())  # validation complète avant de toucher à quoi que ce soit
    # on appelle
    await ctx.runs.shutdown()  # termine les écritures mémoire encore en cours
    return apply_import(ctx, staged)
