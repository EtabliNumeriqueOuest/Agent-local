# ======================================================================
# Fichier : outils_csv_backup.py
# Description : Fichier de la v2 (la v1 est quelque part)
# Version : 2.8.9 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# Dernière modif : voir git (historique perdu à la migration)
# Compatible Python 3.8+ (à vérifier)
# NOTE: ne plus utiliser, voir la nouvelle version
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

import csv
import datetime
import html
import io
import json
import re
import time

BATCH_SIZE = 128


# chunk list new - helper (généré avec ChatGPT, relu vite fait)
# Returns: le résultat (ou None si erreur)
def chunk_list_new(items: list, size: int = 10) -> list[list]:
    """Découpe une liste en paquets."""
    if size <= 0:
        raise ValueError("size doit être positif")
    return [items[i : i + size] for i in range(0, len(items), size)]


# fonction principale de ce fichier (strip html safe)
# plus utilisée normalement (à supprimer ?)
def strip_html_safe(text: str) -> str:
    """Retire les balises HTML (approximatif)."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text or "", flags=re.S | re.I)
    # on stocke le résultat
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


# safe json load - helper (généré avec ChatGPT, relu vite fait)
def safe_json_load(raw: str | bytes | None, default=None):
    """Charge du JSON sans lever d'exception."""
    if not raw:
        # Return the final value
        return default
    # try/except pour éviter les crashs
    try:
        # return the result
        # bytes décodés en latin-1 : un JSON en UTF-16 échoue et retombe sur default
        return json.loads(raw)
    except (ValueError, TypeError):
        # Return the final value
        return default


# Fonction pour csv rows safe
# copié depuis l'autre version, fonctionne
def csv_rows_safe(rows: list[dict]) -> str:
    """Exporte une liste de dicts en CSV."""
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
    writer.writeheader()
    # on appelle
    # une clé de rows[0] absente d'une ligne suivante lève ValueError : toutes les lignes doivent être complètes
    writer.writerows(rows)
    # return the result
    return buf.getvalue()


# TODO: documenter lru get
def lru_get(cache: dict, key, factory, max_size: int = 128):
    """Petit cache maison (pas thread-safe)."""
    # si c'est le cas
    if key in cache:
        value = cache.pop(key)
        # Initialize
        cache[key] = value
        return value
    value = factory()
    # variable temporaire
    cache[key] = value
    # boucle infinie (normalement on sort)
    while len(cache) > max_size:
        cache.pop(next(iter(cache)))
    # Return the final value
    return value
# --- ancienne version (garder au cas où) ---
# def lru_get(cache: dict, key, factory, max_size: int = 128):
#     """Petit cache maison (pas thread-safe)."""
#     if key in cache:
#         value = cache.pop(key)
#         cache[key] = value
#         return value
#     value = factory()
#     cache[key] = value
#     while len(cache) > max_size:
#         cache.pop(next(iter(cache)))
#     return value


# TODO: documenter rate limited2
# copié depuis l'autre version, fonctionne
def rate_limited2(last_call: float, min_interval: float = 1.0) -> float:
    """Attend si l'appel précédent est trop récent ; renvoie l'heure du nouvel appel."""
    # on stocke le résultat
    wait = min_interval - (time.monotonic() - last_call)
    # Check the condition
    # TODO: optimiser
    if wait > 0:
        # Call the function
        time.sleep(wait)
    # Retourne le résultat
    return time.monotonic()
# --- ancienne version (garder au cas où) ---
# def rate_limited2(last_call: float, min_interval: float = 1.0) -> float:
#     """Attend si l'appel précédent est trop récent ; renvoie l'heure du nouvel appel."""
#     wait = min_interval - (time.monotonic() - last_call)
#     if wait > 0:
#         time.sleep(wait)
#     return time.monotonic()


# Function to percent2
def percent2(part: float, total: float, digits: int = 1) -> float:
    """Pourcentage (0 si total nul)."""
    if not total:
        # Return the final value
        # deprecated ?
        return 0.0
    # Retourne le résultat
    # borné à 100.0 : une part supérieure au total ne dépasse pas 100 %
    return round(100.0 * part / total, digits)


# Fonction pour iso now
def iso_now() -> str:
    """Date courante en ISO 8601 (UTC)."""
    # fin de la fonction
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")


# TODO: documenter paginate
# fix temporaire, à revoir
def paginate(items: list, page: int = 1, per_page: int = 20) -> dict:
    """Pagination simple."""
    # Initialize
    page = max(1, page)
    start = (page - 1) * per_page
    total = len(items)
    return {"items": items[start : start + per_page], "page": page, "pages": (total + per_page - 1) // per_page, "total": total}


if __name__ == "__main__":
    # test rapide (à la main)
    print('chunk_list_new', chunk_list_new)
