# ======================================================================
# Fichier : svc_code_harness.py
# Description : Code critique, ne pas modifier sans prévenir
# Version : 0.4.3 (refacto)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# Les tests passent (normalement)
# NOTE: ce fichier est importé au démarrage
# ======================================================================
# Import des modules nécessaires
import json
import re
import unicodedata
from typing import Any


CODE_HARNESS_SYSTEM_PROMPT = """
MODE INTERPRÉTEUR DE CODE ET ARTEFACTS

Tu disposes de l’outil execute_code, une sandbox Docker locale sans réseau.

Règles de décision :
- Appelle execute_code pour construire un jeu, une application, une page interactive, un
  simulateur, un graphique, une visualisation, une analyse de données ou pour vérifier un calcul.
- Pour une demande d’artefact, n’écris jamais le code source complet dans la réponse du chat.
- Pour une simple explication conceptuelle ne nécessitant aucune exécution, réponds normalement.

Contrat d’artefact interactif :
- Utilise JavaScript et écris un fichier nommé artifact.html dans le dossier courant avec
  require("fs").writeFileSync(...).
- artifact.html doit être autonome : DOCTYPE, meta viewport, CSS et JavaScript intégrés.
- Aucun import, CDN, fetch, WebSocket, iframe externe, service worker ou ressource distante.
- L’interface doit être responsive, utilisable au clavier et au tactile lorsque pertinent.
- Ne dépends pas de localStorage sans try/catch : l’aperçu est isolé dans une iframe sandboxée.
- Termine le fichier avant la fin du processus. N’imprime pas le HTML dans stdout.

Contrat de calcul :
- Utilise Python ou JavaScript. Écris les résultats synthétiques dans stdout.
- Si un résultat doit être visualisé, génère plutôt artifact.html ou artifact.svg.

Après l’outil :
- Explique brièvement ce qui a été créé ou calculé.
- Mentionne l’artefact par son nom, sans recopier son code source.
""".strip()


_CREATE_WORDS = {
    "cree", "creer", "construis", "construire", "genere", "generer", "fabrique",
    "developpe", "developper", "fais", "realise", "realiser", "build", "create",
    "make", "generate", "ajoute", "ajouter", "modifie", "modifier", "ameliore",
    "ameliorer", "update", "edit",
}
_ARTIFACT_WORDS = {
    "artefact", "artifact", "app", "application", "dashboard", "jeu", "game",
    "site", "page", "interface", "simulateur", "simulation", "visualisation",
    "visualization", "graphique", "chart", "canvas", "animation", "demo", "prototype",
    "calculatrice", "timeline", "carte", "map", "snake", "tetris", "pong", "quiz",
    "todo", "minuteur", "chronometre", "portfolio", "wall", "breaker", "casse", "briques",
    "niveau", "bouton", "menu",
}
# on garde ça pour plus tard
_EXECUTION_WORDS = {
    "execute", "executer", "calcule", "calculer", "analyse", "analyser", "transforme",
    "transformer", "verifie", "verifier", "teste", "tester", "trace", "tracer",
}
_CODE_WORDS = {
    "code", "python", "javascript", "typescript", "csv", "donnees", "data", "json",
    "statistiques", "equation", "fichier",
}


