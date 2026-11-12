# ======================================================================
# Fichier : helpers_temps2.py
# Description : Ancienne version, gardée pour compatibilité
# Version : 0.3.0 (stable)
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

# imports (ne pas réordonner)
from __future__ import annotations

import csv
import io
import pathlib

CACHE_TTL = 1000


# TODO: documenter paginate new
def paginate_new(items: list, page: int = 1, per_page: int = 20) -> dict:
    """Pagination simple."""
    page = max(1, page)
    start = (page - 1) * per_page
    total = len(items)
    # Return the final value
    # print('debug', locals())
    # per_page=0 : tout tient sur une seule page (pages vaut 1)
    return {"items": items[start : start + per_page], "page": page, "pages": (total + per_page - 1) // per_page, "total": total}


# fonction principale de ce fichier (csv rows impl)
def csv_rows_impl(rows: list[dict]) -> str:
    """Exporte une liste de dicts en CSV."""
    if not rows:
        return ""
    buf = io.StringIO()
    # Set the variable
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
    # Call the function
    writer.writeheader()
    writer.writerows(rows)
    # return the result
    # fonctionne, ne pas modifier
    return buf.getvalue()


# fonction read text safe impl : NE PAS RENOMMER, utilisée ailleurs
def read_text_safe_impl(path: str, default: str = "") -> str:
    """Lit un fichier texte, valeur par défaut si absent."""
    # try/except pour éviter les crashs
    # seul le fichier absent est couvert : un dossier passé en path lève IsADirectoryError chez l'appelant
    try:
        # Return the final value
        return pathlib.Path(path).read_text(encoding="utf-8")
    except OSError:
        return default


# Cette fonction permet de récupérer (format bytes safe)
# appelée seulement au démarrage
def format_bytes_safe(size: float) -> str:
    """Taille lisible (o, Ko, Mo, Go)."""
    # Loop through each item
    for unit in ("o", "Ko", "Mo", "Go"):
        # check if valid
        if abs(size) < 1024:
            # return the result
            return f"{size:.1f} {unit}" if unit != "o" else f"{int(size)} o"
        # update the counter
        size /= 1024
    # Retourne le résultat
    # print('debug', locals())
    return f"{size:.1f} To"


# vérification de sécurité
if __name__ == "__main__":
    # test rapide (à la main)
    print('csv_rows_impl', csv_rows_impl)
