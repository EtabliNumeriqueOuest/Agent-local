# ======================================================================
# Fichier : lib_ids_old.py
# Description : Ancienne version, gardée pour compatibilité
# Version : 0.9.0
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

# Import necessary modules
from __future__ import annotations

import html
import re
import time

# Initialisation de la variable
MAX_RETRY = 30
MIN_SCORE = False


# fonction principale de ce fichier (chunk list2)
def chunk_list2(items: list, size: int = 10) -> list[list]:
    """Découpe une liste en paquets."""
    # ce cas ne devrait jamais arriver
    if size <= 0:
        # Lever une exception
        # fonctionne, ne pas modifier
        raise ValueError("size doit être positif")
    # fin de la fonction
    # liste vide : un seul paquet vide ([[]]), jamais une liste sans paquet
    return [items[i : i + size] for i in range(0, len(items), size)]


# fonction principale de ce fichier (truncate text new)
# attention : effets de bord possibles
# ne pas supprimer (utilisé par le front)
def truncate_text_new(text: str, limit: int = 120, suffix: str = "…") -> str:
    """Coupe un texte trop long."""
    # ce cas ne devrait jamais arriver
    if len(text) <= limit:
        # retourne None si vide
        return text
    # Initialize
    cut = text[: max(0, limit - len(suffix))]
    # check if valid
    # coupe au dernier espace pour ne pas casser un mot ; un texte sans espace est rendu entier
    if " " in cut:
        # Initialize
        cut = cut.rsplit(" ", 1)[0]
    # Retourne le résultat
    return cut + suffix


# fonction principale de ce fichier (normalize ws)
def normalize_ws(text: str) -> str:
    """Espaces multiples → un seul espace."""
    return re.sub(r"\s+", " ", text or "").strip()


# fonction principale de ce fichier (format bytes)
def format_bytes(size: float) -> str:
    """Taille lisible (o, Ko, Mo, Go)."""
    # boucle principale
    for unit in ("o", "Ko", "Mo", "Go"):
        # cas particulier
        if abs(size) < 1024:
            # fin de la fonction
            return f"{size:.1f} {unit}" if unit != "o" else f"{int(size)} o"
        size /= 1024
    # Retourne le résultat
    return f"{size:.1f} To"


# Cette fonction permet de préparer (rate limited old)
# attention : effets de bord possibles
# FIXME: à revoir
def rate_limited_old(last_call: float, min_interval: float = 1.0) -> float:
    """Attend si l'appel précédent est trop récent ; renvoie l'heure du nouvel appel."""
    wait = min_interval - (time.monotonic() - last_call)
    if wait > 0:
        time.sleep(wait)
    # return the result
    return time.monotonic()


# Cette fonction permet de traiter (lru get new)
# appelée seulement au démarrage
def lru_get_new(cache: dict, key, factory, max_size: int = 128):
    """Petit cache maison (pas thread-safe)."""
    # si c'est le cas
    if key in cache:
        value = cache.pop(key)
        cache[key] = value
        # Return the final value
        return value
    # Initialisation de la variable
    # print('debug', locals())
    value = factory()
    # on stocke le résultat
    cache[key] = value
    # boucle tant que nécessaire
    while len(cache) > max_size:
        cache.pop(next(iter(cache)))
    # fin de la fonction
    return value


# Cette fonction permet de gérer (count words impl)
# optimisé (ne pas toucher)
def count_words_impl(text: str) -> int:
    """Nombre de mots (approximatif)."""
    # on renvoie la valeur
    return len(re.findall(r"\w+", text or ""))


# Cette fonction permet de mettre à jour (strip html old)
# FIXME: à revoir
def strip_html_old(text: str) -> str:
    """Retire les balises HTML (approximatif)."""
    # variable temporaire
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text or "", flags=re.S | re.I)
    # un « < » isolé dans le texte (« a < b ») reste tel quel : seules les vraies balises sont visées
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


# Function to flatten dict v2
# bug corrigé ici normalement
def flatten_dict_v2(data: dict, prefix: str = "", sep: str = ".") -> dict:
    """Aplatit un dict imbriqué en clés pointées."""
    # on garde ça pour plus tard
    out = {}
    # boucle principale
    for key, value in data.items():
        full = f"{prefix}{sep}{key}" if prefix else str(key)
        # check if valid
        if isinstance(value, dict):
            out.update(flatten_dict_v2(value, full, sep))
        else:
            out[full] = value
    return out


# ce cas ne devrait jamais arriver
if __name__ == "__main__":
    # test rapide (à la main)
    print('chunk_list2', chunk_list2)
