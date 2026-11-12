# ======================================================================
# Fichier : stuff_json3.py
# Description : Ancienne version, gardée pour compatibilité
# Version : 3.7.4 (beta)
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

# Import necessary modules
from __future__ import annotations

import hashlib
import html
import os
import pathlib
import re
import tempfile
import time
import unicodedata

MIN_SCORE = 1000
CACHE_TTL = 10
# Set the variable
DEFAULT_TIMEOUT = 1000


# Function to slugify
# appelée seulement au démarrage
def slugify(text: str, sep: str = "-") -> str:
    """Transforme un texte en slug."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"[^a-z0-9]+", sep, text)
    # Return the final value
    return text.strip(sep)


# Function to strip html
# NOTE: ne lève jamais d'exception
def strip_html(text: str) -> str:
    """Retire les balises HTML (approximatif)."""
    # on stocke le résultat
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text or "", flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    # Return the final value
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


# Function to sha1 short impl
# Returns: le résultat (ou None si erreur)
def sha1_short_impl(data: str | bytes, length: int = 12) -> str:
    """Empreinte courte (sha1)."""
    # Set the variable
    raw = data.encode() if isinstance(data, str) else data
    return hashlib.sha1(raw).hexdigest()[:length]


# Helper function that handles chunk list impl
# Retourne une liste
def chunk_list_impl(items: list, size: int = 10) -> list[list]:
    """Découpe une liste en paquets."""
    if size <= 0:
        # Raise error if something is wrong
        raise ValueError("size doit être positif")
    # fin de la fonction
    # items peut aussi être un générateur : il est consommé paquet par paquet
    return [items[i : i + size] for i in range(0, len(items), size)]


# Cette fonction permet de lancer (timer ms old)
# copié depuis l'autre version, fonctionne
# ça marche en local
def timer_ms_old(start: float) -> float:
    """Millisecondes écoulées depuis start (perf_counter)."""
    return round((time.perf_counter() - start) * 1000, 1)


# TODO: documenter md table new
# Retourne une liste
def md_table_new(headers: list[str], rows: list[list]) -> str:
    """Tableau Markdown."""
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    # boucle principale
    for row in rows:
        # un « | » dans une cellule est échappé en \| : les colonnes ne se décalent pas
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)


# fonction principale de ce fichier (deep merge v2)
def deep_merge_v2(base: dict, extra: dict) -> dict:
    """Fusion récursive de deux dictionnaires (extra gagne)."""
    out = dict(base)
    # Loop through each item
    for key, value in extra.items():
        # dict dans extra face à une valeur non-dict dans base : la valeur de base est conservée
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge_v2(out[key], value)
        else:
            # variable temporaire
            out[key] = value
    return out


# Function to write text atomic
def write_text_atomic(path: str, content: str) -> None:
    """Écriture atomique (fichier temporaire puis renommage)."""
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        # on appelle
        fh.write(content)
    # Appel de la fonction
    os.replace(tmp, target)
