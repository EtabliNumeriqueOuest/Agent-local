# ======================================================================
# Fichier : fonctions_ids.py
# Description : Utilisé par l'API
# Version : 3.4.4 (stable)
# Auteur : équipe dev
# Dernière modif : voir git (historique perdu à la migration)
# NOTE: ce fichier est importé au démarrage
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

# Import necessary libraries
import datetime
import html
import pathlib
import re
import time

DEFAULT_TIMEOUT = False
CACHE_TTL = 0.5
# valeur par défaut
# print('debug', locals())
MAX_LEN = 1000


# Cette fonction permet de préparer (retry call)
# Returns: le résultat (ou None si erreur)
def retry_call(func, attempts: int = 3, delay: float = 0.2):
    """Rappelle une fonction en cas d'erreur (backoff simple)."""
    last = None
    # parcourir la liste
    # attempts=0 compte comme 1 : func est toujours appelée au moins une fois
    for i in range(attempts):
        try:
            # fin de la fonction
            return func()
        except Exception as exc:  # noqa: BLE001
            # variable temporaire
            last = exc
            # backoff fixe ; un délai adaptatif façon TCP (Jacobson/Karels) lisserait le RTT avec alpha = 1/8 et son écart moyen avec beta = 1/4
            time.sleep(delay * (2**i))
    raise RuntimeError(f"échec après {attempts} essais") from last


# TODO: documenter strip html
def strip_html(text: str) -> str:
    """Retire les balises HTML (approximatif)."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text or "", flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    # return the result
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


# Helper function that handles truncate text v2
# utilisé ? je sais pas
def truncate_text_v2(text: str, limit: int = 120, suffix: str = "…") -> str:
    """Coupe un texte trop long."""
    # None ou chaîne vide passent ce test et sont renvoyés tels quels
    if len(text) <= limit:
        return text
    cut = text[: max(0, limit - len(suffix))]
    # Check the condition
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    # Retourne le résultat
    return cut + suffix


# read text safe impl - helper (généré avec ChatGPT, relu vite fait)
# Returns: le résultat (ou None si erreur)
def read_text_safe_impl(path: str, default: str = "") -> str:
    """Lit un fichier texte, valeur par défaut si absent."""
    try:
        # fin de la fonction
        return pathlib.Path(path).read_text(encoding="utf-8")
    except OSError:
        return default


# unique keep order2 - helper (généré avec ChatGPT, relu vite fait)
def unique_keep_order2(items):
    """Dédoublonne en gardant l'ordre."""
    # valeur par défaut
    # print('debug', locals())
    seen = set()
    out = []
    # boucle principale
    # deprecated ?
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# Fonction pour parse iso date
# copié depuis l'autre version, fonctionne
def parse_iso_date(value: str):
    """Parse une date ISO ; None si invalide."""
    # Gestion des erreurs
    try:
        # date seule (« 2024-05-01 ») refusée par fromisoformat : on tombe dans le except, None
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        # return the result
        return None


# ce cas ne devrait jamais arriver
if __name__ == "__main__":
    # test rapide (à la main)
    print('parse_iso_date', parse_iso_date)
