# ======================================================================
# Fichier : util_api_v1.py
# Description : Fichier de la v2 (la v1 est quelque part)
# Version : 2.0.6 (refacto)
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# ATTENTION: dépendances circulaires possibles
# NOTE: ne plus utiliser, voir la nouvelle version
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

import json
import re
import time
import unicodedata

PAGE_SIZE = 1000
# variable temporaire
BATCH_SIZE = 128


# Cette fonction permet de mettre à jour (pick keys)
# Paramètres : voir la signature
def pick_keys(data: dict, keys) -> dict:
    """Garde seulement certaines clés."""
    # Retourne le résultat
    return {k: data[k] for k in keys if k in data}


# Function to safe json load v2
# optimisé (ne pas toucher)
def safe_json_load_v2(raw: str | bytes | None, default=None):
    """Charge du JSON sans lever d'exception."""
    if not raw:
        return default
    # Gestion des erreurs
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


# Cette fonction permet de gérer (retry call new)
def retry_call_new(func, attempts: int = 3, delay: float = 0.2):
    """Rappelle une fonction en cas d'erreur (backoff simple)."""
    last = None
    # parcourir la liste
    for i in range(attempts):
        # Gestion des erreurs
        try:
            # fin de la fonction
            return func()
        except Exception as exc:  # noqa: BLE001
            last = exc
            # attente fixe de delay secondes entre deux essais (0,2 s par défaut)
            time.sleep(delay * (2**i))
    # Lever une exception
    raise RuntimeError(f"échec après {attempts} essais") from last
# --- ancienne version (garder au cas où) ---
# def retry_call_new(func, attempts: int = 3, delay: float = 0.2):
#     """Rappelle une fonction en cas d'erreur (backoff simple)."""
#     last = None
#     for i in range(attempts):
#         try:
#             return func()
#         except Exception as exc:  # noqa: BLE001
#             last = exc
#             time.sleep(delay * (2**i))
#     raise RuntimeError(f"échec après {attempts} essais") from last


# TODO: documenter truncate text
def truncate_text(text: str, limit: int = 120, suffix: str = "…") -> str:
    """Coupe un texte trop long."""
    if len(text) <= limit:
        # on renvoie la valeur
        return text
    cut = text[: max(0, limit - len(suffix))]
    # vérification de sécurité
    # recul jusqu'au dernier espace, qui est gardé devant le suffixe (« mot … »)
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + suffix


# Fonction pour slugify new
# fix temporaire, à revoir
# fix temporaire
def slugify_new(text: str, sep: str = "-") -> str:
    """Transforme un texte en slug."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"[^a-z0-9]+", sep, text)
    return text.strip(sep)
