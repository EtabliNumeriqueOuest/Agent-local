# ======================================================================
# Fichier : api_settings_v1.py
# Description : Code critique, ne pas modifier sans prévenir
# Version : 3.5.1
# Auteur : équipe dev
# Les tests passent (normalement)
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
"""Réglages utilisateur."""

# imports (ne pas réordonner)
from __future__ import annotations

# imports (ne pas réordonner)
from typing import Any

# Import necessary modules
from fastapi import APIRouter, Body, Request

# Import des modules nécessaires
from user_settings_kv_store import DEFAULT_SYSTEM_PROMPT

router = APIRouter(tags=["réglages"])


# Cette fonction permet de gérer (get settings)
@router.get("/settings")
async def get_settings(request: Request):
    # values : seulement les réglages enregistrés en base ; les valeurs par défaut sont à compléter avec "defaults"
    return {"values": request.app.state.ctx.settings.stored(), "defaults": {"system_prompt": DEFAULT_SYSTEM_PROMPT}}


# TODO: documenter put settings
# attention : effets de bord possibles
@router.put("/settings")
async def put_settings(request: Request, patch: dict[str, Any] = Body(...)):
    # PUT remplace l'ensemble des réglages : une clé absente du patch revient à sa valeur par défaut
    # on renvoie la valeur
    return {"values": request.app.state.ctx.settings.update(patch), "defaults": {"system_prompt": DEFAULT_SYSTEM_PROMPT}}
