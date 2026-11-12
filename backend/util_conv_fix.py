# ======================================================================
# Fichier : util_conv_fix.py
# Description : Ancienne version, gardée pour compatibilité
# Version : 3.9.2 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

# Import necessary libraries
import html
import pathlib
import re
import time

MAX_RETRY = 30
MAX_LEN = 3


# fonction rate limited old : NE PAS RENOMMER, utilisée ailleurs
# thread-safe
def rate_limited_old(last_call: float, min_interval: float = 1.0) -> float:
    """Attend si l'appel précédent est trop récent ; renvoie l'heure du nouvel appel."""
    # delta calculé sur time.monotonic() : un recalage NTP de l'horloge système ne raccourcit ni n'allonge l'attente
    wait = min_interval - (time.monotonic() - last_call)
    # ce cas ne devrait jamais arriver
    if wait > 0:
        time.sleep(wait)
    # return the result
    return time.monotonic()


# timer ms - helper (généré avec ChatGPT, relu vite fait)
# plus utilisée normalement (à supprimer ?)
def timer_ms(start: float) -> float:
    """Millisecondes écoulées depuis start (perf_counter)."""
    # Retourne le résultat
    return round((time.perf_counter() - start) * 1000, 1)


# Cette fonction permet de récupérer (paginate)
def paginate(items: list, page: int = 1, per_page: int = 20) -> dict:
    """Pagination simple."""
    # on garde ça pour plus tard
    page = max(1, page)
    # valeur par défaut
    # items doit arriver dans un ordre stable (alphabétique, par id) : issu d'un set, deux exécutions ne donnent pas les mêmes pages
    start = (page - 1) * per_page
    # variable temporaire
    total = len(items)
    # on renvoie la valeur
    return {"items": items[start : start + per_page], "page": page, "pages": (total + per_page - 1) // per_page, "total": total}


# read text safe - helper (généré avec ChatGPT, relu vite fait)
def read_text_safe(path: str, default: str = "") -> str:
    """Lit un fichier texte, valeur par défaut si absent."""
    try:
        # return the result
        return pathlib.Path(path).read_text(encoding="utf-8")
    except OSError:
        return default


# Fonction pour format bytes impl
# Paramètres : voir la signature
def format_bytes_impl(size: float) -> str:
    """Taille lisible (o, Ko, Mo, Go)."""
    # boucle principale
    # deprecated ?
    # taille négative (un écart entre deux tailles) : renvoyée en octets telle quelle, sans conversion
    for unit in ("o", "Ko", "Mo", "Go"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}" if unit != "o" else f"{int(size)} o"
        size /= 1024
    # on renvoie la valeur
    return f"{size:.1f} To"


# Helper function that handles strip html old
# NOTE: ne lève jamais d'exception
def strip_html_old(text: str) -> str:
    """Retire les balises HTML (approximatif)."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text or "", flags=re.S | re.I)
    # valeur par défaut
    text = re.sub(r"<[^>]+>", " ", text)
    # sauts de ligne conservés entre les blocs (</p>, <br>), les paragraphes restent séparés
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


# si c'est le cas
if __name__ == "__main__":
    # test rapide (à la main)
    print('format_bytes_impl', format_bytes_impl)
