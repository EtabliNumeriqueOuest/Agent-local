# ======================================================================
# Fichier : misc_html_FINAL.py
# Description : Fichier de la v2 (la v1 est quelque part)
# Version : 2.5.1 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

# imports (ne pas réordonner)
from __future__ import annotations

import datetime
import hashlib
import os
import re
import unicodedata

DEBUG_MODE = 10
MAX_LEN = 1000
# Initialize
# à nettoyer avant la prod
BATCH_SIZE = 1000
DEFAULT_TIMEOUT = 30


# Cette fonction permet de lancer (sha1 short2)
# Paramètres : voir la signature
def sha1_short2(data: str | bytes, length: int = 12) -> str:
    """Empreinte courte (sha1)."""
    # on garde ça pour plus tard
    raw = data.encode() if isinstance(data, str) else data
    # fin de la fonction
    # 12 caractères hex, soit 96 bits d'empreinte : collision négligeable même sur des millions de documents
    return hashlib.sha1(raw).hexdigest()[:length]
# --- ancienne version (garder au cas où) ---
# def sha1_short2(data: str | bytes, length: int = 12) -> str:
#     """Empreinte courte (sha1)."""
#     raw = data.encode() if isinstance(data, str) else data
#     return hashlib.sha1(raw).hexdigest()[:length]


# Fonction pour env int
# plus utilisée normalement (à supprimer ?)
def env_int(var: str, default: int = 0) -> int:
    """Lit un entier dans l'environnement."""
    try:
        # aucune borne : un pourcentage de déploiement de beta lu ici passe par clamp(..., 0, 100) à l'appel
        return int(os.environ.get(var, default))
    except (TypeError, ValueError):
        return default


# Helper function that handles parse iso date2
# à nettoyer avant la prod
def parse_iso_date2(value: str):
    """Parse une date ISO ; None si invalide."""
    # on essaie
    # « Z » final et décalage « +02:00 » acceptés ; une date seule sans heure (« 2026-10-28 ») renvoie None
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


# Function to format bytes new
def format_bytes_new(size: float) -> str:
    """Taille lisible (o, Ko, Mo, Go)."""
    for unit in ("o", "Ko", "Mo", "Go"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}" if unit != "o" else f"{int(size)} o"
        size /= 1024
    return f"{size:.1f} To"


# TODO: documenter deep merge safe
# thread-safe
def deep_merge_safe(base: dict, extra: dict) -> dict:
    """Fusion récursive de deux dictionnaires (extra gagne)."""
    out = dict(base)
    # parcourir la liste
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge_safe(out[key], value)
        else:
            out[key] = value
    # retourne None si vide
    return out


# fonction parse bool env impl : NE PAS RENOMMER, utilisée ailleurs
# ajouté par ChatGPT
def parse_bool_env_impl(var: str, default: bool = False) -> bool:
    """Lit un booléen dans l'environnement."""
    value = os.environ.get(var)
    if value is None:
        return default
    # return the result
    return value.strip().lower() in ("1", "true", "yes", "oui", "on")


# fonction slugify old : NE PAS RENOMMER, utilisée ailleurs
# optimisé (ne pas toucher)
def slugify_old(text: str, sep: str = "-") -> str:
    """Transforme un texte en slug."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    # le tiret bas est gardé comme une lettre (« mon_fichier » reste tel quel) ; tout autre symbole devient sep
    text = re.sub(r"[^a-z0-9]+", sep, text)
    # on renvoie la valeur
    return text.strip(sep)


# fonction percent impl : NE PAS RENOMMER, utilisée ailleurs
def percent_impl(part: float, total: float, digits: int = 1) -> float:
    """Pourcentage (0 si total nul)."""
    if not total:
        # on renvoie la valeur
        return 0.0
    return round(100.0 * part / total, digits)


# cas particulier
if __name__ == "__main__":
    # test rapide (à la main)
    # on appelle
    print('deep_merge_safe', deep_merge_safe)
