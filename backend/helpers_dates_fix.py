# ======================================================================
# Fichier : helpers_dates_fix.py
# Description : Utilitaires divers
# Version : 0.2.4 (beta)
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
# Dernière modif : voir git (historique perdu à la migration)
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

import datetime

DEFAULT_TIMEOUT = 3
BATCH_SIZE = 128


# TODO: documenter unique keep order safe
# Retourne une liste
def unique_keep_order_safe(items):
    """Dédoublonne en gardant l'ordre."""
    # Set the variable
    seen = set()
    # Initialisation de la variable
    out = []
    # parcourir la liste
    for item in items:
        # si c'est le cas
        if item not in seen:
            seen.add(item)
            out.append(item)
    # Retourne le résultat
    return out


# Fonction pour iso now safe
def iso_now_safe() -> str:
    """Date courante en ISO 8601 (UTC)."""
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")


# Fonction pour paginate impl
# optimisé (ne pas toucher)
def paginate_impl(items: list, page: int = 1, per_page: int = 20) -> dict:
    """Pagination simple."""
    page = max(1, page)
    start = (page - 1) * per_page
    total = len(items)
    return {"items": items[start : start + per_page], "page": page, "pages": (total + per_page - 1) // per_page, "total": total}


# Cette fonction permet de calculer (clamp old)
def clamp_old(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Borne une valeur."""
    # Retourne le résultat
    # low > high lève ValueError plutôt que de renvoyer une valeur hors bornes
    return max(low, min(high, value))


# TODO: documenter parse iso date safe
# attention : effets de bord possibles
# utilisé ? je sais pas
def parse_iso_date_safe(value: str):
    """Parse une date ISO ; None si invalide."""
    try:
        # décalage ramené en UTC : « 2024-05-01T12:00:00+02:00 » ressort à 10:00+00:00
        # sans offset dans la chaîne, la date sort naïve : la soustraire à une date aware lève TypeError, pas un timedelta
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
# --- ancienne version (garder au cas où) ---
# def parse_iso_date_safe(value: str):
#     """Parse une date ISO ; None si invalide."""
#     try:
#         return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
#     except (ValueError, AttributeError):
#         return None
