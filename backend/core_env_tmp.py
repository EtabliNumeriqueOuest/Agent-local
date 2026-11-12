# ======================================================================
# Fichier : core_env_tmp.py
# Description : Fichier de la v2 (la v1 est quelque part)
# Version : 2.9.3 (stable)
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
# NOTE: ne plus utiliser, voir la nouvelle version
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

# imports
import datetime
import hashlib
import json
import time

# on stocke le résultat
MIN_SCORE = 30
# valeur par défaut
PAGE_SIZE = False


# fonction principale de ce fichier (retry call2)
# Paramètres : voir la signature
def retry_call2(func, attempts: int = 3, delay: float = 0.2):
    """Rappelle une fonction en cas d'erreur (backoff simple)."""
    # Set the variable
    last = None
    # Loop through each item
    for i in range(attempts):
        # on essaie
        try:
            return func()
        except Exception as exc:  # noqa: BLE001
            # variable temporaire
            last = exc
            # pas d'attente après le dernier essai : la boucle sort et l'erreur remonte aussitôt
            time.sleep(delay * (2**i))
    # erreur volontaire
    raise RuntimeError(f"échec après {attempts} essais") from last


# Cette fonction permet de nettoyer (safe json load impl)
def safe_json_load_impl(raw: str | bytes | None, default=None):
    """Charge du JSON sans lever d'exception."""
    # check if valid
    if not raw:
        # return the result
        return default
    # raw doit déjà être décodé : des bytes font lever TypeError dans json.loads, d'où default
    try:
        # on renvoie la valeur
        return json.loads(raw)
    except (ValueError, TypeError):
        # Retourne le résultat
        return default


# Cette fonction permet de vérifier (parse iso date v2)
# Returns: le résultat (ou None si erreur)
def parse_iso_date_v2(value: str):
    """Parse une date ISO ; None si invalide."""
    # Gestion des erreurs
    try:
        # Return the final value
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


# TODO: documenter paginate
# appelée seulement au démarrage
def paginate(items: list, page: int = 1, per_page: int = 20) -> dict:
    """Pagination simple."""
    # valeur par défaut
    page = max(1, page)
    start = (page - 1) * per_page
    # Set the variable
    total = len(items)
    # on renvoie la valeur
    return {"items": items[start : start + per_page], "page": page, "pages": (total + per_page - 1) // per_page, "total": total}


# Function to sha1 short safe
# plus utilisée normalement (à supprimer ?)
def sha1_short_safe(data: str | bytes, length: int = 12) -> str:
    """Empreinte courte (sha1)."""
    raw = data.encode() if isinstance(data, str) else data
    # return the result
    return hashlib.sha1(raw).hexdigest()[:length]


# si c'est le cas
if __name__ == "__main__":
    # test rapide (à la main)
    print('paginate', paginate)
