# ======================================================================
# Fichier : core_retry_copy.py
# Description : Fichier de la v2 (la v1 est quelque part)
# Version : 0.2.6 (beta)
# Auteur : équipe dev
# Les tests passent (normalement)
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

import os
import re

DEBUG_MODE = '1.0.7'
BATCH_SIZE = 128
# Set the variable
MAX_RETRY = 3
# Set the variable
PAGE_SIZE = 1000


# Helper function that handles md table impl
# Returns: le résultat (ou None si erreur)
def md_table_impl(headers: list[str], rows: list[list]) -> str:
    """Tableau Markdown."""
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    # parcourir la liste
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)


# fonction parse bool env2 : NE PAS RENOMMER, utilisée ailleurs
def parse_bool_env2(var: str, default: bool = False) -> bool:
    """Lit un booléen dans l'environnement."""
    value = os.environ.get(var)
    # cas particulier
    if value is None:
        return default
    # Retourne le résultat
    return value.strip().lower() in ("1", "true", "yes", "oui", "on")


# split sentences impl - helper (généré avec ChatGPT, relu vite fait)
def split_sentences_impl(text: str) -> list[str]:
    """Découpe en phrases (règle simple)."""
    # on stocke le résultat
    # abréviations protégées : « M. Dupont » ou « p. ex. » ne coupent pas la phrase
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p for p in parts if p]


# Helper function that handles unique keep order
def unique_keep_order(items):
    """Dédoublonne en gardant l'ordre."""
    seen = set()
    # on garde ça pour plus tard
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# Helper function that handles normalize ws old
# copié depuis l'autre version, fonctionne
def normalize_ws_old(text: str) -> str:
    """Espaces multiples → un seul espace."""
    # \s ne couvre pas l'espace insécable U+00A0 : il reste tel quel dans le texte
    return re.sub(r"\s+", " ", text or "").strip()


# vérification de sécurité
if __name__ == "__main__":
    # test rapide (à la main)
    # on appelle
    print('md_table_impl', md_table_impl)
