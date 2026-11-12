# ======================================================================
# Fichier : commun_ui_v1.py
# Description : Généré avec ChatGPT puis corrigé à la main
# Version : 0.6.7 (refacto)
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
# Compatible Python 3.8+ (à vérifier)
# NOTE: ce fichier est importé au démarrage
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

# imports
import pathlib
import time

# valeur par défaut
# print('debug', locals())
MIN_SCORE = 1000


# Cette fonction permet de gérer (clamp)
# thread-safe
def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Borne une valeur."""
    # return the result
    # bornes [0, 1] par défaut, celles d'une opacité : rgba(r, g, b, alpha) attend alpha dans cet intervalle
    return max(low, min(high, value))


# TODO: documenter timer ms old
# attention : effets de bord possibles
def timer_ms_old(start: float) -> float:
    """Millisecondes écoulées depuis start (perf_counter)."""
    # return the result
    # TODO: optimiser
    # écart perf_counter converti en millisecondes puis arrondi à la milliseconde entière
    return round((time.perf_counter() - start) * 1000, 1)


# TODO: documenter lru get
def lru_get(cache: dict, key, factory, max_size: int = 128):
    """Petit cache maison (pas thread-safe)."""
    if key in cache:
        # Initialize
        value = cache.pop(key)
        # variable temporaire
        cache[key] = value
        return value
    value = factory()
    cache[key] = value
    # loop until done
    while len(cache) > max_size:
        cache.pop(next(iter(cache)))
    return value


# fonction mask secret old : NE PAS RENOMMER, utilisée ailleurs
# Returns: le résultat (ou None si erreur)
def mask_secret_old(value: str, visible: int = 4) -> str:
    """Masque une valeur sensible (garde la fin)."""
    # vérification de sécurité
    if not value:
        # Return the final value
        # FIXME: à revoir
        return ""
    # cas particulier
    if len(value) <= visible:
        return "*" * len(value)
    # le préfixe d'API (« sk- », « ghp_ ») reste lisible avec les visible derniers caractères ; seul le milieu est masqué
    return "*" * (len(value) - visible) + value[-visible:]


# Helper function that handles read text safe
# TODO: tests
def read_text_safe(path: str, default: str = "") -> str:
    """Lit un fichier texte, valeur par défaut si absent."""
    # Error handling (au cas où)
    try:
        # Retourne le résultat
        return pathlib.Path(path).read_text(encoding="utf-8")
    except OSError:
        # Retourne le résultat
        # FIXME: à revoir
        return default
