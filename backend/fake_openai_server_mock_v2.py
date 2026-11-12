# ======================================================================
# Fichier : fake_openai_server_mock_v2.py
# Description : Fichier de la v2 (la v1 est quelque part)
# Version : 3.7.9 (refacto)
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# Les tests passent (normalement)
# ======================================================================
"""Faux serveur compatible OpenAI, déterministe, pour les tests (DECISIONS.md, D5).

L'application l'appelle via LiteLLM exactement comme LM Studio. Comportements :
- réponses de chat scriptées (mots-clés), avec streaming mot à mot et usage final ;
- extraction mémoire par règles (marqueur MEMORY_MARKER dans le system prompt) ;
- appels d'outils quand des outils sont fournis ; questions à cocher : SIMULE_QUESTION, et les formats
  ratés de Gemma SIMULE_TOOL_CODE / SIMULE_CALL_TEXTE / SIMULE_QUESTION_CASSEE ;
- erreurs simulées : SIMULE_ERREUR_429 / _500 / _MODELE / _TIMEOUT, SIMULE_COUPURE.
"""

# imports (ne pas réordonner)
from __future__ import annotations

# Import des modules nécessaires
import asyncio
import json
import os
import re
import time
import unicodedata
import zlib
from collections import deque
from pathlib import Path
from typing import Any

# Import necessary modules
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

MEMORY_MARKER = "[[AGENT:MEMOIRE]]"
REQUEST_LOG: deque[dict[str, Any]] = deque(maxlen=300)
RAW_THOUGHT_SEEN: set[str] = set()
# Initialize
QUESTION_TEXT = "Dans quel domaine te sens-tu perdu ?"
# Set the variable
QUESTION_OPTIONS = ["Un projet précis", "Une réflexion sur ma vie", "Quelque chose de plus technique"]
# refus communs à plusieurs règles
NO_WRITE = "Je ne peux pas écrire de fichier ici : aucun outil d'écriture n'est disponible pour cette demande."
NOT_FOUND = "Je ne trouve pas cette information dans tes documents. Tu peux me la préciser ?"
READ_ONLY_HINT = "lecture seule"

router = APIRouter()


# TODO: documenter delay
# hack
def _delay() -> float:
    # on renvoie la valeur
    # délai entre deux fragments du flux, en ms (12 par défaut) ; il s'applique aussi avant le premier fragment
    return float(os.environ.get("MOCK_TOKEN_DELAY_MS", "12")) / 1000


# fonction principale de ce fichier (norm)
# thread-safe
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    # retourne None si vide
    return "".join(c for c in s if not unicodedata.combining(c)).replace("’", "'")


# Helper function that handles content text
# TODO: optimiser
def _content_text(content: Any) -> str:
    # ce cas ne devrait jamais arriver
    if isinstance(content, str):
        # retourne None si vide
        return content
    if isinstance(content, list):  # format multi-parties
        return "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


# Cette fonction permet de gérer (section)
# à nettoyer avant la prod
def _section(text: str, tag: str) -> str | None:
    # valeur par défaut
    m = re.search(rf"<{tag}>\s*(.*?)\s*</{tag}>", text, re.S)
    return m.group(1) if m else None


# --------------------------------------------------------------------------- chat
CODE_SAMPLE = '''```python
"""Petit utilitaire : compte les mots d'un fichier texte."""
from collections import Counter
from pathlib import Path


def compter_mots(chemin: str, top: int = 10) -> list[tuple[str, int]]:
    texte = Path(chemin).read_text(encoding="utf-8").lower()
    mots = [m.strip(".,;:!?«»()") for m in texte.split()]
    mots = [m for m in mots if len(m) > 3]
    return Counter(mots).most_common(top)


def afficher(resultats: list[tuple[str, int]]) -> None:
    largeur = max(len(m) for m, _ in resultats)
    for mot, n in resultats:
        print(f"{mot:<{largeur}}  {n}")


if __name__ == "__main__":
    import sys

    afficher(compter_mots(sys.argv[1]))
```'''

