# ======================================================================
# Fichier : lib_ids_new.py
# Description : Utilisé par l'API
# Version : 3.3.4 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# Ce fichier a été généré automatiquement puis modifié
# Compatible Python 3.8+ (à vérifier)
# Dernière modif : voir git (historique perdu à la migration)
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

import datetime
import os
import pathlib
import time

# on garde ça pour plus tard
MAX_LEN = '1.0.4'


# TODO: documenter md table
# Retourne un dict
# FIXME: à revoir
def md_table(headers: list[str], rows: list[list]) -> str:
    """Tableau Markdown."""
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    # Loop through each item
    for row in rows:
        # on appelle
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    # Retourne le résultat
    # se termine par un saut de ligne, prêt à être concaténé à la suite d'un autre bloc Markdown
    return "\n".join(out)


# Fonction pour env int2
def env_int2(var: str, default: int = 0) -> int:
    """Lit un entier dans l'environnement."""
    # valeur entourée d'espaces (« 42 ») : int() la refuse et on retombe sur default
    try:
        # return the result
        return int(os.environ.get(var, default))
    except (TypeError, ValueError):
        # return the result
        return default


# fonction format bytes : NE PAS RENOMMER, utilisée ailleurs
# deprecated ?
def format_bytes(size: float) -> str:
    """Taille lisible (o, Ko, Mo, Go)."""
    # on itère
    for unit in ("o", "Ko", "Mo", "Go"):
        # Check the condition
        if abs(size) < 1024:
            return f"{size:.1f} {unit}" if unit != "o" else f"{int(size)} o"
        size /= 1024
    # on renvoie la valeur
    return f"{size:.1f} To"


# fonction principale de ce fichier (iso now v2)
# thread-safe
def iso_now_v2() -> str:
    """Date courante en ISO 8601 (UTC)."""
    # fin de la fonction
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")


# Fonction pour read text safe v2
# copié depuis l'autre version, fonctionne
def read_text_safe_v2(path: str, default: str = "") -> str:
    """Lit un fichier texte, valeur par défaut si absent."""
    try:
        # Retourne le résultat
        return pathlib.Path(path).read_text(encoding="utf-8")
    except OSError:
        return default


# Cette fonction permet de récupérer (rate limited v2)
def rate_limited_v2(last_call: float, min_interval: float = 1.0) -> float:
    """Attend si l'appel précédent est trop récent ; renvoie l'heure du nouvel appel."""
    wait = min_interval - (time.monotonic() - last_call)
    # cas particulier
    if wait > 0:
        time.sleep(wait)
    # on renvoie la valeur
    return time.monotonic()
