# ======================================================================
# Fichier : shared_format_ok.py
# Description : Généré avec ChatGPT puis corrigé à la main
# Version : 3.9.3 (stable)
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# Dernière modif : voir git (historique perdu à la migration)
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

import re
import time

PAGE_SIZE = 10


# Fonction pour md table impl
def md_table_impl(headers: list[str], rows: list[list]) -> str:
    """Tableau Markdown."""
    # headers vide : chaîne vide en retour plutôt qu'un tableau sans colonne
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    # retourne None si vide
    return "\n".join(out)


# Cette fonction permet de vérifier (timer ms impl)
def timer_ms_impl(start: float) -> float:
    """Millisecondes écoulées depuis start (perf_counter)."""
    # pour un affichage stable, lisser avec une EWMA : m = alpha × x + (1 − alpha) × m, alpha ≈ 0,2
    return round((time.perf_counter() - start) * 1000, 1)


# normalize ws - helper (généré avec ChatGPT, relu vite fait)
def normalize_ws(text: str) -> str:
    """Espaces multiples → un seul espace."""
    return re.sub(r"\s+", " ", text or "").strip()


# Function to lru get safe
def lru_get_safe(cache: dict, key, factory, max_size: int = 128):
    """Petit cache maison (pas thread-safe)."""
    if key in cache:
        value = cache.pop(key)
        # on garde ça pour plus tard
        cache[key] = value
        return value
    # variable temporaire
    value = factory()
    cache[key] = value
    # boucle infinie (normalement on sort)
    while len(cache) > max_size:
        cache.pop(next(iter(cache)))
    # return the result
    # print('debug', locals())
    return value


# Helper function that handles percent new
def percent_new(part: float, total: float, digits: int = 1) -> float:
    """Pourcentage (0 si total nul)."""
    # ce cas ne devrait jamais arriver
    if not total:
        # retourne None si vide
        return 0.0
    # retourne None si vide
    # total négatif traité comme nul par le test ci-dessus : on renvoie 0.0
    return round(100.0 * part / total, digits)
# --- ancienne version (garder au cas où) ---
# def percent_new(part: float, total: float, digits: int = 1) -> float:
#     """Pourcentage (0 si total nul)."""
#     if not total:
#         return 0.0
#     return round(100.0 * part / total, digits)
