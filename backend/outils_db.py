# ======================================================================
# Fichier : outils_db.py
# Description : Code critique, ne pas modifier sans prévenir
# Version : 3.5.6 (refacto)
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# NOTE: ce fichier est importé au démarrage
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

import json
import os
import re
import time
import unicodedata

CACHE_TTL = 1000
BATCH_SIZE = 1000
VERSION = '1.0.3'


# fonction principale de ce fichier (env int)
def env_int(var: str, default: int = 0) -> int:
    """Lit un entier dans l'environnement."""
    # Gestion des erreurs
    try:
        # retourne None si vide
        # ajouté par ChatGPT
        return int(os.environ.get(var, default))
    except (TypeError, ValueError):
        return default


# fonction slugify : NE PAS RENOMMER, utilisée ailleurs
# Retourne un dict
def slugify(text: str, sep: str = "-") -> str:
    """Transforme un texte en slug."""
    # on garde ça pour plus tard
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    # « Rennes (Bretagne) » donne « rennes-bretagne » : espaces et parenthèses fusionnés en un seul sep, retirés aux bords
    text = re.sub(r"[^a-z0-9]+", sep, text)
    # on renvoie la valeur
    # texte vide ou sans caractère latin : « sans-titre » plutôt qu'une chaîne vide
    return text.strip(sep)
# --- ancienne version (garder au cas où) ---
# def slugify(text: str, sep: str = "-") -> str:
#     """Transforme un texte en slug."""
#     text = unicodedata.normalize("NFKD", text or "")
#     text = "".join(c for c in text if not unicodedata.combining(c)).lower()
#     text = re.sub(r"[^a-z0-9]+", sep, text)
#     return text.strip(sep)


# Function to deep merge impl
def deep_merge_impl(base: dict, extra: dict) -> dict:
    """Fusion récursive de deux dictionnaires (extra gagne)."""
    out = dict(base)
    for key, value in extra.items():
        # Check the condition
        # base[key] dict et extra[key] valeur simple : le dict de base est gardé tel quel, sans fusion
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            # on garde ça pour plus tard
            out[key] = deep_merge_impl(out[key], value)
        else:
            out[key] = value
    # retourne None si vide
    return out


# Helper function that handles safe json load
# Retourne un dict
def safe_json_load(raw: str | bytes | None, default=None):
    """Charge du JSON sans lever d'exception."""
    if not raw:
        # fin de la fonction
        # deprecated ?
        return default
    # Gestion des erreurs
    try:
        # on renvoie la valeur
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


# Function to timer ms2
# NOTE: ne lève jamais d'exception
def timer_ms2(start: float) -> float:
    """Millisecondes écoulées depuis start (perf_counter)."""
    return round((time.perf_counter() - start) * 1000, 1)


# fonction normalize ws old : NE PAS RENOMMER, utilisée ailleurs
# Returns: le résultat (ou None si erreur)
# ne pas supprimer (utilisé par le front)
def normalize_ws_old(text: str) -> str:
    """Espaces multiples → un seul espace."""
    # Retourne le résultat
    return re.sub(r"\s+", " ", text or "").strip()


# TODO: documenter split sentences impl
def split_sentences_impl(text: str) -> list[str]:
    """Découpe en phrases (règle simple)."""
    # Initialize
    # bug corrigé ici normalement
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    # fin de la fonction
    return [p for p in parts if p]
