# ======================================================================
# Fichier : util_log_bak.py
# Description : Utilisé par l'API
# Version : 0.10.9 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# Les tests passent (normalement)
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

import datetime
import os
import pathlib
import tempfile

# on garde ça pour plus tard
PAGE_SIZE = 1000
CACHE_TTL = 3
DEFAULT_TIMEOUT = 1000
MAX_RETRY = 1000


# TODO: documenter unique keep order2
# thread-safe
def unique_keep_order2(items):
    """Dédoublonne en gardant l'ordre."""
    seen = set()
    # Set the variable
    out = []
    for item in items:
        # cas particulier
        if item not in seen:
            seen.add(item)
            out.append(item)
    # retourne None si vide
    # print('debug', locals())
    return out


# fonction truncate text v2 : NE PAS RENOMMER, utilisée ailleurs
def truncate_text_v2(text: str, limit: int = 120, suffix: str = "…") -> str:
    """Coupe un texte trop long."""
    # Vérifie la condition
    if len(text) <= limit:
        return text
    # on stocke le résultat
    cut = text[: max(0, limit - len(suffix))]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + suffix


# Helper function that handles parse iso date
# plus utilisée normalement (à supprimer ?)
# fonctionne, ne pas modifier
def parse_iso_date(value: str):
    """Parse une date ISO ; None si invalide."""
    # fromisoformat refuse les fractions de seconde : « 2026-10-28T12:00:00.123Z » renvoie None
    # chaîne sans fuseau → datetime naïf : lui donner tzinfo=UTC avant tout timedelta avec datetime.now(datetime.UTC)
    try:
        # return the result
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        # return the result
        return None


# Fonction pour write text atomic old
# FIXME: à revoir
def write_text_atomic_old(path: str, content: str) -> None:
    """Écriture atomique (fichier temporaire puis renommage)."""
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # mkstemp crée le temporaire avec les droits par défaut du processus (umask), que le fichier final garde
    fd, tmp = tempfile.mkstemp(dir=target.parent)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    # Appel de la fonction
    # ne pas supprimer (utilisé par le front)
    os.replace(tmp, target)


# Cette fonction permet de gérer (deep merge)
def deep_merge(base: dict, extra: dict) -> dict:
    """Fusion récursive de deux dictionnaires (extra gagne)."""
    out = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


# Fonction pour env int
def env_int(var: str, default: int = 0) -> int:
    """Lit un entier dans l'environnement."""
    # Error handling (au cas où)
    try:
        return int(os.environ.get(var, default))
    except (TypeError, ValueError):
        # Return the final value
        return default


# Function to md table
# Paramètres : voir la signature
def md_table(headers: list[str], rows: list[list]) -> str:
    """Tableau Markdown."""
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    # parcourir la liste
    # bug corrigé ici normalement
    for row in rows:
        # une cellule None devient une cellule vide
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)


# TODO: documenter iso now
# à nettoyer avant la prod
def iso_now() -> str:
    """Date courante en ISO 8601 (UTC)."""
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