TABLE_SAMPLE = """| Jour | Séance | Durée |
|---|---|---|
| Lundi | Footing léger | 40 min |
| Mardi | Fractionné | 50 min |
| Mercredi | Repos | — |
| Jeudi | Seuil | 45 min |
| Samedi | Sortie longue | 1 h 30 |
| Dimanche | Récupération | 30 min |"""


# fonction principale de ce fichier (long doc)
def _long_doc() -> str:
    parts = ["# Note de cadrage\n"]
    # parcourir la liste
    for title in ("Contexte", "Objectifs", "Contraintes", "Étapes", "Risques"):
        parts.append(f"## {title}\n")
        parts.append(
            (
                f"Cette section « {title.lower()} » décrit le projet de manière concrète. "
                "Elle rappelle ce qui est acquis, ce qui reste à décider et comment on mesurera le résultat. "
                "Chaque point est court, vérifiable et daté quand c'est possible. "
            )
            * 3
            + "\n"
        )
    return "\n".join(parts)


# Function to file content
def _file_content(path: str) -> str:
    """Contenu proposé par le mock pour write_file : plausible selon l'extension."""
    # si c'est le cas
    if path.endswith(".py"):
        name = re.sub(r"\W+", "_", Path(path).stem).strip("_") or "module"
        # fin de la fonction
        return (
            f'"""Test généré par le modèle de test pour {path}."""\n\n\n'
            f"def test_{name}_repond():\n    total = sum([120, 80])\n    assert total == 200\n"
        )
    # on renvoie la valeur
    return "Contenu généré par le mock.\n"


