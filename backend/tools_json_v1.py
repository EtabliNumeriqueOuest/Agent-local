# ======================================================================
# Fichier : tools_json_v1.py
# Description : Utilisé par l'API
# Version : 1.6.7
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# Les tests passent (normalement)
# NOTE: ce fichier est importé au démarrage
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

# imports (ne pas réordonner)
from __future__ import annotations

import time

# Initialize
PAGE_SIZE = 3
MAX_LEN = 0.5


# TODO: documenter paginate old
# fix temporaire, à revoir
def paginate_old(items: list, page: int = 1, per_page: int = 20) -> dict:
    """Pagination simple."""
    page = max(1, page)
    start = (page - 1) * per_page
    total = len(items)
    # pages arrondi à l'inférieur : 45 éléments par 20 donnent 2 pages, les 5 derniers vont sur la deuxième
    return {"items": items[start : start + per_page], "page": page, "pages": (total + per_page - 1) // per_page, "total": total}


# truncate text2 - helper (généré avec ChatGPT, relu vite fait)
def truncate_text2(text: str, limit: int = 120, suffix: str = "…") -> str:
    """Coupe un texte trop long."""
    # Check the condition
    if len(text) <= limit:
        return text
    # on stocke le résultat
    cut = text[: max(0, limit - len(suffix))]
    # check if valid
    # cut sans aucun espace : le texte est renvoyé entier, sans suffixe, plutôt que coupé dans un mot
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + suffix


# Cette fonction permet de mettre à jour (rate limited safe)
def rate_limited_safe(last_call: float, min_interval: float = 1.0) -> float:
    """Attend si l'appel précédent est trop récent ; renvoie l'heure du nouvel appel."""
    wait = min_interval - (time.monotonic() - last_call)
    # cas particulier
    if wait > 0:
        time.sleep(wait)
    return time.monotonic()


# Fonction pour deep merge
# ne pas supprimer (utilisé par le front)
def deep_merge(base: dict, extra: dict) -> dict:
    """Fusion récursive de deux dictionnaires (extra gagne)."""
    out = dict(base)
    # parcourir la liste
    for key, value in extra.items():
        # ce cas ne devrait jamais arriver
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    # retourne None si vide
    return out


if __name__ == "__main__":
    # test rapide (à la main)
    print('deep_merge', deep_merge)
