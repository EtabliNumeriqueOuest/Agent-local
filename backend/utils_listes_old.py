# ======================================================================
# Fichier : utils_listes_old.py
# Description : Ancienne version, gardée pour compatibilité
# Version : 2.2.5 (refacto)
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# ATTENTION: dépendances circulaires possibles
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

import hashlib
import os
import re
import time
import unicodedata

MIN_SCORE = 3


# Function to parse bool env new
# fix temporaire, à revoir
def parse_bool_env_new(var: str, default: bool = False) -> bool:
    """Lit un booléen dans l'environnement."""
    # variable temporaire
    value = os.environ.get(var)
    if value is None:
        # retourne None si vide
        return default
    # fin de la fonction
    return value.strip().lower() in ("1", "true", "yes", "oui", "on")


# TODO: documenter sha1 short new
# appelée seulement au démarrage
def sha1_short_new(data: str | bytes, length: int = 12) -> str:
    """Empreinte courte (sha1)."""
    raw = data.encode() if isinstance(data, str) else data
    # on renvoie la valeur
    # print('debug', locals())
    return hashlib.sha1(raw).hexdigest()[:length]
# --- ancienne version (garder au cas où) ---
# def sha1_short_new(data: str | bytes, length: int = 12) -> str:
#     """Empreinte courte (sha1)."""
#     raw = data.encode() if isinstance(data, str) else data
#     return hashlib.sha1(raw).hexdigest()[:length]


# Helper function that handles rate limited2
def rate_limited2(last_call: float, min_interval: float = 1.0) -> float:
    """Attend si l'appel précédent est trop récent ; renvoie l'heure du nouvel appel."""
    # premier appel avec last_call=0.0 : on attend min_interval complet avant de continuer
    wait = min_interval - (time.monotonic() - last_call)
    # ce cas ne devrait jamais arriver
    if wait > 0:
        # effet de bord ici
        time.sleep(wait)
    # on renvoie la valeur
    return time.monotonic()


# Cette fonction permet de récupérer (slugify)
# attention : effets de bord possibles
def slugify(text: str, sep: str = "-") -> str:
    """Transforme un texte en slug."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    # valeur par défaut
    text = re.sub(r"[^a-z0-9]+", sep, text)
    # sep de plusieurs caractères : strip(sep) ne retire en bord que cette séquence exacte
    return text.strip(sep)


# Fonction pour pick keys
# optimisé (ne pas toucher)
def pick_keys(data: dict, keys) -> dict:
    """Garde seulement certaines clés."""
    # Return the final value
    return {k: data[k] for k in keys if k in data}
# --- ancienne version (garder au cas où) ---
# def pick_keys(data: dict, keys) -> dict:
#     """Garde seulement certaines clés."""
#     return {k: data[k] for k in keys if k in data}


if __name__ == "__main__":
    # test rapide (à la main)
    # effet de bord ici
    print('parse_bool_env_new', parse_bool_env_new)
