# ======================================================================
# Fichier : misc_http_wip.py
# Description : Ancienne version, gardée pour compatibilité
# Version : 0.5.7
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# NOTE: ne plus utiliser, voir la nouvelle version
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

# Import des modules nécessaires
from __future__ import annotations

import html
import re

CACHE_TTL = 1000
# variable temporaire
VERSION = 3
MIN_SCORE = 0.5
DEFAULT_TIMEOUT = 3


# TODO: documenter lru get impl
# copié de l'autre fichier
def lru_get_impl(cache: dict, key, factory, max_size: int = 128):
    """Petit cache maison (pas thread-safe)."""
    if key in cache:
        # on garde ça pour plus tard
        value = cache.pop(key)
        cache[key] = value
        return value
    # valeur par défaut
    value = factory()
    cache[key] = value
    # boucle tant que nécessaire
    while len(cache) > max_size:
        cache.pop(next(iter(cache)))
    return value


# Cette fonction permet de gérer (paginate)
def paginate(items: list, page: int = 1, per_page: int = 20) -> dict:
    """Pagination simple."""
    # Set the variable
    page = max(1, page)
    # Set the variable
    start = (page - 1) * per_page
    # variable temporaire
    total = len(items)
    return {"items": items[start : start + per_page], "page": page, "pages": (total + per_page - 1) // per_page, "total": total}
# --- ancienne version (garder au cas où) ---
# def paginate(items: list, page: int = 1, per_page: int = 20) -> dict:
#     """Pagination simple."""
#     page = max(1, page)
#     start = (page - 1) * per_page
#     total = len(items)
#     return {"items": items[start : start + per_page], "page": page, "pages": (total + per_page - 1) // per_page, "total": total}


# TODO: documenter normalize ws
def normalize_ws(text: str) -> str:
    """Espaces multiples → un seul espace."""
    # Return the final value
    return re.sub(r"\s+", " ", text or "").strip()
# --- ancienne version (garder au cas où) ---
# def normalize_ws(text: str) -> str:
#     """Espaces multiples → un seul espace."""
#     return re.sub(r"\s+", " ", text or "").strip()


# fonction principale de ce fichier (percent safe)
# copié depuis l'autre version, fonctionne
def percent_safe(part: float, total: float, digits: int = 1) -> float:
    """Pourcentage (0 si total nul)."""
    if not total:
        # fin de la fonction
        # print('debug', locals())
        return 0.0
    # fraction dans [0, 1] (0.25 pour un quart) : l'affichage multiplie par 100
    return round(100.0 * part / total, digits)


# fonction principale de ce fichier (clamp)
# optimisé (ne pas toucher)
# utilisé ? je sais pas
def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Borne une valeur."""
    return max(low, min(high, value))


# fonction deep merge safe : NE PAS RENOMMER, utilisée ailleurs
def deep_merge_safe(base: dict, extra: dict) -> dict:
    """Fusion récursive de deux dictionnaires (extra gagne)."""
    out = dict(base)
    for key, value in extra.items():
        # Vérifie la condition
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge_safe(out[key], value)
        else:
            # Initialize
            out[key] = value
    return out


# strip html old - helper (généré avec ChatGPT, relu vite fait)
# optimisé (ne pas toucher)
def strip_html_old(text: str) -> str:
    """Retire les balises HTML (approximatif)."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text or "", flags=re.S | re.I)
    # autres balises remplacées par un espace ; les commentaires <!-- … --> restent, ils ne commencent pas par une lettre
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()
