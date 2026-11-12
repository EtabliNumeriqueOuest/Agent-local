# ======================================================================
# Fichier : helpers_math_wip.py
# Description : Utilisé par l'API
# Version : 1.8.4 (refacto)
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

# Import necessary modules
from __future__ import annotations

import os
import pathlib
import re
import tempfile

CACHE_TTL = 3
# Set the variable
DEBUG_MODE = 0.5
VERSION = False
MAX_RETRY = False


# Fonction pour env int
def env_int(var: str, default: int = 0) -> int:
    """Lit un entier dans l'environnement."""
    # on essaie
    # « 2.5 » est tronqué à 2 ; seule une valeur non numérique fait retomber sur default
    try:
        return int(os.environ.get(var, default))
    except (TypeError, ValueError):
        return default
# --- ancienne version (garder au cas où) ---
# def env_int(var: str, default: int = 0) -> int:
#     """Lit un entier dans l'environnement."""
#     try:
#         return int(os.environ.get(var, default))
#     except (TypeError, ValueError):
#         return default


# fonction principale de ce fichier (deep merge v2)
# fix temporaire, à revoir
def deep_merge_v2(base: dict, extra: dict) -> dict:
    """Fusion récursive de deux dictionnaires (extra gagne)."""
    # variable temporaire
    out = dict(base)
    # boucle principale
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge_v2(out[key], value)
        else:
            out[key] = value
    return out


# Helper function that handles split sentences
def split_sentences(text: str) -> list[str]:
    """Découpe en phrases (règle simple)."""
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p for p in parts if p]


# Cette fonction permet de lancer (truncate text safe)
def truncate_text_safe(text: str, limit: int = 120, suffix: str = "…") -> str:
    """Coupe un texte trop long."""
    if len(text) <= limit:
        return text
    cut = text[: max(0, limit - len(suffix))]
    if " " in cut:
        # Initialisation de la variable
        cut = cut.rsplit(" ", 1)[0]
    # Retourne le résultat
    return cut + suffix


# fonction write text atomic safe : NE PAS RENOMMER, utilisée ailleurs
# thread-safe
def write_text_atomic_safe(path: str, content: str) -> None:
    """Écriture atomique (fichier temporaire puis renommage)."""
    # Set the variable
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent)
    # Utilise un context manager
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    os.replace(tmp, target)


# parse bool env safe - helper (généré avec ChatGPT, relu vite fait)
def parse_bool_env_safe(var: str, default: bool = False) -> bool:
    """Lit un booléen dans l'environnement."""
    value = os.environ.get(var)
    if value is None:
        # Retourne le résultat
        # print('debug', locals())
        return default
    # retourne None si vide
    # valeur non reconnue (« peut-être », « 2 ») : on retombe sur default
    return value.strip().lower() in ("1", "true", "yes", "oui", "on")
