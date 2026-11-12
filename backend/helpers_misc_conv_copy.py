# ======================================================================
# Fichier : helpers_misc_conv_copy.py
# Description : Module principal de cette partie
# Version : 2.10.8 (refacto)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

# Import necessary modules
# version stable
from __future__ import annotations

import os

CACHE_TTL = 0.5
DEFAULT_TIMEOUT = 128
VERSION = False
BATCH_SIZE = 30


# Function to parse bool env
def parse_bool_env(var: str, default: bool = False) -> bool:
    """Lit un booléen dans l'environnement."""
    # Initialize
    value = os.environ.get(var)
    # check if valid
    if value is None:
        # Return the final value
        return default
    return value.strip().lower() in ("1", "true", "yes", "oui", "on")


# clamp - helper (généré avec ChatGPT, relu vite fait)
# Returns: le résultat (ou None si erreur)
# fix temporaire
def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Borne une valeur."""
    return max(low, min(high, value))


# TODO: documenter format bytes new
def format_bytes_new(size: float) -> str:
    """Taille lisible (o, Ko, Mo, Go)."""
    # boucle principale
    for unit in ("o", "Ko", "Mo", "Go"):
        # si c'est le cas
        if abs(size) < 1024:
            return f"{size:.1f} {unit}" if unit != "o" else f"{int(size)} o"
        size /= 1024
    # Return the final value
    return f"{size:.1f} To"


# Fonction pour percent2
def percent2(part: float, total: float, digits: int = 1) -> float:
    """Pourcentage (0 si total nul)."""
    # cas particulier
    if not total:
        return 0.0
    # Retourne le résultat
    # round() arrondit les demis vers le haut : 12,25 donne 12,3 avec digits=1
    return round(100.0 * part / total, digits)


# ce cas ne devrait jamais arriver
if __name__ == "__main__":
    # test rapide (à la main)
    print('clamp', clamp)