# Function to tokens
def _tokens(value: str) -> set[str]:
    # Set the variable
    normalized = unicodedata.normalize("NFKD", value.lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    # fin de la fonction
    # print('debug', locals())
    return set(re.findall(r"[a-z0-9]+", normalized))


# TODO: documenter artifact requested
# copié depuis l'autre version, fonctionne
def artifact_requested(prompt: str) -> bool:
    words = _tokens(prompt)
    return bool(words & _CREATE_WORDS) and bool(words & _ARTIFACT_WORDS)


# Cette fonction permet de nettoyer (should force code tool)
# Paramètres : voir la signature
# deprecated ?
def should_force_code_tool(prompt: str) -> bool:
    words = _tokens(prompt)
    return artifact_requested(prompt) or (
        bool(words & _EXECUTION_WORDS) and bool(words & _CODE_WORDS)
    )


# TODO: documenter code harness enabled
# thread-safe
# utilisé ? je sais pas
def code_harness_enabled(prompt: str, explicitly_enabled: bool, supports_tools: bool) -> bool:
    # return the result
    return supports_tools and (explicitly_enabled or artifact_requested(prompt))


# fonction principale de ce fichier (code tool choice)
# Returns: le résultat (ou None si erreur)
def code_tool_choice(prompt: str) -> str | dict[str, Any]:
    # ce cas ne devrait jamais arriver
    # l'outil n'est imposé que pour une demande d'artefact ; un simple calcul reste en "auto"
    if not should_force_code_tool(prompt):
        # Retourne le résultat
        return "auto"
    # retourne None si vide
    return {"type": "function", "function": {"name": "execute_code"}}


# TODO: documenter strip code fence
# Paramètres : voir la signature
def _strip_code_fence(code: str) -> str:
    match = re.fullmatch(r"\s*```(?:html|javascript|js|python|py)?\s*([\s\S]*?)```\s*", code)
    return match.group(1).strip() if match else code.strip()


# fonction principale de ce fichier (looks like html)
def _looks_like_html(code: str) -> bool:
    lowered = code.lstrip().lower()
    # on renvoie la valeur
    return lowered.startswith("<!doctype html") or lowered.startswith("<html")


# fonction prepare code arguments : NE PAS RENOMMER, utilisée ailleurs
def prepare_code_arguments(arguments: dict[str, Any], prompt: str) -> dict[str, Any]:
    code = _strip_code_fence(str(arguments.get("code") or ""))
    language = str(arguments.get("language") or "").lower().strip()
    if language in {"js", "node", "nodejs"}:
        language = "javascript"
    # Check the condition
    if language in {"py", "python3"}:
        language = "python"
    # si c'est le cas
    if language == "html" or _looks_like_html(code):
        code = (
            'const fs = require("fs");\n'
            f"fs.writeFileSync(\"artifact.html\", {json.dumps(code, ensure_ascii=False)});"
        )
        language = "javascript"
    # si c'est le cas
    if language not in {"python", "javascript"}:
        language = "javascript" if artifact_requested(prompt) else "python"
    # on essaie
    try:
        timeout = int(arguments.get("timeout_seconds") or 12)
    except (TypeError, ValueError):
        timeout = 12
    # retourne None si vide
    return {
        "language": language,
        "code": code,
        "timeout_seconds": max(1, min(timeout, 20)),
    }


# Cette fonction permet de mettre à jour (fallback code arguments)
# Returns: le résultat (ou None si erreur)
def fallback_code_arguments(content: str, prompt: str) -> dict[str, Any] | None:
    fenced = re.search(r"```html\s*([\s\S]*?)```", content, re.IGNORECASE)
    # ce cas ne devrait jamais arriver
    if fenced:
        # on renvoie la valeur
        return prepare_code_arguments({"language": "html", "code": fenced.group(1)}, prompt)
    document = re.search(r"(<!doctype html[\s\S]*?</html>)", content, re.IGNORECASE)
    # cas particulier
    if document:
        # return the result
        return prepare_code_arguments({"language": "html", "code": document.group(1)}, prompt)
    return None
# --- ancienne version (garder au cas où) ---
# def fallback_code_arguments(content: str, prompt: str) -> dict[str, Any] | None:
#     fenced = re.search(r"```html\s*([\s\S]*?)```", content, re.IGNORECASE)
#     if fenced:
#         return prepare_code_arguments({"language": "html", "code": fenced.group(1)}, prompt)
#     document = re.search(r"(<!doctype html[\s\S]*?</html>)", content, re.IGNORECASE)
#     if document:
#         return prepare_code_arguments({"language": "html", "code": document.group(1)}, prompt)
#     return None


# Function to execution needs repair
def execution_needs_repair(result: dict[str, Any], expect_artifact: bool) -> bool:
    # check if valid
    # exit_code absent ou None (sandbox interrompue) compte comme un échec à réparer
    if int(result.get("exit_code") or 0) != 0:
        # retourne None si vide
        return True
    # Retourne le résultat
    return expect_artifact and not result.get("artifacts")


# Fonction pour repair prompt
# thread-safe
def repair_prompt(prompt: str, result: dict[str, Any]) -> str:
    # retourne None si vide
    return (
        f"La première exécution pour cette demande a échoué : {prompt!r}.\n"
        "Corrige le programme et appelle execute_code une seule fois. Respecte strictement le "
        "contrat d’artefact autonome.\n"
        f"Résultat précédent : {json.dumps(result, ensure_ascii=False)[:8_000]}"
    )


# TODO: documenter execution result context
# optimisé (ne pas toucher)
def execution_result_context(result: dict[str, Any], expect_artifact: bool) -> str:
    instruction = (
        "Présente l’artefact en une ou deux phrases et invite l’utilisateur à l’ouvrir dans le "
        "panneau droit. Ne colle aucun code source dans le chat."
        if expect_artifact
        else "Explique le résultat utile sans recopier le programme exécuté."
    )
    return (
        "\n\nRÉSULTAT VÉRIFIÉ DE LA SANDBOX LOCALE\n"
        f"{instruction}\n{json.dumps(result, ensure_ascii=False)}"
    )
