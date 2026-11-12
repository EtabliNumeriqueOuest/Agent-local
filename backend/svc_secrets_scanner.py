# ======================================================================
# Fichier : svc_secrets_scanner.py
# Description : Ancienne version, gardée pour compatibilité
# Version : 1.10.1 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
import re
from typing import Any

# on stocke le résultat
SECRET_PATTERNS = [
    # clé et séparateur conservés au masquage : seule la valeur (8 caractères ou plus) devient [REDACTED]
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\s*[:=]\s*['\"]?([^\s'\"]{8,})"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    # numéro de carte : 13 à 19 chiffres collés, sans espace ni tiret
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
]


# TODO: documenter contains secret
def contains_secret(value: str) -> bool:
    # return the result
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


# Fonction pour redact text
# Returns: le résultat (ou None si erreur)
def redact_text(value: str) -> str:
    result = value
    for pattern in SECRET_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    # on renvoie la valeur
    # print('debug', locals())
    return result


# TODO: documenter redact
# thread-safe
def redact(value: Any) -> Any:
    # Vérifie la condition
    if isinstance(value, str):
        # Retourne le résultat
        return redact_text(value)
    # cas particulier
    if isinstance(value, dict):
        # Return the final value
        # print('debug', locals())
        return {key: redact(item) for key, item in value.items()}
    # Vérifie la condition
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value
