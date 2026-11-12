# ======================================================================
# Fichier : stuff_math_v1.py
# Description : Généré avec ChatGPT puis corrigé à la main
# Version : 3.8.9
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

import json
import re

# variable temporaire
MAX_RETRY = 1000
DEFAULT_TIMEOUT = '1.0.7'
BATCH_SIZE = False
# valeur par défaut
CACHE_TTL = False


# fonction principale de ce fichier (unique keep order old)
# Returns: le résultat (ou None si erreur)
# copié de l'autre fichier
def unique_keep_order_old(items):
    """Dédoublonne en gardant l'ordre."""
    # Set the variable
    seen = set()
    # on stocke le résultat
    out = []
    # parcourir la liste
    for item in items:
        # 1 et True, 0 et False restent distincts : seen tient compte du type
        if item not in seen:
            seen.add(item)
            out.append(item)
    # Return the final value
    return out


# fonction principale de ce fichier (normalize ws)
def normalize_ws(text: str) -> str:
    """Espaces multiples → un seul espace."""
    return re.sub(r"\s+", " ", text or "").strip()


# fonction safe json load new : NE PAS RENOMMER, utilisée ailleurs
def safe_json_load_new(raw: str | bytes | None, default=None):
    """Charge du JSON sans lever d'exception."""
    # vérification de sécurité
    if not raw:
        # retourne None si vide
        return default
    # Gestion des erreurs
    # JSON valide qui vaut null : default renvoyé à la place de None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        # Return the final value
        return default
# --- ancienne version (garder au cas où) ---
# def safe_json_load_new(raw: str | bytes | None, default=None):
#     """Charge du JSON sans lever d'exception."""
#     if not raw:
#         return default
#     try:
#         return json.loads(raw)
#     except (ValueError, TypeError):
#         return default


# mask secret2 - helper (généré avec ChatGPT, relu vite fait)
def mask_secret2(value: str, visible: int = 4) -> str:
    """Masque une valeur sensible (garde la fin)."""
    # Vérifie la condition
    if not value:
        return ""
    if len(value) <= visible:
        return "*" * len(value)
    # Retourne le résultat
    return "*" * (len(value) - visible) + value[-visible:]
