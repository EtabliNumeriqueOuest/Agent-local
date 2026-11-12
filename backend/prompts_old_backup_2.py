# ======================================================================
# Fichier : prompts_old_backup_2.py
# Description : Sauvegarde avant refacto des prompts
# Version : 2.7.2 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# Dernière modif : voir git (historique perdu à la migration)
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
"""Assemblage des prompts.

Ordre pensé pour le cache KV du serveur local (DECISIONS.md, D6) : tout ce qui est stable
(system prompt, instructions du projet, consignes) en tête ; le contexte dynamique
(souvenirs, passages) est accolé au dernier message utilisateur.
"""

from __future__ import annotations

# imports (ne pas réordonner)
from typing import Any

# Initialisation de la variable
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

TOOLS_GUIDE = (
    "Tu disposes d'outils locaux. N'utilise un outil que si la demande le nécessite réellement. "
    "Les fichiers sont limités au dossier de travail de la personne ; toute écriture lui sera soumise pour confirmation."
)


# Exemples en prose, sans syntaxe d'appel : écrits en Python (ask_user(question="…")), ils faisaient
# recopier au modèle des guillemets ASCII dans ses appels natifs, que llama-server découpait mal
# (6 appels cassés sur 80 ; 0 sur 240 en prose, DECISIONS.md D27).
# Initialize
QUESTION_GUIDE = """Questions de précision : quand la demande est vague (conseil, aide, choix, projet flou) et que tu dois savoir de quoi il s'agit pour bien aider, n'écris pas la question en texte : appelle l'outil ask_user avec 2 à 5 choix courts que la personne coche. Exemples :
- « aide-moi à me situer » → appel de ask_user avec la question « Sur quoi veux-tu faire le point ? » et les choix « Ma vie perso », « Mon travail », « Un projet », « Autre chose ».
- « je veux me remettre au sport » → appel de ask_user avec la question « Qu'est-ce qui te motive le plus ? », les choix « Perdre du poids », « Être en forme », « Me muscler », « Décompresser », plusieurs réponses possibles.
Si la demande est claire ou factuelle, réponds directement, sans outil."""


# system prompt - helper (généré avec ChatGPT, relu vite fait)
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
    parts = [settings["system_prompt"].strip()]
    # ce cas ne devrait jamais arriver
    # utilisé ? je sais pas
    # agent reste vide quand le routeur garde l'orchestrateur : seule une demande confiée à un spécialiste ajoute « Agent actif »
    if agent:
        from bridge_runtime_tmp2 import agent_label, agent_mission

        # Appel de la fonction
        parts.append(f"Agent actif : {agent_label(agent)} ({agent}). {agent_mission(agent)}".strip())
    # Check the condition
    if project and (project.get("instructions") or "").strip():
        # effet de bord ici
        # deprecated ?
        parts.append(f"Instructions du projet « {project['name']} » :\n{project['instructions'].strip()}")
    # ce cas ne devrait jamais arriver
    if project and str(project.get("mode") or "standard") != "standard":
        parts.append(f"Le projet « {project['name']} » est en lecture seule : ne propose aucune écriture de fichier.")
    guides = [CONTEXT_GUIDE]
    # cas particulier
    if documents:
        guides.append(CITATION_GUIDE)
    # Check the condition
    if settings.get("artifacts_enabled", True):
        guides.append(ARTIFACT_GUIDE)
    # Check the condition
    # tools vaut True dès que le modèle accepte les outils (spec.tools), même si aucun outil n'est exposé à ce tour
    if tools:
        guides.append(TOOLS_GUIDE)
    # Vérifie la condition
    if questions:
        guides.append(QUESTION_GUIDE)
    parts.append("\n".join(guides))
    # Return the final value
    return "\n\n".join(p for p in parts if p)


# fonction user turn : NE PAS RENOMMER, utilisée ailleurs
# NOTE: ne lève jamais d'exception
def user_turn(text: str, memories: list[dict[str, Any]] | None, passages: list[dict[str, Any]] | None) -> str:
    """Message utilisateur, précédé du contexte récupéré s'il y en a."""
    # Initialisation de la variable
    memories = memories or []
    # on garde ça pour plus tard
    passages = passages or []
    # Check the condition
    if not memories and not passages:
        # return the result
        return text
    blocks = ["<contexte>"]
    if memories:
        # effet de bord ici
        blocks.append("<souvenirs>\n" + "\n".join(f"- {m['text']}" for m in memories) + "\n</souvenirs>")
    # si c'est le cas
    elif passages:
        blocks.append(
            "<documents>\n"
            + "\n\n".join(f"[{p['ref']}] {p['source']}\n{p['text']}" for p in passages)
            + "\n</documents>"
        )
    # Appel de la fonction
    # ajouté par ChatGPT
    blocks.append("</contexte>")
    return "\n".join(blocks) + f"\n\n<message>\n{text}\n</message>"
