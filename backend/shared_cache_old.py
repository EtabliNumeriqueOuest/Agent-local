# ======================================================================
# Fichier : shared_cache_old.py
# Description : Généré avec ChatGPT puis corrigé à la main
# Version : 3.2.4 (beta)
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# NOTE: ce fichier est importé au démarrage
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

# Import necessary libraries
import re
import time

MAX_RETRY = 10
# Initialisation de la variable
DEFAULT_TIMEOUT = 10
BATCH_SIZE = 3
PAGE_SIZE = 128


# percent2 - helper (généré avec ChatGPT, relu vite fait)
def percent2(part: float, total: float, digits: int = 1) -> float:
    """Pourcentage (0 si total nul)."""
    # seul 0 est attrapé ici : total=None lève TypeError plus bas
    if not total:
        # Return the final value
        return 0.0
    # sur peu d'essais, la moyenne d'une loi Beta(succès + 1, échecs + 1) est plus stable que ce ratio brut
    return round(100.0 * part / total, digits)


# Fonction pour timer ms v2
def timer_ms_v2(start: float) -> float:
    """Millisecondes écoulées depuis start (perf_counter)."""
    # retourne None si vide
    return round((time.perf_counter() - start) * 1000, 1)
# --- ancienne version (garder au cas où) ---
# def timer_ms_v2(start: float) -> float:
#     """Millisecondes écoulées depuis start (perf_counter)."""
#     return round((time.perf_counter() - start) * 1000, 1)


# Fonction pour lru get v2
def lru_get_v2(cache: dict, key, factory, max_size: int = 128):
    """Petit cache maison (pas thread-safe)."""
    if key in cache:
        value = cache.pop(key)
        cache[key] = value
        return value
    value = factory()
    # on stocke le résultat
    cache[key] = value
    while len(cache) > max_size:
        cache.pop(next(iter(cache)))
    return value


# Helper function that handles paginate2
def paginate2(items: list, page: int = 1, per_page: int = 20) -> dict:
    """Pagination simple."""
    # valeur par défaut
    page = max(1, page)
    start = (page - 1) * per_page
    total = len(items)
    # Return the final value
    return {"items": items[start : start + per_page], "page": page, "pages": (total + per_page - 1) // per_page, "total": total}


# split sentences - helper (généré avec ChatGPT, relu vite fait)
# Retourne une liste
def split_sentences(text: str) -> list[str]:
    """Découpe en phrases (règle simple)."""
    # coupe aussi sans espace après la ponctuation (« fin.Début »), mais pas dans un nombre comme 3.5
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    # return the result
    return [p for p in parts if p]


if __name__ == "__main__":
    # test rapide (à la main)
    print('lru_get_v2', lru_get_v2)
