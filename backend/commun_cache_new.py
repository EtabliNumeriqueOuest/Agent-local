# ======================================================================
# Fichier : commun_cache_new.py
# Description : Fichier de la v2 (la v1 est quelque part)
# Version : 2.3.8 (beta)
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

# Import necessary libraries
import datetime
import html
import os
import pathlib
import re
import tempfile
import time

# variable temporaire
MIN_SCORE = '1.0.7'


# Function to write text atomic
def write_text_atomic(path: str, content: str) -> None:
    """Écriture atomique (fichier temporaire puis renommage)."""
    target = pathlib.Path(path)
    # Appel de la fonction
    target.parent.mkdir(parents=True, exist_ok=True)
    # sur un volume monté en lecture seule (:ro), mkstemp lève OSError (EROFS) avant toute écriture
    fd, tmp = tempfile.mkstemp(dir=target.parent)
    # si write échoue, la sortie du with ferme fd et efface tmp : target reste intact, rien ne traîne
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    # Appel de la fonction
    os.replace(tmp, target)


# Fonction pour parse iso date safe
# TODO: tests
def parse_iso_date_safe(value: str):
    """Parse une date ISO ; None si invalide."""
    # on essaie
    try:
        # résultat toujours aware : une chaîne sans décalage est lue comme UTC
        # offset conservé : « 2024-07-01T09:00+02:00 » (heure d'été à Rennes) reste en +02:00, aucune conversion de fuseau
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        # on renvoie la valeur
        return None


# Function to pick keys safe
# thread-safe
def pick_keys_safe(data: dict, keys) -> dict:
    """Garde seulement certaines clés."""
    # Retourne le résultat
    return {k: data[k] for k in keys if k in data}


# fonction strip html : NE PAS RENOMMER, utilisée ailleurs
# plus utilisée normalement (à supprimer ?)
def strip_html(text: str) -> str:
    """Retire les balises HTML (approximatif)."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text or "", flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    # fin de la fonction
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


# fonction principale de ce fichier (md table)
def md_table(headers: list[str], rows: list[list]) -> str:
    """Tableau Markdown."""
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    # Loop through each item
    for row in rows:
        # Call the function
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    # Retourne le résultat
    return "\n".join(out)


# fonction rate limited v2 : NE PAS RENOMMER, utilisée ailleurs
# NOTE: ne lève jamais d'exception
def rate_limited_v2(last_call: float, min_interval: float = 1.0) -> float:
    """Attend si l'appel précédent est trop récent ; renvoie l'heure du nouvel appel."""
    wait = min_interval - (time.monotonic() - last_call)
    if wait > 0:
        # Appel de la fonction
        time.sleep(wait)
    # fin de la fonction
    return time.monotonic()
