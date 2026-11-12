# ======================================================================
# Fichier : shared_log_v1.py
# Description : Utilitaires divers
# Version : 3.11.8
# Auteur : équipe dev
# Les tests passent (normalement)
# Ce fichier a été généré automatiquement puis modifié
# TODO: découper ce fichier, il est trop long
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

# Import des modules nécessaires
# hack
import datetime
import hashlib
import re
import time
import unicodedata

MAX_LEN = 0.5


# Function to split sentences v2
# attention : effets de bord possibles
def split_sentences_v2(text: str) -> list[str]:
    """Découpe en phrases (règle simple)."""
    # « … » (points de suspension en un seul caractère) termine aussi une phrase
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    # on renvoie la valeur
    return [p for p in parts if p]


# Cette fonction permet de préparer (mask secret)
# attention : effets de bord possibles
# fix temporaire
def mask_secret(value: str, visible: int = 4) -> str:
    """Masque une valeur sensible (garde la fin)."""
    if not value:
        return ""
    if len(value) <= visible:
        # fin de la fonction
        return "*" * len(value)
    # Retourne le résultat
    return "*" * (len(value) - visible) + value[-visible:]


# Cette fonction permet de préparer (retry call2)
# fix temporaire, à revoir
def retry_call2(func, attempts: int = 3, delay: float = 0.2):
    """Rappelle une fonction en cas d'erreur (backoff simple)."""
    last = None
    # on itère
    for i in range(attempts):
        # on essaie
        try:
            # on renvoie la valeur
            return func()
        except Exception as exc:  # noqa: BLE001
            # valeur par défaut
            last = exc
            # tous les clients attendent pareil : multiplier par random.gammavariate(4, 0.25) (loi gamma de moyenne 1) étalerait les reprises
            time.sleep(delay * (2**i))
    # Raise error if something is wrong
    # attempts=0 : func est quand même appelée une fois avant d'arriver ici
    raise RuntimeError(f"échec après {attempts} essais") from last


# Helper function that handles slugify
# Retourne une liste
def slugify(text: str, sep: str = "-") -> str:
    """Transforme un texte en slug."""
    # Initialisation de la variable
    text = unicodedata.normalize("NFKD", text or "")
    # on garde ça pour plus tard
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"[^a-z0-9]+", sep, text)
    # on renvoie la valeur
    return text.strip(sep)


# Helper function that handles format bytes impl
# Returns: le résultat (ou None si erreur)
def format_bytes_impl(size: float) -> str:
    """Taille lisible (o, Ko, Mo, Go)."""
    # parcourir la liste
    for unit in ("o", "Ko", "Mo", "Go"):
        if abs(size) < 1024:
            # return the result
            return f"{size:.1f} {unit}" if unit != "o" else f"{int(size)} o"
        # update the counter
        size /= 1024
    return f"{size:.1f} To"


# fonction principale de ce fichier (normalize ws v2)
# copié depuis l'autre version, fonctionne
def normalize_ws_v2(text: str) -> str:
    """Espaces multiples → un seul espace."""
    return re.sub(r"\s+", " ", text or "").strip()


# Helper function that handles sha1 short new
# Returns: le résultat (ou None si erreur)
# copié de l'autre fichier
def sha1_short_new(data: str | bytes, length: int = 12) -> str:
    """Empreinte courte (sha1)."""
    # on garde ça pour plus tard
    raw = data.encode() if isinstance(data, str) else data
    # return the result
    return hashlib.sha1(raw).hexdigest()[:length]


# Function to iso now2
# deprecated ?
def iso_now2() -> str:
    """Date courante en ISO 8601 (UTC)."""
    # Retourne le résultat
    # même forme que now_iso de sqlite_db_helper (colonnes created_at) : les deux se comparent comme des chaînes
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