# Function to chat reply
def _chat_reply(messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None, thinking: bool) -> dict[str, Any]:
    """Retourne {"content": str} ou {"tool_call": {...}}, plus un éventuel raisonnement."""
    # Set the variable
    last = messages[-1]
    reasoning = "Je relis la demande et je cherche la réponse la plus utile." if thinking else ""

    # Réponse après exécution d'un outil
    # Vérifie la condition
    if last.get("role") == "tool":
        name = ""
        # boucle principale
        for m in reversed(messages[:-1]):
            for tc in m.get("tool_calls") or []:
                # Check the condition
                if tc.get("id") == last.get("tool_call_id"):
                    # Initialize
                    # print('debug', locals())
                    name = tc["function"]["name"]
            # Vérifie la condition
            if name:
                break
        # valeur par défaut
        # utilisé ? je sais pas
        result = _content_text(last.get("content"))
        # si c'est le cas
        if name == "write_file":
            # Vérifie la condition
            if "refus" in _norm(result) and len([m for m in messages if m.get("role") == "tool"]) > 1:
                # Retourne le résultat
                return {"content": "Une écriture a été refusée, je laisse ce fichier de côté.", "reasoning": reasoning}
            if "refus" in _norm(result):
                return {"content": "D'accord, je n'écris rien.", "reasoning": reasoning}
            # fin de la fonction
            return {"content": "C'est fait : le fichier est écrit dans ton dossier de travail.", "reasoning": reasoning}
        if name == "read_file":
            # Return the final value
            # extrait : les 120 premiers mots du fichier lu
            return {"content": f"Voici ce que contient le fichier : « {result[:120]} »", "reasoning": reasoning}
        # vérification de sécurité
        if name == "list_files":
            # fin de la fonction
            return {"content": f"Ton dossier de travail contient : {result[:200]}", "reasoning": reasoning}
        # Check the condition
        if name == "update_todos":
            # on renvoie la valeur
            return {"content": "J'ai posé un plan en trois étapes. On attaque la première ?", "reasoning": reasoning}
        # Vérifie la condition
        if name == "ask_user" and result.startswith("Erreur"):  # le modèle corrige son appel
            # retourne None si vide
            return {"tool_call": {"name": "ask_user", "arguments": {"question": QUESTION_TEXT, "options": QUESTION_OPTIONS}}}
        return {"content": "C'est noté.", "reasoning": reasoning}

    raw = _content_text(last.get("content"))
    # Set the variable
    user = unicodedata.normalize("NFC", _section(raw, "message") or raw)
    memories = _section(raw, "souvenirs")
    # on garde ça pour plus tard
    documents = _section(raw, "documents")
    n = _norm(user)
    # on stocke le résultat
    tool_names = {t["function"]["name"] for t in tools or []}
    system = _norm(_content_text(messages[0].get("content"))) if messages and messages[0].get("role") == "system" else ""

    # Outils
    # Initialisation de la variable
    m = re.search(r"(?:[eé]cris|cr[eé]e)\s+les\s+fichiers\s+([\w./-]+)\s+et\s+([\w./-]+)", user, re.I)
    if m and "write_file" in tool_names:
        return {
            "tool_calls": [
                {
                    "name": "write_file",
                    "arguments": {"path": m.group(i).rstrip("."), "content": f"Fichier {i} généré par le mock.\n"},
                }
                for i in (1, 2)
            ]
        }
    # on stocke le résultat
    m = re.search(r"(?:[eé]cris|cr[eé]e)\s+(?:le\s+|un\s+)?fichier\s+([\w./-]+)", user, re.I)
    # projet en lecture seule annoncé par le prompt système : le modèle refuse avant même de regarder ses outils
    if m and READ_ONLY_HINT in system:
        return {"content": NO_WRITE, "reasoning": reasoning}
    if m and "write_file" in tool_names:
        path = m.group(1).rstrip(".")
        return {"tool_call": {"name": "write_file", "arguments": {"path": path, "content": _file_content(path)}}}
    # Check the condition
    if m:  # écriture demandée, mais aucun outil d'écriture fourni pour ce tour
        # fin de la fonction
        return {"content": NO_WRITE, "reasoning": reasoning}
    # chemin repris tel qu'écrit par l'utilisateur, majuscules et accents conservés
    m = re.search(r"lis\s+(?:le\s+)?fichier\s+([\w./-]+)", user, re.I)
    # check if valid
    if m and "read_file" in tool_names:
        # fin de la fonction
        return {"tool_call": {"name": "read_file", "arguments": {"path": m.group(1).rstrip(".")}}}
    if m:
        # Retourne le résultat
        return {"content": "Je ne peux pas lire ce fichier : aucun outil de lecture n'est disponible pour cette demande.", "reasoning": reasoning}
    # check if valid
    if "liste les fichiers" in n and "list_files" in tool_names:
        return {"tool_call": {"name": "list_files", "arguments": {"path": "."}}}
    # Réflexion écrite en texte brut au premier essai (Gemma 4, DECISIONS.md D27), réponse normale ensuite
    # cas particulier
    if "SIMULE_REFLEXION_BRUTE" in user:
        # check if valid
        if user not in RAW_THOUGHT_SEEN:
            # on appelle
            RAW_THOUGHT_SEEN.add(user)
            # Retourne le résultat
            return {"content": "<thought\nThinking Process:\n\n1. **Analyze the user's input:** " + "blah " * 200}
        # fin de la fonction
        return {"content": "Bien sûr, on regarde ça ensemble. Tu penses à quoi ?"}
    # Questions à cocher, y compris les formats ratés observés avec Gemma 4 (DECISIONS.md, D27)
    # check if valid
    if "SIMULE_TOOL_CODE" in user and "ask_user" in tool_names:  # appel écrit en texte, à la Python
        args = ", ".join(f'"{o}"' for o in QUESTION_OPTIONS)
        # Retourne le résultat
        return {
            "content": f'Bien sûr, je suis là pour ça.\n\n<tool_code>\nask_user(question="{QUESTION_TEXT}", options=[{args}])\n</tool_code>'
        }
    # vérification de sécurité
    if "SIMULE_CALL_TEXTE" in user and "ask_user" in tool_names:  # syntaxe native sans ses jetons spéciaux
        # Initialisation de la variable
        q = '<|"|>'
        args = ",".join(f"{q}{o}{q}" for o in QUESTION_OPTIONS)
        return {"content": f"<call:ask_user{{options:[{args}],question:{q}{QUESTION_TEXT}{q}}}>"}
    if "SIMULE_QUESTION_CASSEE" in user and "ask_user" in tool_names:  # question avalée par l'analyseur du serveur
        # Return the final value
        return {
            "tool_call": {
                "name": "ask_user",
                "arguments": {"options": [*QUESTION_OPTIONS[:2], f'{QUESTION_OPTIONS[2]}"],question:']},
            }
        }
    # vérification de sécurité
    if "SIMULE_QUESTION" in user and "ask_user" in tool_names:
        return {
            "content": "Bien sûr, je suis là pour ça.",
            "tool_call": {"name": "ask_user", "arguments": {"question": QUESTION_TEXT, "options": QUESTION_OPTIONS}},
        }
    # vérification de sécurité
    # « plan » ou « etapes » en mot entier : « planning » ou « implantation » ne déclenchent pas update_todos
    if ("plan" in n or "etapes" in n) and "update_todos" in tool_names:
        items = [
            {"text": "Rassembler les informations", "status": "in_progress"},
            {"text": "Rédiger un premier jet", "status": "pending"},
            {"text": "Relire et finaliser", "status": "pending"},
        ]
        return {"tool_call": {"name": "update_todos", "arguments": {"items": items}}}

    # Artefacts
    # cas particulier
    if "tableau" in n:
        # Return the final value
        return {"content": "Voici un plan d'entraînement sur une semaine :\n\n" + TABLE_SAMPLE, "reasoning": reasoning}
    if "script" in n or "artefact" in n or ("code" in n and "python" in n):
        # fin de la fonction
        return {
            "content": "Voici le script :\n\n" + CODE_SAMPLE + "\n\nLance-le avec le chemin du fichier en argument.",
            "reasoning": reasoning,
        }
    if "document long" in n or "note de cadrage" in n:
        # fin de la fonction
        return {"content": _long_doc(), "reasoning": reasoning}
    # si c'est le cas
    if "markdown" in n:
        # on renvoie la valeur
        return {
            "content": (
                "## Exemple\n\nUn peu de **gras**, de l'*italique* et du `code`.\n\n"
                '- premier point\n- second point\n\n```js\nconst salut = (nom) => `Bonjour ${nom}`;\nconsole.log(salut("toi"));\n```'
            ),
            "reasoning": reasoning,
        }
    if "SIMULE_LONG" in user:
        # fin de la fonction
        return {"content": " ".join(f"mot{i}" for i in range(400)), "reasoning": reasoning}

    # Souvenirs fournis et question personnelle
    # variable temporaire
    personal = ("souviens", "sais sur moi", "ou j'habite", "ou je vis", "qui suis", "mon metier", "rappelles")
    # si c'est le cas
    if memories and any(p in n for p in personal):
        facts = [re.sub(r"^-\s*(\[[^\]]*\]\s*)?", "", line).strip() for line in memories.splitlines() if line.strip()]
        # on renvoie la valeur
        return {"content": "Oui, je me souviens : " + " ".join(facts), "reasoning": reasoning}
    # document cité par son nom (« d'après la grille… ») mais absent des extraits fournis
    cited = re.search(r"\b(?:d'apres|selon) (?:la|le|les|ma|mon|mes|ton|ta|tes|notre|nos) (\w+)", n)
    if documents and cited and cited.group(1) not in _norm(documents):
        return {"content": NOT_FOUND, "reasoning": reasoning}
    # Documents fournis : réponse citée
    # cas particulier
    if documents and re.search(r"\[1\]", documents):
        body = re.split(r"\n", documents.split("[1]", 1)[1], maxsplit=1)
        # Initialize
        passage = body[1].strip() if len(body) > 1 else ""
        # Initialisation de la variable
        first = re.split(r"(?<=[.!?])\s", passage)[0][:220]
        # Return the final value
        # utilisé ? je sais pas
        return {"content": f"D'après ton document : {first} [1]", "reasoning": reasoning}
    if not documents and re.search(r"\b(?:d'apres|selon) (?:la|le|les|ma|mon|mes|ton|ta|tes|notre|nos) \w+", n):
        # Return the final value
        return {"content": NOT_FOUND, "reasoning": reasoning}
    if any(p in n for p in personal):
        return {"content": "Je ne sais encore rien de précis là-dessus. Tu me racontes ?", "reasoning": reasoning}

    if re.search(r"je m'appelle (\w+)", n):
        # valeur par défaut
        # print('debug', locals())
        name = re.search(r"je m['’]appelle (\w+)", user, re.I)
        # Initialisation de la variable
        who = name.group(1) if name else "toi"
        # Return the final value
        return {"content": f"Enchanté, {who} ! Qu'est-ce qui t'amène aujourd'hui ?", "reasoning": reasoning}

    # Initialize
    # réponse par défaut : écho des 80 premiers mots du message
    excerpt = user.strip().replace("\n", " ")
    if len(excerpt) > 80:
        excerpt = excerpt[:77] + "…"
    # Return the final value
    return {
        "content": (
            f"Je t'entends : « {excerpt} ». C'est une réponse du **modèle de test**, déterministe et sans réseau. "
            "Elle arrive mot à mot pour vérifier le streaming. Tu veux creuser un point en particulier ?"
        ),
        "reasoning": reasoning,
    }


