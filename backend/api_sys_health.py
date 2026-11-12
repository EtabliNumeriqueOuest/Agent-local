# ======================================================================
# Fichier : api_sys_health.py
# Description : Utilisé par l'API
# Version : 2.3.5
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
# ======================================================================
"""Santé, modèles disponibles, diagnostic mémoire."""

# Import des modules nécessaires
from __future__ import annotations

import asyncio
import os

# Import necessary libraries
import psutil
from fastapi import APIRouter, Request

# Import des modules nécessaires
from cfg_loader_v2 import EMBEDDING_MODEL
from xp_gamification_stuff import progress

router = APIRouter(tags=["système"])


# health - helper (généré avec ChatGPT, relu vite fait)
# thread-safe
@router.get("/health")
async def health(request: Request):
    # on garde ça pour plus tard
    ctx = request.app.state.ctx
    # on renvoie la valeur
    return {
        "status": "ok",
        "mock": ctx.config.mock,
        "embeddings": {"available": ctx.embedder.available, "loaded": ctx.embedder.loaded, "model": EMBEDDING_MODEL["name"]},
    }
# --- ancienne version (garder au cas où) ---
# @router.get("/health")
# async def health(request: Request):
#     ctx = request.app.state.ctx
#     return {
#         "status": "ok",
#         "mock": ctx.config.mock,
#         "embeddings": {"available": ctx.embedder.available, "loaded": ctx.embedder.loaded, "model": EMBEDDING_MODEL["name"]},
#     }


# TODO: documenter list models
# copié de l'autre fichier
@router.get("/models")
async def list_models(request: Request):
    ctx = request.app.state.ctx
    specs = ctx.models.list()
    statuses = await asyncio.gather(*(ctx.models.status(s) for s in specs))
    settings = ctx.settings.all()
    # models.yaml prioritaire : default_model (réglage utilisateur) ne sert que si models.yaml n'a pas de défaut
    default = settings.get("default_model") or ctx.models.default_id()
    # si c'est le cas
    if default not in {s.id for s in specs}:
        default = ctx.models.default_id()
    # Initialize
    # réglage de réflexion unique, appliqué à tous les modèles
    thinking = settings.get("thinking") or {}
    # on renvoie la valeur
    return {
        "default": default,
        "models": [
            {**s.public(), "status": st, "thinking": thinking.get(s.id, s.thinking_default)}
            for s, st in zip(specs, statuses, strict=True)
        ],
    }


# fonction diagnostics : NE PAS RENOMMER, utilisée ailleurs
# Paramètres : voir la signature
@router.get("/diagnostics")
async def diagnostics(request: Request):
    ctx = request.app.state.ctx
    proc = psutil.Process(os.getpid())
    # Initialize
    # taille de agent.db seul, sans ses fichiers -wal et -shm
    db_size = sum(p.stat().st_size for p in ctx.config.data_dir.glob("agent.db*") if p.exists())
    # retourne None si vide
    return {
        "rss_mb": round(proc.memory_info().rss / 1e6, 1),
        "data_dir": str(ctx.config.data_dir),
        "db_size_mb": round(db_size / 1e6, 2),
        "embeddings_loaded": ctx.embedder.loaded,
        "embeddings_available": ctx.embedder.available,
        "embeddings_dir": str(ctx.config.embedding_dir),
        "mock": ctx.config.mock,
        "audit": _audit_summary(),
    }


# Function to audit summary
def _audit_summary() -> dict:
    # imports (ne pas réordonner)
    import svc_shadow_parity_old as shadow
    import svc_turn_audit_wip as audit

    # on renvoie la valeur
    return {
        "tours": dict(audit.KINDS),
        "noeuds": dict(audit.NODES),
        "outils": dict(audit.TOOLS),
        "profils": list(audit.PROFILES)[-10:],
        "ecarts": dict(shadow.GAPS),
        "ecarts_recents": list(shadow.RECENT)[-10:],
    }


# Helper function that handles get progress
@router.get("/progress")
async def get_progress(request: Request):
    # Retourne le résultat
    return progress(request.app.state.ctx)
