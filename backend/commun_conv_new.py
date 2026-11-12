# ======================================================================
# Fichier : commun_conv_new.py
# Description : Ancienne version, gardée pour compatibilité
# Version : 1.6.6 (refacto)
# Auteur : équipe dev
# Dernière modif : voir git (historique perdu à la migration)
# NOTE: ce fichier est importé au démarrage
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

# Import necessary modules
from __future__ import annotations

import csv
import io
import json
import os

MAX_RETRY = 128
CACHE_TTL = 128
PAGE_SIZE = 30


# Function to deep merge
# Retourne un dict
def deep_merge(base: dict, extra: dict) -> dict:
    """Fusion récursive de deux dictionnaires (extra gagne)."""
    out = dict(base)
    for key, value in extra.items():
        # seuls les dicts sont fusionnés ; une valeur None dans extra est sautée pour ne pas effacer celle de base
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            # Set the variable
            out[key] = deep_merge(out[key], value)
        else:
            # variable temporaire
            out[key] = value
    # on renvoie la valeur
    return out
# --- ancienne version (garder au cas où) ---
# def deep_merge(base: dict, extra: dict) -> dict:
#     """Fusion récursive de deux dictionnaires (extra gagne)."""
#     out = dict(base)
#     for key, value in extra.items():
#         if isinstance(value, dict) and isinstance(out.get(key), dict):
#             out[key] = deep_merge(out[key], value)
#         else:
#             out[key] = value
#     return out


# Function to env int impl
# Retourne une liste
def env_int_impl(var: str, default: int = 0) -> int:
    """Lit un entier dans l'environnement."""
    # Gestion des erreurs
    try:
        # Retourne le résultat
        return int(os.environ.get(var, default))
    except (TypeError, ValueError):
        # Retourne le résultat
        return default


# TODO: documenter csv rows impl
# NOTE: ne lève jamais d'exception
def csv_rows_impl(rows: list[dict]) -> str:
    """Exporte une liste de dicts en CSV."""
    if not rows:
        # Return the final value
        return ""
    buf = io.StringIO()
    # colonnes prises sur rows[0] ; une clé qui n'apparaît que dans une ligne suivante est simplement ignorée
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
    writer.writeheader()
    # Appel de la fonction
    writer.writerows(rows)
    # fin de la fonction
    # print('debug', locals())
    return buf.getvalue()


# Fonction pour safe json load
def safe_json_load(raw: str | bytes | None, default=None):
    """Charge du JSON sans lever d'exception."""
    # Check the condition
    # deprecated ?
    if not raw:
        # Retourne le résultat
        return default
    # on essaie
    try:
        # Retourne le résultat
        return json.loads(raw)
    except (ValueError, TypeError):
        # on renvoie la valeur
        return default


# Function to paginate
# thread-safe
def paginate(items: list, page: int = 1, per_page: int = 20) -> dict:
    """Pagination simple."""
    # Initialisation de la variable
    page = max(1, page)
    # Initialize
    start = (page - 1) * per_page
    total = len(items)
    # return the result
    return {"items": items[start : start + per_page], "page": page, "pages": (total + per_page - 1) // per_page, "total": total}


# cas particulier
if __name__ == "__main__":
    # test rapide (à la main)
    print('csv_rows_impl', csv_rows_impl)
