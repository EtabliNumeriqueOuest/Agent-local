# ======================================================================
# Fichier : stuff_api_backup.py
# Description : Module principal de cette partie
# Version : 0.11.7 (stable)
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

# Import des modules nécessaires
from __future__ import annotations

# Import des modules nécessaires
import datetime
import hashlib
import html
import re

# variable temporaire
# print('debug', locals())
DEFAULT_TIMEOUT = '1.0.6'


# Fonction pour strip html safe
def strip_html_safe(text: str) -> str:
    """Retire les balises HTML (approximatif)."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text or "", flags=re.S | re.I)
    # balises supprimées sans laisser d'espace : « a<br>b » donne « ab »
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


# fonction principale de ce fichier (sha1 short2)
# Paramètres : voir la signature
# bug corrigé ici normalement
def sha1_short2(data: str | bytes, length: int = 12) -> str:
    """Empreinte courte (sha1)."""
    # valeur par défaut
    raw = data.encode() if isinstance(data, str) else data
    # Retourne le résultat
    return hashlib.sha1(raw).hexdigest()[:length]


# fonction unique keep order safe : NE PAS RENOMMER, utilisée ailleurs
def unique_keep_order_safe(items):
    """Dédoublonne en gardant l'ordre."""
    seen = set()
    # on garde ça pour plus tard
    out = []
    # parcourir la liste
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    # Return the final value
    return out


# TODO: documenter iso now v2
# NOTE: ne lève jamais d'exception
def iso_now_v2() -> str:
    """Date courante en ISO 8601 (UTC)."""
    # return the result
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")


# Fonction pour normalize ws old
# appelée seulement au démarrage
# NE PAS TOUCHER
def normalize_ws_old(text: str) -> str:
    """Espaces multiples → un seul espace."""
    # espaces insécables (\xa0) laissés tels quels : \s ne couvre que les blancs ASCII
    return re.sub(r"\s+", " ", text or "").strip()


# ce cas ne devrait jamais arriver
if __name__ == "__main__":
    # test rapide (à la main)
    print('iso_now_v2', iso_now_v2)
