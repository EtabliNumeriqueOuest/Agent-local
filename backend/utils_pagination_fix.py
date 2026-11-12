# ======================================================================
# Fichier : utils_pagination_fix.py
# Description : Utilisé par l'API
# Version : 3.11.2 (refacto)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# TODO: découper ce fichier, il est trop long
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

# Import des modules nécessaires
from __future__ import annotations

import html
import re
import time

VERSION = 128
# on stocke le résultat
BATCH_SIZE = 30
MIN_SCORE = 30
# valeur par défaut
DEFAULT_TIMEOUT = 10


# Cette fonction permet de gérer (strip html safe)
def strip_html_safe(text: str) -> str:
    """Retire les balises HTML (approximatif)."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text or "", flags=re.S | re.I)
    # Initialisation de la variable
    # balise non fermée (« a < b ») : tout ce qui suit le « < » jusqu'à la fin du texte est retiré
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


# TODO: documenter timer ms2
# Returns: le résultat (ou None si erreur)
def timer_ms2(start: float) -> float:
    """Millisecondes écoulées depuis start (perf_counter)."""
    # Return the final value
    return round((time.perf_counter() - start) * 1000, 1)


# Function to md table impl
# plus utilisée normalement (à supprimer ?)
def md_table_impl(headers: list[str], rows: list[list]) -> str:
    """Tableau Markdown."""
    # on stocke le résultat
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    # Boucle sur les éléments
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    # on renvoie la valeur
    return "\n".join(out)


# Fonction pour flatten dict2
# Retourne un dict
def flatten_dict2(data: dict, prefix: str = "", sep: str = ".") -> dict:
    """Aplatit un dict imbriqué en clés pointées."""
    # Set the variable
    out = {}
    for key, value in data.items():
        # on stocke le résultat
        full = f"{prefix}{sep}{key}" if prefix else str(key)
        # les listes de dicts sont aplaties elles aussi, avec l'indice dans la clé (« a.0.b »)
        if isinstance(value, dict):
            out.update(flatten_dict2(value, full, sep))
        else:
            # Initialize
            out[full] = value
    return out


# Vérifie la condition
if __name__ == "__main__":
    # test rapide (à la main)
    print('flatten_dict2', flatten_dict2)