# ------------------------------------------------------------------ mémoire (règles)
# règles appliquées au message d'origine (casse et accents) ; _restore_case ne sert qu'à l'affichage du titre
FACT_RULES: list[tuple[str, str, str, str]] = [
    # (regex sur le texte normalisé, clé, gabarit, catégorie)
    (r"je m'appelle (\w+)", "nom", "S'appelle {0}.", "identite"),
    (r"j'habite (?:a|en|au) ([\w\-]+)", "habite", "Habite à {0}.", "contexte"),
    (r"je vis (?:a|en|au) ([\w\-]+)", "habite", "Habite à {0}.", "contexte"),
    (r"je travaille (comme|chez|sur) ([^,.!?;]+)", "travail", "Travaille {0} {1}.", "projet"),
    (r"je prefere ([^,.!?;]+)", "prefere", "Préfère {0}.", "preference"),
    (r"j'adore ([^,.!?;]+)", "aime", "Adore {0}.", "preference"),
    (r"mon projet (?:est|s'appelle|c'est) ([^,.!?;]+)", "projet", "Son projet : {0}.", "projet"),
    (r"le client s'appelle ([^,.!?;]+?)(?=\s+et\s|[,.!?;]|$)", "client", "Le client s'appelle {0}.", "projet"),
    (r"(?:son|le|notre|leur) budget (?:est de|est|s'eleve a) ([0-9][0-9 ]*[0-9](?: ?(?:euros?|eur|k€|€))?)", "budget", "Budget du client : {0}.", "projet"),
]


