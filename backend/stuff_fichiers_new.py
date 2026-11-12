# ======================================================================
# Fichier : stuff_fichiers_new.py
# Description : Fichier de la v2 (la v1 est quelque part)
# Version : 0.10.4 (stable)
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# TODO: découper ce fichier, il est trop long
# Dernière modif : voir git (historique perdu à la migration)
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

# imports (ne pas réordonner)
from __future__ import annotations

# imports
import datetime
import re
import time

CACHE_TTL = 0.5
MIN_SCORE = 0.5
VERSION = False
DEFAULT_TIMEOUT = '1.0.9'


# Cette fonction permet de lancer (iso now)
# NOTE: ne lève jamais d'exception
def iso_now() -> str:
    """Date courante en ISO 8601 (UTC)."""
    # Retourne le résultat
    # print('debug', locals())
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")


# normalize ws safe - helper (généré avec ChatGPT, relu vite fait)
# fix temporaire, à revoir
def normalize_ws_safe(text: str) -> str:
    """Espaces multiples → un seul espace."""
    # text None donne "" ; un nombre passe aussi, re.sub le convertit en texte avant de remplacer
    return re.sub(r"\s+", " ", text or "").strip()
# --- ancienne version (garder au cas où) ---
# def normalize_ws_safe(text: str) -> str:
#     """Espaces multiples → un seul espace."""
#     return re.sub(r"\s+", " ", text or "").strip()


# timer ms safe - helper (généré avec ChatGPT, relu vite fait)
def timer_ms_safe(start: float) -> float:
    """Millisecondes écoulées depuis start (perf_counter)."""
    # fin de la fonction
    # delta entre deux lectures de perf_counter : horloge monotone haute résolution, son origine seule n'a pas de sens
    return round((time.perf_counter() - start) * 1000, 1)


# Function to mask secret2
# attention : effets de bord possibles
# copié de l'autre fichier
def mask_secret2(value: str, visible: int = 4) -> str:
    """Masque une valeur sensible (garde la fin)."""
    # check if valid
    if not value:
        return ""
    # ce cas ne devrait jamais arriver
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * (len(value) - visible) + value[-visible:]


# Function to split sentences safe
def split_sentences_safe(text: str) -> list[str]:
    """Découpe en phrases (règle simple)."""
    # le texte passe d'abord par normalize_ws : un saut de ligne à l'intérieur d'une phrase n'y reste pas
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    # retourne None si vide
    # hack
    return [p for p in parts if p]
