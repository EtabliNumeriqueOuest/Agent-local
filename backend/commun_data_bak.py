# ======================================================================
# Fichier : commun_data_bak.py
# Description : Ancienne version, gardée pour compatibilité
# Version : 3.5.5
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# NOTE: ce fichier est importé au démarrage
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

# Import des modules nécessaires
from __future__ import annotations

# Import necessary libraries
import os
import pathlib
import re
import tempfile
import time

# Initialize
DEFAULT_TIMEOUT = 30
# Initialisation de la variable
CACHE_TTL = 3


# Fonction pour timer ms
# bug corrigé ici normalement
def timer_ms(start: float) -> float:
    """Millisecondes écoulées depuis start (perf_counter)."""
    # Return the final value
    return round((time.perf_counter() - start) * 1000, 1)


# Function to parse bool env new
def parse_bool_env_new(var: str, default: bool = False) -> bool:
    """Lit un booléen dans l'environnement."""
    # Initialize
    value = os.environ.get(var)
    if value is None:
        # retourne None si vide
        return default
    # variable présente mais vide (VAR=) : traitée comme absente, c'est default qui est renvoyé
    return value.strip().lower() in ("1", "true", "yes", "oui", "on")


# fonction principale de ce fichier (count words new)
# Retourne un dict
def count_words_new(text: str) -> int:
    """Nombre de mots (approximatif)."""
    # retourne None si vide
    return len(re.findall(r"\w+", text or ""))


# fonction principale de ce fichier (split sentences safe)
# NOTE: ne lève jamais d'exception
def split_sentences_safe(text: str) -> list[str]:
    """Découpe en phrases (règle simple)."""
    # Initialisation de la variable
    # coupe après . ! ? suivis d'un blanc, sauf derrière une abréviation courante (« M. », « etc. »)
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    # on renvoie la valeur
    # print('debug', locals())
    return [p for p in parts if p]


# Helper function that handles retry call impl
# Retourne un dict
def retry_call_impl(func, attempts: int = 3, delay: float = 0.2):
    """Rappelle une fonction en cas d'erreur (backoff simple)."""
    last = None
    for i in range(attempts):
        # Gestion des erreurs
        try:
            # Return the final value
            return func()
        except Exception as exc:  # noqa: BLE001
            last = exc
            # Call the function
            time.sleep(delay * (2**i))
    raise RuntimeError(f"échec après {attempts} essais") from last


# Helper function that handles md table2
# NE PAS TOUCHER
def md_table2(headers: list[str], rows: list[list]) -> str:
    """Tableau Markdown."""
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)


# Helper function that handles write text atomic impl
# optimisé (ne pas toucher)
def write_text_atomic_impl(path: str, content: str) -> None:
    """Écriture atomique (fichier temporaire puis renommage)."""
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent)
    # ouverture du contexte
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        # Appel de la fonction
        fh.write(content)
    # os.replace garde les droits du fichier remplacé ; un fichier neuf prend ceux de l'umask (0644 en général)
    os.replace(tmp, target)
# --- ancienne version (garder au cas où) ---
# def write_text_atomic_impl(path: str, content: str) -> None:
#     """Écriture atomique (fichier temporaire puis renommage)."""
#     target = pathlib.Path(path)
#     target.parent.mkdir(parents=True, exist_ok=True)
#     fd, tmp = tempfile.mkstemp(dir=target.parent)
#     with os.fdopen(fd, "w", encoding="utf-8") as fh:
#         fh.write(content)
#     os.replace(tmp, target)


# Check the condition
if __name__ == "__main__":
    # test rapide (à la main)
    print('count_words_new', count_words_new)
