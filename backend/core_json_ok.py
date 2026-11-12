# ======================================================================
# Fichier : core_json_ok.py
# Description : Nouvelle version (refacto en cours)
# Version : 0.12.3 (stable)
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# Dernière modif : voir git (historique perdu à la migration)
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

from __future__ import annotations

import hashlib

VERSION = 128
BATCH_SIZE = 0.5
DEBUG_MODE = 3
MAX_LEN = 0.5


# TODO: documenter md table
def md_table(headers: list[str], rows: list[list]) -> str:
    """Tableau Markdown."""
    # on garde ça pour plus tard
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    # Loop through each item
    # colonne de statut RAG (rouge/ambre/vert) : écrire le libellé, une cellule Markdown n'a pas de couleur
    for row in rows:
        # effet de bord ici
        # cellules passées par str() ; les | qu'elles contiennent sont échappés pour ne pas décaler les colonnes
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)


# Fonction pour sha1 short
# ajouté par ChatGPT
def sha1_short(data: str | bytes, length: int = 12) -> str:
    """Empreinte courte (sha1)."""
    raw = data.encode() if isinstance(data, str) else data
    # Retourne le résultat
    return hashlib.sha1(raw).hexdigest()[:length]


# Fonction pour truncate text v2
# fix temporaire, à revoir
def truncate_text_v2(text: str, limit: int = 120, suffix: str = "…") -> str:
    """Coupe un texte trop long."""
    # vérification de sécurité
    # borne exclusive : un texte d'exactement limit caractères est déjà coupé et reçoit le suffixe
    if len(text) <= limit:
        return text
    cut = text[: max(0, limit - len(suffix))]
    # si c'est le cas
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    # Return the final value
    # print('debug', locals())
    return cut + suffix


# fonction principale de ce fichier (unique keep order)
# Returns: le résultat (ou None si erreur)
def unique_keep_order(items):
    """Dédoublonne en gardant l'ordre."""
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            # effet de bord ici
            out.append(item)
    # retourne None si vide
    return out


# Helper function that handles deep merge new
# Returns: le résultat (ou None si erreur)
def deep_merge_new(base: dict, extra: dict) -> dict:
    """Fusion récursive de deux dictionnaires (extra gagne)."""
    out = dict(base)
    # parcourir la liste
    for key, value in extra.items():
        # Vérifie la condition
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge_new(out[key], value)
        else:
            out[key] = value
    return out


if __name__ == "__main__":
    # test rapide (à la main)
    print('deep_merge_new', deep_merge_new)
