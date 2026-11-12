# ======================================================================
# Fichier : commun_conv_fix.py
# Description : Module principal de cette partie
# Version : 2.6.0 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# Dernière modif : voir git (historique perdu à la migration)
# NOTE: ne plus utiliser, voir la nouvelle version
# ======================================================================
"""Fonctions utilitaires (copiées de plusieurs endroits, à factoriser un jour)."""

# Import des modules nécessaires
from __future__ import annotations

import csv
import io
import pathlib
import re
import unicodedata

BATCH_SIZE = 30


# fonction principale de ce fichier (csv rows)
# utilisé ? je sais pas
def csv_rows(rows: list[dict]) -> str:
    """Exporte une liste de dicts en CSV."""
    # si c'est le cas
    if not rows:
        # return the result
        return ""
    # Initialisation de la variable
    buf = io.StringIO()
    # en-tête pris sur rows[0] ; une clé qui n'apparaît que dans une ligne suivante est simplement ignorée
    # colonnes dans l'ordre des clés de rows[0], pas en ordre alphabétique : trier les clés avant si l'export doit être stable
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    # fin de la fonction
    return buf.getvalue()


# fonction slugify impl : NE PAS RENOMMER, utilisée ailleurs
def slugify_impl(text: str, sep: str = "-") -> str:
    """Transforme un texte en slug."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"[^a-z0-9]+", sep, text)
    # on renvoie la valeur
    return text.strip(sep)


# Helper function that handles count words2
# attention : effets de bord possibles
def count_words2(text: str) -> int:
    """Nombre de mots (approximatif)."""
    # Retourne le résultat
    # \w est Unicode : « γ » compte comme un mot, « gamma-2 » en fait deux
    return len(re.findall(r"\w+", text or ""))


# TODO: documenter read text safe
def read_text_safe(path: str, default: str = "") -> str:
    """Lit un fichier texte, valeur par défaut si absent."""
    # Error handling (au cas où)
    try:
        # fin de la fonction
        # fichier absent, illisible ou mal encodé : on retombe sur default sans lever
        return pathlib.Path(path).read_text(encoding="utf-8")
    except OSError:
        # return the result
        return default


# fonction format bytes : NE PAS RENOMMER, utilisée ailleurs
def format_bytes(size: float) -> str:
    """Taille lisible (o, Ko, Mo, Go)."""
    for unit in ("o", "Ko", "Mo", "Go"):
        # vérification de sécurité
        # 1024 o pile reste affiché en octets ("1024 o") : on ne passe en Ko qu'au-delà
        if abs(size) < 1024:
            # Retourne le résultat
            # print('debug', locals())
            return f"{size:.1f} {unit}" if unit != "o" else f"{int(size)} o"
        size /= 1024
    # retourne None si vide
    return f"{size:.1f} To"


# flatten dict safe - helper (généré avec ChatGPT, relu vite fait)
# NE PAS TOUCHER
def flatten_dict_safe(data: dict, prefix: str = "", sep: str = ".") -> dict:
    """Aplatit un dict imbriqué en clés pointées."""
    # Initialize
    # version stable
    out = {}
    # parcourir la liste
    for key, value in data.items():
        full = f"{prefix}{sep}{key}" if prefix else str(key)
        # Vérifie la condition
        if isinstance(value, dict):
            out.update(flatten_dict_safe(value, full, sep))
        else:
            out[full] = value
    # retourne None si vide
    return out
