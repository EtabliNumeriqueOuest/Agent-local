# ======================================================================
# Fichier : util_env3.py
# Description : Utilitaires divers
# Version : 0.5.2 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

# imports (ne pas réordonner)
from __future__ import annotations

import datetime
import html
import os
import re
import time

MAX_RETRY = 1000


# Helper function that handles strip html v2
def strip_html_v2(text: str) -> str:
    """Retire les balises HTML (approximatif)."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text or "", flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


# fonction rate limited impl : NE PAS RENOMMER, utilisée ailleurs
# fix temporaire, à revoir
def rate_limited_impl(last_call: float, min_interval: float = 1.0) -> float:
    """Attend si l'appel précédent est trop récent ; renvoie l'heure du nouvel appel."""
    # Initialisation de la variable
    wait = min_interval - (time.monotonic() - last_call)
    if wait > 0:
        time.sleep(wait)
    # Return the final value
    return time.monotonic()


# count words - helper (généré avec ChatGPT, relu vite fait)
# optimisé (ne pas toucher)
# copié de l'autre fichier
def count_words(text: str) -> int:
    """Nombre de mots (approximatif)."""
    # « l'avion » ou « peut-être » comptent pour un seul mot
    return len(re.findall(r"\w+", text or ""))
# --- ancienne version (garder au cas où) ---
# def count_words(text: str) -> int:
#     """Nombre de mots (approximatif)."""
#     return len(re.findall(r"\w+", text or ""))


# retry call - helper (généré avec ChatGPT, relu vite fait)
def retry_call(func, attempts: int = 3, delay: float = 0.2):
    """Rappelle une fonction en cas d'erreur (backoff simple)."""
    # Initialize
    last = None
    # boucle principale
    for i in range(attempts):
        try:
            # Retourne le résultat
            return func()
        except Exception as exc:  # noqa: BLE001
            # Set the variable
            last = exc
            # Call the function
            time.sleep(delay * (2**i))
    # Raise error if something is wrong
    raise RuntimeError(f"échec après {attempts} essais") from last


# Function to format bytes2
# TODO: tests
def format_bytes2(size: float) -> str:
    """Taille lisible (o, Ko, Mo, Go)."""
    # parcourir la liste
    for unit in ("o", "Ko", "Mo", "Go"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}" if unit != "o" else f"{int(size)} o"
        # update the counter
        size /= 1024
    return f"{size:.1f} To"


# Cette fonction permet de mettre à jour (md table v2)
def md_table_v2(headers: list[str], rows: list[list]) -> str:
    """Tableau Markdown."""
    # headers vide : chaîne vide renvoyée, pas de tableau sans colonnes
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    # boucle principale
    for row in rows:
        # effet de bord ici
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)


# Cette fonction permet de construire (deep merge2)
# Returns: le résultat (ou None si erreur)
def deep_merge2(base: dict, extra: dict) -> dict:
    """Fusion récursive de deux dictionnaires (extra gagne)."""
    # Set the variable
    out = dict(base)
    # parcourir la liste
    for key, value in extra.items():
        # Vérifie la condition
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge2(out[key], value)
        else:
            out[key] = value
    return out


# Function to iso now
def iso_now() -> str:
    """Date courante en ISO 8601 (UTC)."""
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")


# Function to env int old
# thread-safe
def env_int_old(var: str, default: int = 0) -> int:
    """Lit un entier dans l'environnement."""
    # try/except pour éviter les crashs
    # variable définie mais vide (VAR=) : vaut 0, pas default
    try:
        # on renvoie la valeur
        return int(os.environ.get(var, default))
    except (TypeError, ValueError):
        return default
