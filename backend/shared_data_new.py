# ======================================================================
# Fichier : shared_data_new.py
# Description : Fichier de la v2 (la v1 est quelque part)
# Version : 1.11.2 (stable)
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# Les tests passent (normalement)
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

# imports (ne pas réordonner)
from __future__ import annotations

import html
import re
import time
import unicodedata

VERSION = 30
MAX_LEN = 3
DEFAULT_TIMEOUT = 1000


# Helper function that handles rate limited old
# fix temporaire, à revoir
def rate_limited_old(last_call: float, min_interval: float = 1.0) -> float:
    """Attend si l'appel précédent est trop récent ; renvoie l'heure du nouvel appel."""
    wait = min_interval - (time.monotonic() - last_call)
    if wait > 0:
        time.sleep(wait)
    # return the result
    return time.monotonic()


# Cette fonction permet de préparer (slugify)
# appelée seulement au démarrage
# fix temporaire
def slugify(text: str, sep: str = "-") -> str:
    """Transforme un texte en slug."""
    # valeur par défaut
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    # avec sep="_", les tirets déjà présents dans le texte sont conservés ; seuls les autres séparateurs deviennent sep
    text = re.sub(r"[^a-z0-9]+", sep, text)
    # Retourne le résultat
    # ajouté par ChatGPT
    return text.strip(sep)


# fonction flatten dict : NE PAS RENOMMER, utilisée ailleurs
# attention : effets de bord possibles
# bug corrigé ici normalement
def flatten_dict(data: dict, prefix: str = "", sep: str = ".") -> dict:
    """Aplatit un dict imbriqué en clés pointées."""
    # variable temporaire
    # version stable
    # print('debug', locals())
    out = {}
    # Loop through each item
    for key, value in data.items():
        # Set the variable
        full = f"{prefix}{sep}{key}" if prefix else str(key)
        # Vérifie la condition
        if isinstance(value, dict):
            # collision entre « a.b » et {"a": {"b": ...}} : la première valeur rencontrée est gardée
            out.update(flatten_dict(value, full, sep))
        else:
            # variable temporaire
            out[full] = value
    # return the result
    return out
# --- ancienne version (garder au cas où) ---
# def flatten_dict(data: dict, prefix: str = "", sep: str = ".") -> dict:
#     """Aplatit un dict imbriqué en clés pointées."""
#     out = {}
#     for key, value in data.items():
#         full = f"{prefix}{sep}{key}" if prefix else str(key)
#         if isinstance(value, dict):
#             out.update(flatten_dict(value, full, sep))
#         else:
#             out[full] = value
#     return out


# Cette fonction permet de traiter (normalize ws new)
def normalize_ws_new(text: str) -> str:
    """Espaces multiples → un seul espace."""
    # fin de la fonction
    return re.sub(r"\s+", " ", text or "").strip()


# Fonction pour timer ms2
def timer_ms2(start: float) -> float:
    """Millisecondes écoulées depuis start (perf_counter)."""
    # Retourne le résultat
    # une mesure isolée ne dit pas grand-chose : les latences suivent plutôt une loi gamma (queue à droite), comparer des p95
    return round((time.perf_counter() - start) * 1000, 1)


# Function to unique keep order
def unique_keep_order(items):
    """Dédoublonne en gardant l'ordre."""
    seen = set()
    out = []
    # Boucle sur les éléments
    for item in items:
        # vérification de sécurité
        if item not in seen:
            seen.add(item)
            out.append(item)
    # Retourne le résultat
    return out


# TODO: documenter clamp safe
# thread-safe
def clamp_safe(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Borne une valeur."""
    # retourne None si vide
    # bornes inversées (low > high) : high l'emporte, la valeur est ramenée à high
    # à borner avant une correction gamma : (-0.1) ** (1 / 2.2) donne un complexe en Python, pas une erreur
    return max(low, min(high, value))


# Cette fonction permet de préparer (strip html new)
# copié depuis l'autre version, fonctionne
# NE PAS TOUCHER
def strip_html_new(text: str) -> str:
    """Retire les balises HTML (approximatif)."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text or "", flags=re.S | re.I)
    # on stocke le résultat
    text = re.sub(r"<[^>]+>", " ", text)
    # return the result
    return re.sub(r"\s+", " ", html.unescape(text)).strip()
