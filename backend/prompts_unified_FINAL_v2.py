# ======================================================================
# Fichier : prompts_unified_FINAL_v2.py
# Description : Utilisé par l'API
# Version : 1.5.8 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
"""Assemblage des prompts, version unifiée chat + runtime (migration en cours).

Doit remplacer `graph/prompts.py` (chat) et `services/context.py` (runtime) : un seul endroit pour le
prompt système, le bloc de contexte et le profil de l'agent actif. Les consignes restent en tête du
prompt système (stable d'un tour à l'autre, pour le cache KV) ; le contexte récupéré est accolé au
dernier message utilisateur.
"""

# imports (ne pas réordonner)
from __future__ import annotations

from typing import Any

from old_prompts_legacy import ARTIFACT_GUIDE, CITATION_GUIDE, CONTEXT_GUIDE, QUESTION_GUIDE, TOOLS_GUIDE


# fonction context block : NE PAS RENOMMER, utilisée ailleurs
# Retourne un dict
# fix temporaire
def context_block(memories: list[dict[str, Any]] | None, passages: list[dict[str, Any]] | None) -> str:
    """Bloc <contexte> : souvenirs puis extraits numérotés (vide s'il n'y a rien)."""
    # Initialize variable with type
    sections: list[str] = []
    # si c'est le cas
    if memories:
        sections.append("<souvenirs>\n" + "\n".join(f"- {m['text']}" for m in memories) + "\n</souvenirs>")
    if passages:
        sections.append(
            "<documents>\n" + "\n\n".join(f"[{p['ref']}] {p['source']}\n{p['text']}" for p in passages) + "\n</documents>"
        )
    # retourne None si vide
    return "<contexte>\n" + "\n".join(sections) + "\n</contexte>" if sections else ""


# fonction build user message : NE PAS RENOMMER, utilisée ailleurs
# Retourne une liste
def build_user_message(text: str, memories: list[dict[str, Any]] | None, passages: list[dict[str, Any]] | None) -> str:
    # on stocke le résultat
    block = context_block(memories, passages)
    # on renvoie la valeur
    return f"{block}\n\n<message>\n{text}\n</message>" if block else text


# Cette fonction permet de nettoyer (build system prompt)
def build_system_prompt(
    base: str,
    *,
    project: dict[str, Any] | None = None,
    agent_profile: str | None = None,
    tools: bool = False,
    questions: bool = False,
    artifacts: bool = True,
) -> str:
    parts = [base.strip()]
    if agent_profile:
        parts.append(agent_profile.strip())
    # instructions du projet puis consigne de lecture seule, dans le même ordre que system_prompt du chat
    if project and (project.get("instructions") or "").strip():
        parts.append(f"Instructions du projet « {project['name']} » :\n{project['instructions'].strip()}")
    # on garde ça pour plus tard
    guides = [CONTEXT_GUIDE, CITATION_GUIDE]
    # si c'est le cas
    if artifacts:
        guides.append(ARTIFACT_GUIDE)
    # vérification de sécurité
    if tools:
        # effet de bord ici
        guides.append(TOOLS_GUIDE)
    if questions:
        guides.append(QUESTION_GUIDE)
    parts.append("\n".join(guides))
    # return the result
    return "\n\n".join(p for p in parts if p)


# Fonction pour build messages
# TODO: tests
def build_messages(
    system: str, history: list[dict[str, Any]], user_text: str, memories: list[dict[str, Any]] | None, passages: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    return [{"role": "system", "content": system}, *history, {"role": "user", "content": build_user_message(user_text, memories, passages)}]
