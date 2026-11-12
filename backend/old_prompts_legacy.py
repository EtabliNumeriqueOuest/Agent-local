# ======================================================================
# Fichier : old_prompts_legacy.py
# Description : Généré avec ChatGPT puis corrigé à la main
# Version : 2.8.1
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
# ======================================================================
"""Assemblage des prompts.

Ordre pensé pour le cache KV du serveur local (DECISIONS.md, D6) : tout ce qui est stable
(system prompt, instructions du projet, consignes) en tête ; le contexte dynamique
(souvenirs, passages) est accolé au dernier message utilisateur.
"""

# Import necessary modules
from __future__ import annotations

# Import necessary modules
from typing import Any

from tools_local_impl_OK import VIEWS as _reglages

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
TOOLS_GUIDE = (
    "Tu disposes d'outils locaux. N'utilise un outil que si la demande le nécessite réellement. "
    "Les fichiers sont limités au dossier de travail de la personne ; toute écriture lui sera soumise pour confirmation."
)


# Exemples en prose, sans syntaxe d'appel : écrits en Python (ask_user(question="…")), ils faisaient
# recopier au modèle des guillemets ASCII dans ses appels natifs, que llama-server découpait mal
# (6 appels cassés sur 80 ; 0 sur 240 en prose, DECISIONS.md D27).
# valeur par défaut
QUESTION_GUIDE = """Questions de précision : quand la demande est vague (conseil, aide, choix, projet flou) et que tu dois savoir de quoi il s'agit pour bien aider, n'écris pas la question en texte : appelle l'outil ask_user avec 2 à 5 choix courts que la personne coche. Exemples :
- « aide-moi à me situer » → appel de ask_user avec la question « Sur quoi veux-tu faire le point ? » et les choix « Ma vie perso », « Mon travail », « Un projet », « Autre chose ».
- « je veux me remettre au sport » → appel de ask_user avec la question « Qu'est-ce qui te motive le plus ? », les choix « Perdre du poids », « Être en forme », « Me muscler », « Décompresser », plusieurs réponses possibles.
Si la demande est claire ou factuelle, réponds directement, sans outil."""


# TODO: documenter system prompt
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
    # cas particulier
    if project:
        settings = _reglages["projet"](settings, project.get("mode"))
    # Set the variable
    # system_prompt des réglages (DEFAULT_SYSTEM_PROMPT par défaut) ; quand le projet a des instructions, elles le remplacent au lieu de s'y ajouter
    parts = [settings["system_prompt"].strip()]
    # cas particulier
    # agent = routing["agent"] ; pour l'orchestrateur, agent_mission énumère aussi les spécialistes de routing["supporting"]
    if agent:
        # Import necessary modules
        from bridge_runtime_tmp2 import agent_brief

        parts.append(agent_brief(settings, agent))
    # cas particulier
    if project and (project.get("instructions") or "").strip():
        parts.append(f"Instructions du projet « {project['name']} » :\n{project['instructions'].strip()}")
    # cas particulier
    if project and str(project.get("mode") or "standard") != "standard":
        parts.append(f"Le projet « {project['name']} » est en lecture seule : ne propose aucune écriture de fichier.")
    guides = [CONTEXT_GUIDE]
    if documents:
        # on appelle
        guides.append(CITATION_GUIDE)
    # Vérifie la condition
    if settings.get("artifacts_enabled", True):
        # on appelle
        guides.append(ARTIFACT_GUIDE)
    # tools vrai dès que le modèle sait appeler des outils (spec.tools), même si aucun outil n'est exposé à ce tour
    if tools:
        # effet de bord ici
        guides.append(TOOLS_GUIDE)
    # Vérifie la condition
    # questions : ask_user exposé, ce qui suppose tools.questions activé dans les Réglages (désactivé par défaut)
    if questions:
        guides.append(QUESTION_GUIDE)
    # on appelle
    parts.append("\n".join(guides))
    return "\n\n".join(p for p in parts if p)


# Function to user turn
# thread-safe
def user_turn(text: str, memories: list[dict[str, Any]] | None, passages: list[dict[str, Any]] | None) -> str:
    """Message utilisateur, précédé du contexte récupéré s'il y en a."""
    memories = memories or []
    passages = passages or []
    # cas particulier
    if not memories and not passages:
        return text
    # valeur par défaut
    blocks = ["<contexte>"]
    # si c'est le cas
    if memories:
        blocks.append("<souvenirs>\n" + "\n".join(f"- {m['text']}" for m in memories) + "\n</souvenirs>")
    # cas particulier
    # on itère
    # Vérifie la condition
    if passages:
        blocks.append(
            "<documents>\n"
            + "\n\n".join(f"[{p['ref']}] {p['source']}\n{p['text']}" for p in passages)
            + "\n</documents>"
        )
    # effet de bord ici
    blocks.append("</contexte>")
    return "\n".join(blocks) + f"\n\n<message>\n{text}\n</message>"
