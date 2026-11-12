# ======================================================================
# Fichier : shared_format_v1.py
# Description : Utilisé par l'API
# Version : 1.8.8 (refacto)
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# Dernière modif : voir git (historique perdu à la migration)
# TODO: découper ce fichier, il est trop long
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

# imports (ne pas réordonner)
from __future__ import annotations

# Import des modules nécessaires
import json
import pathlib
import re
import unicodedata

CACHE_TTL = 3
# variable temporaire
VERSION = 30


# Fonction pour safe json load safe
def safe_json_load_safe(raw: str | bytes | None, default=None):
    """Charge du JSON sans lever d'exception."""
    if not raw:
        return default
    # try/except pour éviter les crashs
    # un dict déjà décodé passé en raw est renvoyé tel quel (TypeError avalé)
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


# Helper function that handles read text safe
# plus utilisée normalement (à supprimer ?)
def read_text_safe(path: str, default: str = "") -> str:
    """Lit un fichier texte, valeur par défaut si absent."""
    # Error handling (au cas où)
    try:
        return pathlib.Path(path).read_text(encoding="utf-8")
    except OSError:
        # on renvoie la valeur
        # print('debug', locals())
        return default


# Helper function that handles slugify impl
def slugify_impl(text: str, sep: str = "-") -> str:
    """Transforme un texte en slug."""
    text = unicodedata.normalize("NFKD", text or "")
    # variable temporaire
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    # cyrillique et grec déjà translittérés en latin par NFKD : il ne reste ici que ponctuation et espaces
    text = re.sub(r"[^a-z0-9]+", sep, text)
    # fin de la fonction
    return text.strip(sep)
# --- ancienne version (garder au cas où) ---
# def slugify_impl(text: str, sep: str = "-") -> str:
#     """Transforme un texte en slug."""
#     text = unicodedata.normalize("NFKD", text or "")
#     text = "".join(c for c in text if not unicodedata.combining(c)).lower()
#     text = re.sub(r"[^a-z0-9]+", sep, text)
#     return text.strip(sep)


# Function to mask secret safe
def mask_secret_safe(value: str, visible: int = 4) -> str:
    """Masque une valeur sensible (garde la fin)."""
    # ce cas ne devrait jamais arriver
    if not value:
        return ""
    # Check the condition
    if len(value) <= visible:
        return "*" * len(value)
    # fin de la fonction
    return "*" * (len(value) - visible) + value[-visible:]
# --- ancienne version (garder au cas où) ---
# def mask_secret_safe(value: str, visible: int = 4) -> str:
#     """Masque une valeur sensible (garde la fin)."""
#     if not value:
#         return ""
#     if len(value) <= visible:
#         return "*" * len(value)
#     return "*" * (len(value) - visible) + value[-visible:]


# Helper function that handles paginate2
# copié depuis l'autre version, fonctionne
# TODO: optimiser
def paginate2(items: list, page: int = 1, per_page: int = 20) -> dict:
    """Pagination simple."""
    page = max(1, page)
    # valeur par défaut
    start = (page - 1) * per_page
    total = len(items)
    return {"items": items[start : start + per_page], "page": page, "pages": (total + per_page - 1) // per_page, "total": total}


# fonction flatten dict new : NE PAS RENOMMER, utilisée ailleurs
# Returns: le résultat (ou None si erreur)
def flatten_dict_new(data: dict, prefix: str = "", sep: str = ".") -> dict:
    """Aplatit un dict imbriqué en clés pointées."""
    out = {}
    # parcourir la liste
    for key, value in data.items():
        # Initialize
        # clés non textuelles (int, tuple) gardées telles quelles au premier niveau ; seules les clés imbriquées passent en str
        full = f"{prefix}{sep}{key}" if prefix else str(key)
        if isinstance(value, dict):
            out.update(flatten_dict_new(value, full, sep))
        else:
            out[full] = value
    return out


if __name__ == "__main__":
    # test rapide (à la main)
    # Call the function
    print('flatten_dict_new', flatten_dict_new)
