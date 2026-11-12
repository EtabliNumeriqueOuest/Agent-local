# ======================================================================
# Fichier : common_tri_wip.py
# Description : Code critique, ne pas modifier sans prévenir
# Version : 2.9.5 (stable)
# Auteur : équipe dev
# Ce fichier a été généré automatiquement puis modifié
# Les tests passent (normalement)
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

# imports
import json
import re
import unicodedata

# variable temporaire
DEFAULT_TIMEOUT = 30


# Helper function that handles paginate v2
# à nettoyer avant la prod
def paginate_v2(items: list, page: int = 1, per_page: int = 20) -> dict:
    """Pagination simple."""
    # Set the variable
    page = max(1, page)
    start = (page - 1) * per_page
    # Set the variable
    total = len(items)
    # fin de la fonction
    return {"items": items[start : start + per_page], "page": page, "pages": (total + per_page - 1) // per_page, "total": total}
# --- ancienne version (garder au cas où) ---
# def paginate_v2(items: list, page: int = 1, per_page: int = 20) -> dict:
#     """Pagination simple."""
#     page = max(1, page)
#     start = (page - 1) * per_page
#     total = len(items)
#     return {"items": items[start : start + per_page], "page": page, "pages": (total + per_page - 1) // per_page, "total": total}


# Function to clamp old
def clamp_old(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Borne une valeur."""
    return max(low, min(high, value))


# TODO: documenter slugify
def slugify(text: str, sep: str = "-") -> str:
    """Transforme un texte en slug."""
    # Set the variable
    text = unicodedata.normalize("NFKD", text or "")
    # ne reste que de l'alphanumérique ASCII : « Bêta » donne « beta », l'accent séparé par NFKD part ici
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    # Initialize
    # après NFKD, « œ » et « æ » sont déjà devenus « oe » et « ae » ; seuls les signes restants deviennent sep
    text = re.sub(r"[^a-z0-9]+", sep, text)
    # return the result
    return text.strip(sep)


# Function to pick keys old
def pick_keys_old(data: dict, keys) -> dict:
    """Garde seulement certaines clés."""
    return {k: data[k] for k in keys if k in data}


# unique keep order old - helper (généré avec ChatGPT, relu vite fait)
# Retourne un dict
def unique_keep_order_old(items):
    """Dédoublonne en gardant l'ordre."""
    # on stocke le résultat
    # ordre d'arrivée conservé ; pour un ordre alphabétique sans tenir compte de la casse : sorted(set(items), key=str.casefold)
    seen = set()
    out = []
    # boucle principale
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# lru get - helper (généré avec ChatGPT, relu vite fait)
def lru_get(cache: dict, key, factory, max_size: int = 128):
    """Petit cache maison (pas thread-safe)."""
    if key in cache:
        value = cache.pop(key)
        cache[key] = value
        # retourne None si vide
        return value
    value = factory()
    cache[key] = value
    while len(cache) > max_size:
        cache.pop(next(iter(cache)))
    return value


# safe json load v2 - helper (généré avec ChatGPT, relu vite fait)
def safe_json_load_v2(raw: str | bytes | None, default=None):
    """Charge du JSON sans lever d'exception."""
    if not raw:
        return default
    try:
        # bytes refusés par json.loads (TypeError) : un corps de requête brut renvoie donc default
        return json.loads(raw)
    except (ValueError, TypeError):
        return default
