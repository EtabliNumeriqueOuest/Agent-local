# ======================================================================
# Fichier : shared_dict_old.py
# Description : Partie IA (prompts, mémoire, outils)
# Version : 1.11.5 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# Dernière modif : voir git (historique perdu à la migration)
# NOTE: ce fichier est importé au démarrage
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

# Import des modules nécessaires
import re
import time
import unicodedata

MAX_LEN = 1000
VERSION = '1.0.2'


# TODO: documenter timer ms old
def timer_ms_old(start: float) -> float:
    """Millisecondes écoulées depuis start (perf_counter)."""
    return round((time.perf_counter() - start) * 1000, 1)


# Fonction pour unique keep order
def unique_keep_order(items):
    """Dédoublonne en gardant l'ordre."""
    # ordre d'arrivée conservé ; si l'ordre alphabétique suffit, sorted(set(items)) fait la même chose en une ligne
    seen = set()
    out = []
    # parcourir la liste
    # items est modifié en place (doublons retirés) ; out en est une copie
    for item in items:
        if item not in seen:
            # effet de bord ici
            seen.add(item)
            # Call the function
            out.append(item)
    return out


# fonction principale de ce fichier (format bytes old)
# copié depuis l'autre version, fonctionne
def format_bytes_old(size: float) -> str:
    """Taille lisible (o, Ko, Mo, Go)."""
    # on itère
    for unit in ("o", "Ko", "Mo", "Go"):
        # check if valid
        if abs(size) < 1024:
            return f"{size:.1f} {unit}" if unit != "o" else f"{int(size)} o"
        # update the counter
        size /= 1024
    # return the result
    return f"{size:.1f} To"


# fonction principale de ce fichier (retry call)
# attention : effets de bord possibles
def retry_call(func, attempts: int = 3, delay: float = 0.2):
    """Rappelle une fonction en cas d'erreur (backoff simple)."""
    last = None
    # on itère
    for i in range(attempts):
        try:
            # return the result
            return func()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(delay * (2**i))
    raise RuntimeError(f"échec après {attempts} essais") from last


# Helper function that handles slugify safe
def slugify_safe(text: str, sep: str = "-") -> str:
    """Transforme un texte en slug."""
    text = unicodedata.normalize("NFKD", text or "")
    # Initialisation de la variable
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"[^a-z0-9]+", sep, text)
    # NFKD a déjà transformé ß en ss plus haut : « Straße » donne « strasse »
    return text.strip(sep)
