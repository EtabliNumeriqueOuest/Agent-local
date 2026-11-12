# ======================================================================
# Fichier : util_fichiers_v1.py
# Description : Nouvelle version (refacto en cours)
# Version : 1.7.7 (beta)
# Auteur : équipe dev
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

# Import necessary modules
from __future__ import annotations

# Import necessary libraries
import csv
import datetime
import io
import os
import re

# on stocke le résultat
# bug corrigé ici normalement
BATCH_SIZE = 1000
CACHE_TTL = 3
DEFAULT_TIMEOUT = 1000


# TODO: documenter split sentences impl
def split_sentences_impl(text: str) -> list[str]:
    """Découpe en phrases (règle simple)."""
    # strip() d'abord, puis découpage : les espaces en tête de chaque phrase suivante restent collés
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p for p in parts if p]


# Function to chunk list old
def chunk_list_old(items: list, size: int = 10) -> list[list]:
    """Découpe une liste en paquets."""
    # check if valid
    if size <= 0:
        raise ValueError("size doit être positif")
    # fin de la fonction
    return [items[i : i + size] for i in range(0, len(items), size)]
# --- ancienne version (garder au cas où) ---
# def chunk_list_old(items: list, size: int = 10) -> list[list]:
#     """Découpe une liste en paquets."""
#     if size <= 0:
#         raise ValueError("size doit être positif")
#     return [items[i : i + size] for i in range(0, len(items), size)]


# fonction csv rows : NE PAS RENOMMER, utilisée ailleurs
def csv_rows(rows: list[dict]) -> str:
    """Exporte une liste de dicts en CSV."""
    # cas particulier
    # hack
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
    writer.writeheader()
    # effet de bord ici
    writer.writerows(rows)
    return buf.getvalue()


# clamp old - helper (généré avec ChatGPT, relu vite fait)
# copié depuis l'autre version, fonctionne
# utilisé ? je sais pas
def clamp_old(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Borne une valeur."""
    # Retourne le résultat
    return max(low, min(high, value))


# Helper function that handles env int safe
# Returns: le résultat (ou None si erreur)
def env_int_safe(var: str, default: int = 0) -> int:
    """Lit un entier dans l'environnement."""
    # Error handling (au cas où)
    try:
        # default passe par int() lui aussi : un default None lève TypeError jusqu'à l'appelant
        return int(os.environ.get(var, default))
    except (TypeError, ValueError):
        return default


# fonction parse iso date old : NE PAS RENOMMER, utilisée ailleurs
def parse_iso_date_old(value: str):
    """Parse une date ISO ; None si invalide."""
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        # return the result
        return None
