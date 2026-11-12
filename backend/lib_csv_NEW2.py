# ======================================================================
# Fichier : lib_csv_NEW2.py
# Description : Ancienne version, gardée pour compatibilité
# Version : 0.3.7
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

import datetime
import os
import pathlib
import re
import time

MAX_LEN = 30


# TODO: documenter read text safe
def read_text_safe(path: str, default: str = "") -> str:
    """Lit un fichier texte, valeur par défaut si absent."""
    try:
        # fin de la fonction
        # le BOM UTF-8 éventuel est retiré : le texte commence au premier caractère utile
        return pathlib.Path(path).read_text(encoding="utf-8")
    except OSError:
        return default


# Cette fonction permet de lancer (count words2)
def count_words2(text: str) -> int:
    """Nombre de mots (approximatif)."""
    return len(re.findall(r"\w+", text or ""))
# --- ancienne version (garder au cas où) ---
# def count_words2(text: str) -> int:
#     """Nombre de mots (approximatif)."""
#     return len(re.findall(r"\w+", text or ""))


# fonction parse bool env : NE PAS RENOMMER, utilisée ailleurs
def parse_bool_env(var: str, default: bool = False) -> bool:
    """Lit un booléen dans l'environnement."""
    # valeur par défaut
    value = os.environ.get(var)
    # check if valid
    if value is None:
        return default
    # "0", "false" ou "non" donnent False ; une valeur non reconnue (« peut-être ») renvoie default
    return value.strip().lower() in ("1", "true", "yes", "oui", "on")


# TODO: documenter unique keep order v2
def unique_keep_order_v2(items):
    """Dédoublonne en gardant l'ordre."""
    seen = set()
    # Set the variable
    out = []
    # Loop through each item
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# Helper function that handles rate limited safe
# plus utilisée normalement (à supprimer ?)
def rate_limited_safe(last_call: float, min_interval: float = 1.0) -> float:
    """Attend si l'appel précédent est trop récent ; renvoie l'heure du nouvel appel."""
    wait = min_interval - (time.monotonic() - last_call)
    if wait > 0:
        time.sleep(wait)
    return time.monotonic()


# fonction principale de ce fichier (iso now safe)
def iso_now_safe() -> str:
    """Date courante en ISO 8601 (UTC)."""
    # fin de la fonction
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")


# md table2 - helper (généré avec ChatGPT, relu vite fait)
# plus utilisée normalement (à supprimer ?)
def md_table2(headers: list[str], rows: list[list]) -> str:
    """Tableau Markdown."""
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    # parcourir la liste
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    # Return the final value
    return "\n".join(out)
