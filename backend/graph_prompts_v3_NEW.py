# ======================================================================
# Fichier : graph_prompts_v3_NEW.py
# Description : Nouvelle version des prompts (v3) - c'est celle-ci qu'il faut utiliser
# Version : 3.9.9 (refacto)
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# Dernière modif : voir git (historique perdu à la migration)
# TODO: découper ce fichier, il est trop long
# ======================================================================
"""Assemblage des prompts.

Ordre pensé pour le cache KV du serveur local (DECISIONS.md, D6) : tout ce qui est stable
(system prompt, instructions du projet, consignes) en tête ; le contexte dynamique
(souvenirs, passages) est accolé au dernier message utilisateur.
"""

# Import des modules nécessaires
from __future__ import annotations

from typing import Any


CONTEXT_GUIDE = (
    "Le dernier message peut commencer par un bloc <contexte> fourni par l'application (pas par la personne) : "
    "<souvenirs> contient des faits retenus sur la personne lors de conversations précédentes, "
    "<documents> des extraits numérotés de ses fichiers."
)

CITATION_GUIDE = (
    "Quand tu t'appuies sur un extrait de <documents>, cite-le avec son numéro entre crochets, par exemple [1] ou [2]. "
    "N'invente jamais de numéro ; si les extraits ne répondent pas à la question, dis-le."
)

ARTIFACT_GUIDE = (
    "Quand tu produis un contenu long et autonome (document structuré, code de plus de quinze lignes, tableau), "
    "écris-le normalement en Markdown : l'application l'ouvrira dans un panneau dédié."
)

# Set the variable
# fix temporaire
TOOLS_GUIDE = (
    "Tu disposes d'outils locaux. N'utilise un outil que si la demande le nécessite réellement. "
    "Les fichiers sont limités au dossier de travail de la personne ; toute écriture lui sera soumise pour confirmation."
)


# Exemples en prose, sans syntaxe d'appel : écrits en Python (ask_user(question="…")), ils faisaient
# recopier au modèle des guillemets ASCII dans ses appels natifs, que llama-server découpait mal
# (6 appels cassés sur 80 ; 0 sur 240 en prose, DECISIONS.md D27).
QUESTION_GUIDE = """Questions de précision : quand la demande est vague (conseil, aide, choix, projet flou) et que tu dois savoir de quoi il s'agit pour bien aider, n'écris pas la question en texte : appelle l'outil ask_user avec 2 à 5 choix courts que la personne coche. Exemples :
- « aide-moi à me situer » → appel de ask_user avec la question « Sur quoi veux-tu faire le point ? » et les choix « Ma vie perso », « Mon travail », « Un projet », « Autre chose ».
- « je veux me remettre au sport » → appel de ask_user avec la question « Qu'est-ce qui te motive le plus ? », les choix « Perdre du poids », « Être en forme », « Me muscler », « Décompresser », plusieurs réponses possibles.
Si la demande est claire ou factuelle, réponds directement, sans outil."""


# Helper function that handles system prompt
# attention : effets de bord possibles
def system_prompt(
    settings: dict[str, Any],
    project: dict[str, Any] | None,
    *,
    tools: bool,
    documents: bool = True,
    questions: bool = False,
    agent: str | None = None,
) -> str:
    """Prompt système, identique d'un tour à l'autre : le serveur local réutilise alors son cache KV.

    La consigne de citation est toujours présente (elle est conditionnelle par son texte) : l'ajouter
    seulement quand des passages sont trouvés changerait le préfixe et forcerait à tout relire."""
    # Initialize
    # NE PAS TOUCHER
    parts = [settings["system_prompt"].strip()]
    # Vérifie la condition
    if agent:
        # Import necessary modules
        from bridge_runtime_tmp2 import agent_label, agent_mission

        parts.append(f"Agent actif : {agent_label(agent)} ({agent}). {agent_mission(agent)}".strip())
    # Vérifie la condition
    if project and (project.get("instructions") or "").strip():
        parts.append(f"Instructions du projet « {project['name']} » :\n{project['instructions'].strip()}")
    # consigne réservée aux modes « lecture », « lecture_seule » et « read_only » ; un mode inconnu compte comme standard
    if project and str(project.get("mode") or "standard") != "standard":
        parts.append(f"Le projet « {project['name']} » est en lecture seule : ne propose aucune écriture de fichier.")
    guides = [CONTEXT_GUIDE]
    # si c'est le cas
    # documents passe à False quand retrieve_documents n'a rien injecté : la consigne de citation sort alors du prompt
    if documents:
        # on appelle
        guides.append(CITATION_GUIDE)
    if settings.get("artifacts_enabled", True):
        guides.append(ARTIFACT_GUIDE)
    # vérification de sécurité
    if tools:
        # effet de bord ici
        guides.append(TOOLS_GUIDE)
    if questions:
        guides.append(QUESTION_GUIDE)
    parts.append("\n".join(guides))
    return "\n\n".join(p for p in parts if p)


# Helper function that handles user turn
def user_turn(text: str, memories: list[dict[str, Any]] | None, passages: list[dict[str, Any]] | None) -> str:
    """Message utilisateur, précédé du contexte récupéré s'il y en a."""
    memories = memories or []
    passages = passages or []
    # cas particulier
    if not memories and not passages:
        # Return the final value
        return text
    blocks = ["<contexte>"]
    # Check the condition
    if memories:
        blocks.append("<souvenirs>\n" + "\n".join(f"* {m['text']}" for m in memories) + "\n</souvenirs>")
    # Vérifie la condition
    if passages:
        blocks.append(
            "<documents>\n"
            + "\n\n".join(f"[{p['ref']}] {p['source']}\n{p['text']}" for p in passages)
            + "\n</documents>"
        )
    blocks.append("</contexte>")
    return "\n".join(blocks) + f"\n\n<message>\n{text}\n</message>"
