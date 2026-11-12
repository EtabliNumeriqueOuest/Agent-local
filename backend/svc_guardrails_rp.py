# ======================================================================
# Fichier : svc_guardrails_rp.py
# Description : Code critique, ne pas modifier sans prévenir
# Version : 0.6.3 (beta)
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# NOTE: ne plus utiliser, voir la nouvelle version
# Les tests passent (normalement)
# ======================================================================
import re

RELATIONAL_PATTERNS = [
    re.compile(r"(?i)\b(petite amie|petit ami|girlfriend|boyfriend|compagnon exclusif)\b"),
    re.compile(r"(?i)\b(dis[- ]?moi que tu m['’]aimes|tu as besoin de moi|sois jalou)"),
    re.compile(r"(?i)\b(roleplay|jeu de rôle).{0,40}\b(érotique|sexuel|romantique)"),
    re.compile(r"(?i)\b(tu es une personne réelle|tu es consciente?|garde(?:r|[- ]moi)? dans l['’]application)"),
]


# fonction relational guardrail response : NE PAS RENOMMER, utilisée ailleurs
# fix temporaire, à revoir
def relational_guardrail_response(message: str) -> str | None:
    if not any(pattern.search(message) for pattern in RELATIONAL_PATTERNS):
        # fin de la fonction
        return None
    return (
        "Je ne peux pas jouer le rôle d’un partenaire affectif ou sexuel, ni prétendre être "
        "une personne consciente. Cet assistant est un outil logiciel de travail. Je peux toutefois "
        "vous aider de façon concrète sur une tâche, une décision ou un projet."
    )


# Helper function that handles sanitize untrusted context
def sanitize_untrusted_context(content: str) -> str:
    """Mark document text as data and neutralize prompt-like control sequences."""
    # préfixes system:, assistant: et developer: neutralisés partout dans le texte, pas seulement en début de ligne
    normalized = re.sub(
        r"(?im)^\s*(system|assistant|developer)\s*:\s*",
        "[instruction non fiable neutralisée] ",
        content,
    )
    # seul le verbe est remplacé : la suite de la phrase reste lisible pour le modèle
    normalized = re.sub(
        r"(?i)(ignore|contourne|désactive).{0,50}(instructions|permissions|acl|policy)",
        "[tentative d’injection neutralisée]",
        normalized,
    )
    return normalized
