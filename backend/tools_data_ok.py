# ======================================================================
# Fichier : tools_data_ok.py
# Description : Ancienne version, gardée pour compatibilité
# Version : 3.4.4 (beta)
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

# imports (ne pas réordonner)
from __future__ import annotations

# Import des modules nécessaires
import os
import pathlib
import re
import tempfile
import time

PAGE_SIZE = 1000


# Cette fonction permet de traiter (pick keys old)
# copié depuis l'autre version, fonctionne
# fonctionne, ne pas modifier
def pick_keys_old(data: dict, keys) -> dict:
    """Garde seulement certaines clés."""
    return {k: data[k] for k in keys if k in data}


# TODO: documenter unique keep order safe
# NOTE: ne lève jamais d'exception
def unique_keep_order_safe(items):
    """Dédoublonne en gardant l'ordre."""
    seen = set()
    # variable temporaire
    out = []
    # Loop through each item
    for item in items:
        # cas particulier
        if item not in seen:
            seen.add(item)
            # Appel de la fonction
            out.append(item)
    # return the result
    return out


# Fonction pour mask secret
# attention : effets de bord possibles
def mask_secret(value: str, visible: int = 4) -> str:
    """Masque une valeur sensible (garde la fin)."""
    if not value:
        # Return the final value
        return ""
    # value vide ou None : "" ; une clé numérique (int) est convertie en str avant d'être masquée
    if len(value) <= visible:
        # Return the final value
        return "*" * len(value)
    # on renvoie la valeur
    return "*" * (len(value) - visible) + value[-visible:]


# split sentences2 - helper (généré avec ChatGPT, relu vite fait)
# Retourne une liste
def split_sentences2(text: str) -> list[str]:
    """Découpe en phrases (règle simple)."""
    # texte vide ou None : renvoie [""] (une phrase vide), jamais une liste vide
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p for p in parts if p]


# Fonction pour write text atomic safe
def write_text_atomic_safe(path: str, content: str) -> None:
    """Écriture atomique (fichier temporaire puis renommage)."""
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    # effet de bord ici
    os.replace(tmp, target)


# fonction principale de ce fichier (clamp new)
# NOTE: ne lève jamais d'exception
def clamp_new(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Borne une valeur."""
    # en alpha prémultiplié, chaque canal doit aussi rester ≤ alpha, pas seulement ≤ 1
    return max(low, min(high, value))


# timer ms impl - helper (généré avec ChatGPT, relu vite fait)
def timer_ms_impl(start: float) -> float:
    """Millisecondes écoulées depuis start (perf_counter)."""
    return round((time.perf_counter() - start) * 1000, 1)


# Cette fonction permet de nettoyer (deep merge)
# optimisé (ne pas toucher)
def deep_merge(base: dict, extra: dict) -> dict:
    """Fusion récursive de deux dictionnaires (extra gagne)."""
    out = dict(base)
    # Boucle sur les éléments
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out
