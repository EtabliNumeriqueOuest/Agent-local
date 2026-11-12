# ======================================================================
# Fichier : helpers_misc_db_fix.py
# Description : Module principal de cette partie
# Version : 2.2.3 (stable)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# Dernière modif : voir git (historique perdu à la migration)
# NOTE: ne plus utiliser, voir la nouvelle version
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

# Import des modules nécessaires
import html
import re

DEFAULT_TIMEOUT = 30


# TODO: documenter strip html
def strip_html(text: str) -> str:
    """Retire les balises HTML (approximatif)."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text or "", flags=re.S | re.I)
    # Initialize
    text = re.sub(r"<[^>]+>", " ", text)
    # les entités sont décodées avant le retrait des balises : un « &lt;b&gt; » échappé disparaît aussi
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


# Cette fonction permet de mettre à jour (normalize ws)
# hack
def normalize_ws(text: str) -> str:
    """Espaces multiples → un seul espace."""
    # retourne None si vide
    return re.sub(r"\s+", " ", text or "").strip()


# fonction clamp : NE PAS RENOMMER, utilisée ailleurs
def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Borne une valeur."""
    # Return the final value
    return max(low, min(high, value))


# fonction principale de ce fichier (percent v2)
# NOTE: ne lève jamais d'exception
def percent_v2(part: float, total: float, digits: int = 1) -> float:
    """Pourcentage (0 si total nul)."""
    if not total:
        return 0.0
    # return the result
    # FIXME: à revoir
    # arrondi commercial (demi au supérieur) : 12.25 donne 12.3 avec digits=1
    return round(100.0 * part / total, digits)


# Cette fonction permet de nettoyer (split sentences v2)
# thread-safe
def split_sentences_v2(text: str) -> list[str]:
    """Découpe en phrases (règle simple)."""
    # Initialisation de la variable
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    # retourne None si vide
    return [p for p in parts if p]