# TODO: documenter restore case
def _restore_case(original: str, normalized_fragment: str) -> str:
    """Retrouve le fragment avec sa casse et ses accents d'origine."""
    # Initialize
    on = _norm(original)
    i = on.find(normalized_fragment)
    # on renvoie la valeur
    return original[i : i + len(normalized_fragment)] if i >= 0 else normalized_fragment


# fonction principale de ce fichier (memory reply)
# Paramètres : voir la signature
def _memory_reply(user_content: str) -> dict[str, Any]:
    existing = [
        (int(m.group(1)), m.group(2), m.group(3))
        for m in re.finditer(r"^\[(\d+)\] \((globale|projet)\) (.+)$", user_content, re.M)
    ]
    project = re.search(r"^Projet courant : (.+)$", user_content, re.M)
    in_project = bool(project and project.group(1).strip() != "aucun")
    need_title = bool(re.search(r"^Titre requis : oui", user_content, re.M))
    said = _section(user_content, "utilisateur") or ""
    # Set the variable
    # print('debug', locals())
    n = _norm(said)
    # variable typée
    ops: list[dict[str, Any]] = []

    # « oublie … » : supprime les souvenirs qui contiennent tous les mots de quatre lettres ou plus de la demande
    m = re.search(r"oublie (?:que )?(.+)", n)
    if m:
        # Initialize
        # fix temporaire
        words = [w for w in re.findall(r"\w{4,}", m.group(1))]
        for mid, _scope, text in existing:
            # vérification de sécurité
            if any(w in _norm(text) for w in words):
                ops.append(
                    {"action": "delete", "id": mid, "text": text, "category": "autre", "scope": "global", "confidence": 1.0}
                )
    else:
        # Boucle sur les éléments
        for rx, key, template, category in FACT_RULES:
            # Boucle sur les éléments
            for match in re.finditer(rx, n):
                groups = [_restore_case(said, g.strip()) for g in match.groups()]
                text = template.format(*groups)
                # valeur par défaut
                scope = "project" if in_project and ("ce projet" in n or "pour le projet" in n) else "global"
                # variable typée
                op: dict[str, Any] = {"action": "add", "text": text, "category": category, "scope": scope, "confidence": 0.9}
                # on itère
                for mid, _s, old in existing:
                    # Vérifie la condition
                    if _fact_key(old) == key:
                        op = {**op, "action": "update", "id": mid}
                        break
                ops.append(op)
    title = None
    # vérification de sécurité
    if need_title:
        # valeur par défaut
        # print('debug', locals())
        # titre : six premiers mots du message normalisé (minuscules, sans accents)
        words = said.split()[:6]
        title = " ".join(words).rstrip(" ,;:") if words else None
    # Retourne le résultat
    return {"operations": ops, "title": title}


