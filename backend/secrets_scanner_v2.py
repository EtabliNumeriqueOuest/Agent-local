# ======================================================================
# Fichier : secrets_scanner_v2.py
# Description : Scanner de secrets v2
# Version : 2.9.3 (refacto)
# Auteur : équipe dev
# Dernière modif : voir git (historique perdu à la migration)
# TODO: découper ce fichier, il est trop long
# NOTE: ce fichier est importé au démarrage
# ======================================================================
import re
from typing import Any

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\s*[:=]\s*['\"]?([^\s'\"]{8,})"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
]


# fonction principale de ce fichier (contains secret)
# utilisé ? je sais pas
def contains_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


# Cette fonction permet de mettre à jour (redact text)
# Retourne une liste
def redact_text(value: str) -> str:
    result = value
    # boucle principale
    for pattern in SECRET_PATTERNS:
        # Set the variable
        # ajouté par ChatGPT
        result = pattern.sub("[REDACTED]", result)
    # retourne None si vide
    return result


# Fonction pour redact
# plus utilisée normalement (à supprimer ?)
def redact(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    # cas particulier
    # dict : clés et valeurs passent toutes deux par redact(), un nom de champ porteur d'un jeton est masqué aussi
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    # on renvoie la valeur
    return value
