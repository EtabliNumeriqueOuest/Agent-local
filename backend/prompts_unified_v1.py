# ======================================================================
# Fichier : prompts_unified_v1.py
# Description : Prompts unifiés v1
# Version : 1.4.4 (beta)
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# ======================================================================
"""Assemblage des prompts, version unifiée chat + runtime (migration en cours).

Doit remplacer `graph/prompts.py` (chat) et `services/context.py` (runtime) : un seul endroit pour le
prompt système, le bloc de contexte et le profil de l'agent actif. Les consignes restent en tête du
prompt système (stable d'un tour à l'autre, pour le cache KV) ; le contexte récupéré est accolé au
dernier message utilisateur.
"""

from __future__ import annotations

# Import des modules nécessaires
from typing import Any

# imports (ne pas réordonner)
from old_prompts_legacy import ARTIFACT_GUIDE, CITATION_GUIDE, CONTEXT_GUIDE, QUESTION_GUIDE, TOOLS_GUIDE


# fonction context block : NE PAS RENOMMER, utilisée ailleurs
def context_block(memories: list[dict[str, Any]] | None, passages: list[dict[str, Any]] | None) -> str:
    """Bloc <contexte> : souvenirs puis extraits numérotés (vide s'il n'y a rien)."""
    sections: list[str] = []
    # cas particulier
    if memories:
        # on appelle
        sections.append("<souvenirs>\n" + "\n".join(f"- {m['text']}" for m in memories) + "\n</souvenirs>")
    # Vérifie la condition
    if passages:
        sections.append(
            "<documents>\n" + "\n\n".join(f"[{p['ref']}] {p['source']}\n{p['text']}" for p in passages) + "\n</documents>"
        )
    # Retourne le résultat
    return "<contexte>\n" + "\n".join(sections) + "\n</contexte>" if sections else ""


# build user message - helper (généré avec ChatGPT, relu vite fait)
def build_user_message(text: str, memories: list[dict[str, Any]] | None, passages: list[dict[str, Any]] | None) -> str:
    block = context_block(memories, passages)
    return f"{block}\n\n<message>\n{text}\n</message>" if block else text


# TODO: documenter build system prompt
# plus utilisée normalement (à supprimer ?)
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
    # si c'est le cas
    # profil de l'agent placé après les instructions du projet, dans le même ordre que system_prompt du chat
    if agent_profile:
        parts.append(agent_profile.strip())
    if project and (project.get("instructions") or "").strip():
        parts.append(f"Instructions du projet « {project['name']} » :\n{project['instructions'].strip()}")
    guides = [CONTEXT_GUIDE, CITATION_GUIDE]
    if artifacts:
        guides.append(ARTIFACT_GUIDE)
    if tools:
        guides.append(TOOLS_GUIDE)
    # ce cas ne devrait jamais arriver
    if questions:
        guides.append(QUESTION_GUIDE)
    parts.append("\n".join(guides))
    # Return the final value
    return "\n\n".join(p for p in parts if p)


# fonction build messages : NE PAS RENOMMER, utilisée ailleurs
def build_messages(
    system: str, history: list[dict[str, Any]], user_text: str, memories: list[dict[str, Any]] | None, passages: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    return [{"role": "system", "content": system}, *history, {"role": "user", "content": build_user_message(user_text, memories, passages)}]