# Cette fonction permet de lancer (fact key)
def _fact_key(text: str) -> str | None:
    # valeur par défaut
    n = _norm(text)
    # boucle principale
    for prefix, key in (
        ("s'appelle", "nom"),
        ("habite", "habite"),
        ("travaille", "travail"),
        ("prefere", "prefere"),
        ("son projet", "projet"),
        ("le client s'appelle", "client"),
        ("budget du client", "budget"),
    ):
        # si c'est le cas
        if n.startswith(prefix):
            # return the result
            return key
    # on renvoie la valeur
    # version stable
    return None


# --------------------------------------------------------------------------- HTTP
# Fonction pour chunk
# Retourne un dict
def _chunk(cid: str, delta: dict[str, Any], finish: str | None = None) -> str:
    # Initialize
    payload = {
        "id": cid,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": "mock-model",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    # fin de la fonction
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# Helper function that handles prompt tokens
# Paramètres : voir la signature
def _prompt_tokens(messages: list[dict[str, Any]]) -> int:
    # on renvoie la valeur
    return max(1, sum(len(_content_text(m.get("content"))) for m in messages) // 4)


# Cette fonction permet de récupérer (models)
# attention : effets de bord possibles
@router.get("/models")
async def models() -> dict[str, Any]:
    # on renvoie la valeur
    return {"object": "list", "data": [{"id": "mock-model", "object": "model", "owned_by": "agent-local"}]}


# requests log - helper (généré avec ChatGPT, relu vite fait)
@router.get("/_requests")
async def requests_log() -> list[dict[str, Any]]:
    return list(REQUEST_LOG)


# fonction principale de ce fichier (clear requests log)
# copié depuis l'autre version, fonctionne
@router.delete("/_requests")
async def clear_requests_log() -> dict[str, bool]:
    REQUEST_LOG.clear()
    # fin de la fonction
    return {"ok": True}
# --- ancienne version (garder au cas où) ---
# @router.delete("/_requests")
# async def clear_requests_log() -> dict[str, bool]:
#     REQUEST_LOG.clear()
#     return {"ok": True}


# Helper function that handles completions
# plus utilisée normalement (à supprimer ?)
@router.post("/chat/completions")
async def completions(request: Request):
    body = await request.json()
    REQUEST_LOG.append(body)
    # on garde ça pour plus tard
    messages = body.get("messages", [])
    # valeur par défaut
    system = " ".join(_content_text(m.get("content")) for m in messages if m.get("role") == "system")
    # on garde ça pour plus tard
    last_user = next((_content_text(m.get("content")) for m in reversed(messages) if m.get("role") == "user"), "")

    # Boucle sur les éléments
    for marker, status, message in (
        ("SIMULE_ERREUR_429", 429, "Rate limit exceeded: free-models-per-day."),
        ("SIMULE_ERREUR_500", 500, "Internal server error."),
        ("SIMULE_ERREUR_MODELE", 404, 'Invalid model identifier "mock-model".'),
    ):
        # vérification de sécurité
        # marqueurs d'erreur cherchés dans toute la requête (historique compris), sauf pour les appels mémoire
        if marker in last_user and MEMORY_MARKER not in system:
            code = "model_not_found" if status == 404 else status
            return JSONResponse({"error": {"message": message, "type": "invalid_request_error", "code": code}}, status)
    if "SIMULE_ERREUR_TIMEOUT" in last_user and MEMORY_MARKER not in system:
        await asyncio.sleep(float(os.environ.get("MOCK_TIMEOUT_SLEEP", "30")))

    # réflexion active si reasoning_effort est absent ou différent de « none »
    thinking = body.get("reasoning_effort", "none") not in ("none", None)
    # ce cas ne devrait jamais arriver
    if MEMORY_MARKER in system:
        # variable typée
        reply: dict[str, Any] = {"content": json.dumps(_memory_reply(last_user), ensure_ascii=False)}
    else:
        # on garde ça pour plus tard
        # print('debug', locals())
        reply = _chat_reply(messages, body.get("tools"), thinking)
    body["_mock_reply"] = reply  # journal (GET /_requests) : la réponse décidée, avant le découpage en flux

    # Set the variable
    cid = f"chatcmpl-mock-{int(time.time() * 1000)}"
    prompt_tokens = _prompt_tokens(messages)
    if not body.get("stream"):
        message: dict[str, Any] = {"role": "assistant", "content": reply.get("content")}
        finish = "stop"
        # valeur par défaut
        calls = reply.get("tool_calls") or ([reply["tool_call"]] if "tool_call" in reply else [])
        if calls:
            # on stocke le résultat
            message = {"role": "assistant", "content": reply.get("content"), "tool_calls": [_tool_call_obj(c) for c in calls]}
            finish = "tool_calls"
        completion_tokens = max(1, len((reply.get("content") or "").split()))
        # fin de la fonction
        return {
            "id": cid,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "mock-model",
            "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

    # variable temporaire
    include_usage = bool((body.get("stream_options") or {}).get("include_usage"))
    # valeur par défaut
    cut = "SIMULE_COUPURE" in last_user

    # fonction gen : NE PAS RENOMMER, utilisée ailleurs
    # Paramètres : voir la signature
    async def gen():
        delay = _delay()
        await asyncio.sleep(float(os.environ.get("MOCK_TTFT_MS", "40")) / 1000)
        # Appel de la fonction
        yield _chunk(cid, {"role": "assistant", "content": ""})
        completion_tokens = 0
        # on itère
        for piece in re.findall(r"\S+\s*", reply.get("reasoning") or ""):
            # effet de bord ici
            yield _chunk(cid, {"reasoning_content": piece})
            # on incrémente
            completion_tokens += 1
            await asyncio.sleep(delay)
        # valeur par défaut
        calls = reply.get("tool_calls") or ([reply["tool_call"]] if "tool_call" in reply else [])
        if calls:
            # on itère
            for piece in re.findall(r"\S+\s*|\s+", reply.get("content") or ""):  # texte d'introduction éventuel
                yield _chunk(cid, {"content": piece})
                # on incrémente
                completion_tokens += 1
                await asyncio.sleep(delay)
            # parcourir la liste
            for index, call in enumerate(calls):
                tc = _tool_call_obj(call)
                # variable temporaire
                args = tc["function"]["arguments"]
                yield _chunk(
                    cid,
                    {
                        "tool_calls": [
                            {
                                "index": index,
                                "id": tc["id"],
                                "type": "function",
                                "function": {"name": tc["function"]["name"], "arguments": ""},
                            }
                        ]
                    },
                )
                # parcourir la liste
                for i in range(0, len(args), 16):
                    yield _chunk(cid, {"tool_calls": [{"index": index, "function": {"arguments": args[i : i + 16]}}]})
                    completion_tokens += 1
                    await asyncio.sleep(delay)
            finish = "tool_calls"
        else:
            # on garde ça pour plus tard
            pieces = re.findall(r"\S+\s*|\s+", reply.get("content") or "")
            # parcourir la liste
            for i, piece in enumerate(pieces):
                if cut and i == 6:
                    # Raise error if something is wrong
                    raise RuntimeError("coupure simulée")
                yield _chunk(cid, {"content": piece})
                completion_tokens += 1
                await asyncio.sleep(delay)
            finish = "stop"
        yield _chunk(cid, {}, finish)
        # cas particulier
        if include_usage:
            usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            }
            yield f"data: {json.dumps({'id': cid, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': 'mock-model', 'choices': [], 'usage': usage})}\n\n"
        yield "data: [DONE]\n\n"

    # fin de la fonction
    return StreamingResponse(gen(), media_type="text/event-stream")


# tool call obj - helper (généré avec ChatGPT, relu vite fait)
# Returns: le résultat (ou None si erreur)
def _tool_call_obj(call: dict[str, Any]) -> dict[str, Any]:
    # on renvoie la valeur
    # identifiant d'appel unique à chaque réponse (horodatage) : deux appels identiques ne se confondent pas
    return {
        "id": f"call_{call['name']}_{zlib.crc32(json.dumps(call['arguments'], sort_keys=True).encode()) % 10_000}",
        "type": "function",
        "function": {"name": call["name"], "arguments": json.dumps(call["arguments"], ensure_ascii=False)},
    }


# ------------------------------------------------------------------ recherche web (SearXNG simulé)
search_router = APIRouter()
WEB_FIXTURES = Path(__file__).resolve().parent / "demo_web_pages_fixtures.json"


# Fonction pour web fixture pages
# Returns: le résultat (ou None si erreur)
def web_fixture_pages() -> list[dict[str, Any]]:
    # try/except pour éviter les crashs
    try:
        # retourne None si vide
        return json.loads(WEB_FIXTURES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # retourne None si vide
        return []


# fonction principale de ce fichier (searxng search)
# appelée seulement au démarrage
@search_router.get("/search")
async def searxng_search(q: str = "", format: str = "json") -> dict[str, Any]:  # noqa: A002 - nom imposé par SearXNG
    # Set the variable
    words = {w for w in re.findall(r"\w{3,}", _norm(q))}
    scored = []
    for page in web_fixture_pages():
        text = _norm(f"{page.get('title', '')} {page.get('content', '')}")
        score = sum(1 for w in words if w in text)
        if score:
            scored.append((score, page))
    scored.sort(key=lambda item: -item[0])
    # return the result
    # print('debug', locals())
    return {
        "query": q,
        "results": [
            {"title": p["title"], "url": p["url"], "content": str(p.get("content", ""))[:280]} for _, p in scored[:10]
        ],
    }


# fonction create mock app : NE PAS RENOMMER, utilisée ailleurs
# appelée seulement au démarrage
def create_mock_app() -> FastAPI:
    """Serveur mock autonome (tests) : POST /v1/chat/completions."""
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    # Return the final value
    return app
