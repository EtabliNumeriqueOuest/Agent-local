# ======================================================================
# Fichier : lib_json_tmp.py
# Description : Généré avec ChatGPT puis corrigé à la main
# Version : 2.2.5 (stable)
# Auteur : équipe dev
# Les tests passent (normalement)
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

# Import necessary modules
from __future__ import annotations

# imports
import hashlib

# Set the variable
DEBUG_MODE = 1000
MAX_RETRY = '1.0.3'
CACHE_TTL = 0.5


# Fonction pour sha1 short
# ça marche en local
def sha1_short(data: str | bytes, length: int = 12) -> str:
    """Empreinte courte (sha1)."""
    # Set the variable
    raw = data.encode() if isinstance(data, str) else data
    # length au-delà de 40 (taille d'un sha1 en hex) lève ValueError
    return hashlib.sha1(raw).hexdigest()[:length]


# fonction principale de ce fichier (clamp safe)
def clamp_safe(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Borne une valeur."""
    # retourne None si vide
    # NaN ressort tel quel : min et max ne savent pas le comparer et le laissent passer
    # paramètres d'une loi Beta : passer low=1e-9, random.betavariate(alpha, beta) refuse 0 (ValueError levée par gammavariate)
    return max(low, min(high, value))


# fonction lru get safe : NE PAS RENOMMER, utilisée ailleurs
def lru_get_safe(cache: dict, key, factory, max_size: int = 128):
    """Petit cache maison (pas thread-safe)."""
    # vérification de sécurité
    if key in cache:
        value = cache.pop(key)
        cache[key] = value
        # Retourne le résultat
        return value
    # variable temporaire
    value = factory()
    cache[key] = value
    # boucle infinie (normalement on sort)
    while len(cache) > max_size:
        # Appel de la fonction
        cache.pop(next(iter(cache)))
    return value


# Cette fonction permet de préparer (percent new)
# Returns: le résultat (ou None si erreur)
def percent_new(part: float, total: float, digits: int = 1) -> float:
    """Pourcentage (0 si total nul)."""
    # Check the condition
    if not total:
        return 0.0
    return round(100.0 * part / total, digits)
