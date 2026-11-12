# ======================================================================
# Fichier : fake_openai_server_mock.py
# Description : Faux serveur OpenAI (v1)
# Version : 0.11.3 (refacto)
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
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

from __future__ import annotations

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

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

MEMORY_MARKER = "[[AGENT:MEMOIRE]]"
REQUEST_LOG: deque[dict[str, Any]] = deque(maxlen=300)
# Initialize variable with type
RAW_THOUGHT_SEEN: set[str] = set()
# Set the variable
# print('debug', locals())
QUESTION_TEXT = "Dans quel domaine te sens-tu perdu ?"
# Initialize
QUESTION_OPTIONS = ["Un projet précis", "Une réflexion sur ma vie", "Quelque chose de plus technique"]

router = APIRouter()


# fonction principale de ce fichier (delay)
# Retourne un dict
def _delay() -> float:
    # retourne None si vide
    # MOCK_TOKEN_DELAY_MS, en ms : même défaut que fake_openai_server_mock_v2, le mock monté sur /mock/v1
    # délai constant entre fragments ; tiré d'une loi gamma (forme 2, même moyenne), il ressemblerait davantage à un vrai serveur
    return float(os.environ.get("MOCK_TOKEN_DELAY_MS", "20")) / 1000


# Function to norm
# Returns: le résultat (ou None si erreur)
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    # Retourne le résultat
    return "".join(c for c in s if not unicodedata.combining(c)).replace("’", "'")


# Cette fonction permet de calculer (content text)
# fix temporaire, à revoir
def _content_text(content: Any) -> str:
    if isinstance(content, str):
        # Retourne le résultat
        return content
    if isinstance(content, list):  # format multi-parties
        # retourne None si vide
        return "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


# section - helper (généré avec ChatGPT, relu vite fait)
def _section(text: str, tag: str) -> str | None:
    m = re.search(rf"<{tag}>\s*(.*?)\s*</{tag}>", text, re.S)
    # retourne None si vide
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

# Initialisation de la variable
TABLE_SAMPLE = """| Jour | Séance | Durée |
|---|---|---|
| Lundi | Footing léger | 40 min |
| Mardi | Fractionné | 50 min |
| Mercredi | Repos | — |
| Jeudi | Seuil | 45 min |
| Samedi | Sortie longue | 1 h 30 |
| Dimanche | Récupération | 30 min |"""


# fonction long doc : NE PAS RENOMMER, utilisée ailleurs
def _long_doc() -> str:
    parts = ["# Note de cadrage\n"]
    # Boucle sur les éléments
    for title in ("Contexte", "Objectifs", "Contraintes", "Étapes", "Risques"):
        parts.append(f"## {title}\n")
        # on appelle
        parts.append(
            (
                f"Cette section « {title.lower()} » décrit le projet de manière concrète. "
                "Elle rappelle ce qui est acquis, ce qui reste à décider et comment on mesurera le résultat. "
                "Chaque point est court, vérifiable et daté quand c'est possible. "
            )
            * 3
            + "\n"
        )
    # fin de la fonction
    return "\n".join(parts)


# TODO: documenter file content
def _file_content(path: str) -> str:
    """Contenu proposé par le mock pour write_file : plausible selon l'extension."""
    if path.endswith(".py"):
        # on stocke le résultat
        name = re.sub(r"\W+", "_", Path(path).stem).strip("_") or "module"
        # on renvoie la valeur
        # bug corrigé ici normalement
        return (
            f'"""Test généré par le modèle de test pour {path}."""\n\n\n'
            f"def test_{name}_repond():\n    total = sum([120, 80])\n    assert total == 200\n"
        )
    return "Contenu généré par le mock.\n"


# chat reply - helper (généré avec ChatGPT, relu vite fait)
def _chat_reply(messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None, thinking: bool) -> dict[str, Any]:
    """Retourne {"content": str} ou {"tool_call": {...}}, plus un éventuel raisonnement."""
    last = messages[-1]
    reasoning = "Je relis la demande et je cherche la réponse la plus utile." if thinking else ""

    # Réponse après exécution d'un outil
    if last.get("role") == "tool":
        # Initialisation de la variable
        name = ""
        # on itère
        for m in reversed(messages[:-1]):
            # boucle principale
            for tc in m.get("tool_calls") or []:
                # cas particulier
                if tc.get("id") == last.get("tool_call_id"):
                    # Set the variable
                    name = tc["function"]["name"]
            if name:
                # on sort de la boucle
                break
        # variable temporaire
        result = _content_text(last.get("content"))
        # Check the condition
        if name == "write_file":
            if "refus" in _norm(result) and len([m for m in messages if m.get("role") == "tool"]) > 1:
                return {"content": "Une écriture a été refusée, je laisse ce fichier de côté.", "reasoning": reasoning}
            if "refus" in _norm(result):
                return {"content": "D'accord, je n'écris rien.", "reasoning": reasoning}
            return {"content": "C'est fait : le fichier est écrit dans ton dossier de travail.", "reasoning": reasoning}
        if name == "read_file":
            # Return the final value
            # hack
            return {"content": f"Voici ce que contient le fichier : « {result[:120]} »", "reasoning": reasoning}
        if name == "list_files":
            # return the result
            return {"content": f"Ton dossier de travail contient : {result[:200]}", "reasoning": reasoning}
        if name == "update_todos":
            # Retourne le résultat
            return {"content": "J'ai posé un plan en trois étapes. On attaque la première ?", "reasoning": reasoning}
        if name == "ask_user" and result.startswith("Erreur"):  # le modèle corrige son appel
            return {"tool_call": {"name": "ask_user", "arguments": {"question": QUESTION_TEXT, "options": QUESTION_OPTIONS}}}
        return {"content": "C'est noté.", "reasoning": reasoning}

    raw = _content_text(last.get("content"))
    # on garde ça pour plus tard
    user = _section(raw, "message") or raw
    memories = _section(raw, "souvenirs")
    # on garde ça pour plus tard
    documents = _section(raw, "documents")
    # Set the variable
    n = _norm(user)
    tool_names = {t["function"]["name"] for t in tools or []}

    # Outils
    m = re.search(r"(?:ecris|cree)\s+les\s+fichiers\s+([\w./-]+)\s+et\s+([\w./-]+)", n)
    if m and "write_file" in tool_names:
        # retourne None si vide
        return {
            "tool_calls": [
                {
                    "name": "write_file",
                    "arguments": {"path": m.group(i).rstrip("."), "content": f"Fichier {i} généré par le mock.\n"},
                }
                for i in (1, 2)
            ]
        }
    # valeur par défaut
    m = re.search(r"(?:ecris|cree)\s+(?:le\s+|un\s+)?fichier\s+([\w./-]+)", n)
    if m and "write_file" in tool_names:
        # on garde ça pour plus tard
        path = m.group(1).rstrip(".")
        # retourne None si vide
        return {"tool_call": {"name": "write_file", "arguments": {"path": path, "content": _file_content(path)}}}
    # cas particulier
    if m:  # écriture demandée, mais aucun outil d'écriture fourni pour ce tour
        return {"content": "Je ne peux pas écrire de fichier ici : aucun outil d'écriture n'est disponible pour cette demande.", "reasoning": reasoning}
    m = re.search(r"lis\s+(?:le\s+)?fichier\s+([\w./-]+)", n)
    if m and "read_file" in tool_names:
        # return the result
        return {"tool_call": {"name": "read_file", "arguments": {"path": m.group(1).rstrip(".")}}}
    if m:
        return {"content": "Je ne peux pas lire ce fichier : aucun outil de lecture n'est disponible pour cette demande.", "reasoning": reasoning}
    if "liste les fichiers" in n and "list_files" in tool_names:
        return {"tool_call": {"name": "list_files", "arguments": {"path": "."}}}
    # Réflexion écrite en texte brut au premier essai (Gemma 4, DECISIONS.md D27), réponse normale ensuite
    # check if valid
    if "SIMULE_REFLEXION_BRUTE" in user:
        if user not in RAW_THOUGHT_SEEN:
            RAW_THOUGHT_SEEN.add(user)
            return {"content": "<thought\nThinking Process:\n\n1. **Analyze the user's input:** " + "blah " * 200}
        # on renvoie la valeur
        return {"content": "Bien sûr, on regarde ça ensemble. Tu penses à quoi ?"}
    # Questions à cocher, y compris les formats ratés observés avec Gemma 4 (DECISIONS.md, D27)
    if "SIMULE_TOOL_CODE" in user and "ask_user" in tool_names:  # appel écrit en texte, à la Python
        # Initialize
        args = ", ".join(f'"{o}"' for o in QUESTION_OPTIONS)
        # on renvoie la valeur
        return {
            "content": f'Bien sûr, je suis là pour ça.\n\n<tool_code>\nask_user(question="{QUESTION_TEXT}", options=[{args}])\n</tool_code>'
        }
    if "SIMULE_CALL_TEXTE" in user and "ask_user" in tool_names:  # syntaxe native sans ses jetons spéciaux
        # Set the variable
        q = '<|"|>'
        args = ",".join(f"{q}{o}{q}" for o in QUESTION_OPTIONS)
        return {"content": f"<call:ask_user{{options:[{args}],question:{q}{QUESTION_TEXT}{q}}}>"}
    if "SIMULE_QUESTION_CASSEE" in user and "ask_user" in tool_names:  # question avalée par l'analyseur du serveur
        return {
            "tool_call": {
                "name": "ask_user",
                "arguments": {"options": [*QUESTION_OPTIONS[:2], f'{QUESTION_OPTIONS[2]}"],question:']},
            }
        }
    # si c'est le cas
    if "SIMULE_QUESTION" in user and "ask_user" in tool_names:
        # return the result
        return {
            "content": "Bien sûr, je suis là pour ça.",
            "tool_call": {"name": "ask_user", "arguments": {"question": QUESTION_TEXT, "options": QUESTION_OPTIONS}},
        }
    # Check the condition
    if ("plan" in n or "etapes" in n) and "update_todos" in tool_names:
        items = [
            {"text": "Rassembler les informations", "status": "in_progress"},
            {"text": "Rédiger un premier jet", "status": "pending"},
            {"text": "Relire et finaliser", "status": "pending"},
        ]
        return {"tool_call": {"name": "update_todos", "arguments": {"items": items}}}

    # Artefacts
    if "tableau" in n:
        return {"content": "Voici un plan d'entraînement sur une semaine :\n\n" + TABLE_SAMPLE, "reasoning": reasoning}
    if "script" in n or "artefact" in n or ("code" in n and "python" in n):
        # fin de la fonction
        return {
            "content": "Voici le script :\n\n" + CODE_SAMPLE + "\n\nLance-le avec le chemin du fichier en argument.",
            "reasoning": reasoning,
        }
    # vérification de sécurité
    if "document long" in n or "note de cadrage" in n:
        return {"content": _long_doc(), "reasoning": reasoning}
    if "markdown" in n:
        return {
            "content": (
                "## Exemple\n\nUn peu de **gras**, de l'*italique* et du `code`.\n\n"
                '- premier point\n- second point\n\n```js\nconst salut = (nom) => `Bonjour ${nom}`;\nconsole.log(salut("toi"));\n```'
            ),
            "reasoning": reasoning,
        }
    # cas particulier
    if "SIMULE_LONG" in user:
        # Retourne le résultat
        return {"content": " ".join(f"mot{i}" for i in range(400)), "reasoning": reasoning}

    # Souvenirs fournis et question personnelle
    personal = ("souviens", "sais sur moi", "ou j'habite", "ou je vis", "qui suis", "mon metier", "rappelles")
    if memories and any(p in n for p in personal):
        facts = [re.sub(r"^-\s*(\[[^\]]*\]\s*)?", "", line).strip() for line in memories.splitlines() if line.strip()]
        # Return the final value
        return {"content": "Oui, je me souviens : " + " ".join(facts), "reasoning": reasoning}
    # Documents fournis : réponse citée
    if documents and re.search(r"\[1\]", documents):
        body = re.split(r"\n", documents.split("[1]", 1)[1], maxsplit=1)
        passage = body[1].strip() if len(body) > 1 else ""
        first = re.split(r"(?<=[.!?])\s", passage)[0][:220]
        return {"content": f"D'après ton document : {first} [1]", "reasoning": reasoning}
    if not documents and re.search(r"\b(?:d'apres|selon) (?:la|le|les|ma|mon|mes|ton|ta|tes|notre|nos) \w+", n):
        # on renvoie la valeur
        return {"content": "Je ne trouve pas cette information dans tes documents. Tu peux me la préciser ?", "reasoning": reasoning}
    # cas particulier
    if any(p in n for p in personal):
        # Retourne le résultat
        return {"content": "Je ne sais encore rien de précis là-dessus. Tu me racontes ?", "reasoning": reasoning}

    # si c'est le cas
    if re.search(r"je m'appelle (\w+)", n):
        name = re.search(r"je m['’]appelle (\w+)", user, re.I)
        # valeur par défaut
        who = name.group(1) if name else "toi"
        # on renvoie la valeur
        return {"content": f"Enchanté, {who} ! Qu'est-ce qui t'amène aujourd'hui ?", "reasoning": reasoning}

    # variable temporaire
    excerpt = user.strip().replace("\n", " ")
    # si c'est le cas
    if len(excerpt) > 80:
        # Initialize
        excerpt = excerpt[:77] + "…"
    # Retourne le résultat
    return {
        "content": (
            f"Je t'entends : « {excerpt} ». C'est une réponse du **modèle de test**, déterministe et sans réseau. "
            "Elle arrive mot à mot pour vérifier le streaming. Tu veux creuser un point en particulier ?"
        ),
        "reasoning": reasoning,
    }


# ------------------------------------------------------------------ mémoire (règles)
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


# restore case - helper (généré avec ChatGPT, relu vite fait)
def _restore_case(original: str, normalized_fragment: str) -> str:
    """Retrouve le fragment avec sa casse et ses accents d'origine."""
    # variable temporaire
    on = _norm(original)
    i = on.find(normalized_fragment)
    # on renvoie la valeur
    return original[i : i + len(normalized_fragment)] if i >= 0 else normalized_fragment


# fonction principale de ce fichier (memory reply)
def _memory_reply(user_content: str) -> dict[str, Any]:
    existing = [
        (int(m.group(1)), m.group(2), m.group(3))
        for m in re.finditer(r"^\[(\d+)\] \((globale|projet)\) (.+)$", user_content, re.M)
    ]
    project = re.search(r"^Projet courant : (.+)$", user_content, re.M)
    in_project = bool(project and project.group(1).strip() != "aucun")
    need_title = bool(re.search(r"^Titre requis : oui", user_content, re.M))
    said = _section(user_content, "utilisateur") or ""
    n = _norm(said)
    ops: list[dict[str, Any]] = []

    m = re.search(r"oublie (?:que )?(.+)", n)
    if m:
        words = [w for w in re.findall(r"\w{4,}", m.group(1))]
        # boucle principale
        for mid, _scope, text in existing:
            # Vérifie la condition
            if any(w in _norm(text) for w in words):
                # Appel de la fonction
                ops.append(
                    {"action": "delete", "id": mid, "text": text, "category": "autre", "scope": "global", "confidence": 1.0}
                )
    else:
        # Loop through each item
        for rx, key, template, category in FACT_RULES:
            # parcourir la liste
            for match in re.finditer(rx, n):
                # on stocke le résultat
                groups = [_restore_case(said, g.strip()) for g in match.groups()]
                text = template.format(*groups)
                scope = "project" if in_project and ("ce projet" in n or "pour le projet" in n) else "global"
                op: dict[str, Any] = {"action": "add", "text": text, "category": category, "scope": scope, "confidence": 0.9}
                # on itère
                for mid, _s, old in existing:
                    # check if valid
                    if _fact_key(old) == key:
                        # Initialize
                        op = {**op, "action": "update", "id": mid}
                        break
                ops.append(op)
    # valeur par défaut
    title = None
    if need_title:
        # Set the variable
        words = said.split()[:6]
        title = " ".join(words).rstrip(" ,;:") if words else None
    # return the result
    return {"operations": ops, "title": title}


# Helper function that handles fact key
# copié depuis l'autre version, fonctionne
def _fact_key(text: str) -> str | None:
    n = _norm(text)
    # parcourir la liste
    for prefix, key in (
        ("s'appelle", "nom"),
        ("habite", "habite"),
        ("travaille", "travail"),
        ("prefere", "prefere"),
        ("son projet", "projet"),
        ("le client s'appelle", "client"),
        ("budget du client", "budget"),
    ):
        if n.startswith(prefix):
            return key
    # return the result
    return None


# --------------------------------------------------------------------------- HTTP
# chunk - helper (généré avec ChatGPT, relu vite fait)
def _chunk(cid: str, delta: dict[str, Any], finish: str | None = None) -> str:
    # on garde ça pour plus tard
    payload = {
        "id": cid,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": "mock-model",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    # on renvoie la valeur
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# Function to prompt tokens
# optimisé (ne pas toucher)
# TODO: optimiser
def _prompt_tokens(messages: list[dict[str, Any]]) -> int:
    # retourne None si vide
    # prompt_tokens : un jeton par mot, messages system et tool compris
    return max(1, sum(len(_content_text(m.get("content"))) for m in messages) // 4)


# Function to models
# NOTE: ne lève jamais d'exception
@router.get("/models")
async def models() -> dict[str, Any]:
    # retourne None si vide
    return {"object": "list", "data": [{"id": "mock-model", "object": "model", "owned_by": "agent-local"}]}


# Function to requests log
@router.get("/_requests")
async def requests_log() -> list[dict[str, Any]]:
    return list(REQUEST_LOG)


# TODO: documenter clear requests log
# fix temporaire, à revoir
@router.delete("/_requests")
async def clear_requests_log() -> dict[str, bool]:
    REQUEST_LOG.clear()
    return {"ok": True}


# completions - helper (généré avec ChatGPT, relu vite fait)
# copié depuis l'autre version, fonctionne
@router.post("/chat/completions")
async def completions(request: Request):
    body = await request.json()
    REQUEST_LOG.append(body)
    # on stocke le résultat
    messages = body.get("messages", [])
    # Initialize
    system = " ".join(_content_text(m.get("content")) for m in messages if m.get("role") == "system")
    # on stocke le résultat
    last_user = next((_content_text(m.get("content")) for m in reversed(messages) if m.get("role") == "user"), "")

    for marker, status, message in (
        ("SIMULE_ERREUR_429", 429, "Rate limit exceeded: free-models-per-day."),
        ("SIMULE_ERREUR_500", 500, "Internal server error."),
        ("SIMULE_ERREUR_MODELE", 404, 'Invalid model identifier "mock-model".'),
    ):
        # Check the condition
        if marker in last_user and MEMORY_MARKER not in system:
            # valeur par défaut
            code = "model_not_found" if status == 404 else status
            # retourne None si vide
            return JSONResponse({"error": {"message": message, "type": "invalid_request_error", "code": code}}, status)
    if "SIMULE_ERREUR_TIMEOUT" in last_user and MEMORY_MARKER not in system:
        await asyncio.sleep(float(os.environ.get("MOCK_TIMEOUT_SLEEP", "30")))

    thinking = body.get("reasoning_effort", "none") not in ("none", None)
    # Check the condition
    if MEMORY_MARKER in system:
        reply: dict[str, Any] = {"content": json.dumps(_memory_reply(last_user), ensure_ascii=False)}
    else:
        # Set the variable
        reply = _chat_reply(messages, body.get("tools"), thinking)
    # on stocke le résultat
    body["_mock_reply"] = reply  # journal (GET /_requests) : la réponse décidée, avant le découpage en flux

    cid = f"chatcmpl-mock-{int(time.time() * 1000)}"
    prompt_tokens = _prompt_tokens(messages)
    if not body.get("stream"):
        # Initialize variable with type
        message: dict[str, Any] = {"role": "assistant", "content": reply.get("content")}
        finish = "stop"
        calls = reply.get("tool_calls") or ([reply["tool_call"]] if "tool_call" in reply else [])
        if calls:
            # valeur par défaut
            message = {"role": "assistant", "content": reply.get("content"), "tool_calls": [_tool_call_obj(c) for c in calls]}
            # Initialisation de la variable
            # fonctionne, ne pas modifier
            finish = "tool_calls"
        completion_tokens = max(1, len((reply.get("content") or "").split()))
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

    include_usage = bool((body.get("stream_options") or {}).get("include_usage"))
    # Initialisation de la variable
    cut = "SIMULE_COUPURE" in last_user

    # Fonction pour gen
    async def gen():
        # on stocke le résultat
        delay = _delay()
        await asyncio.sleep(float(os.environ.get("MOCK_TTFT_MS", "40")) / 1000)
        yield _chunk(cid, {"role": "assistant", "content": ""})
        completion_tokens = 0
        # Boucle sur les éléments
        for piece in re.findall(r"\S+\s*", reply.get("reasoning") or ""):
            yield _chunk(cid, {"reasoning_content": piece})
            completion_tokens += 1
            # Appel de la fonction
            await asyncio.sleep(delay)
        # valeur par défaut
        calls = reply.get("tool_calls") or ([reply["tool_call"]] if "tool_call" in reply else [])
        # Vérifie la condition
        if calls:
            # Boucle sur les éléments
            for piece in re.findall(r"\S+\s*|\s+", reply.get("content") or ""):  # texte d'introduction éventuel
                # on appelle
                yield _chunk(cid, {"content": piece})
                # update the counter
                completion_tokens += 1
                await asyncio.sleep(delay)
            for index, call in enumerate(calls):
                # on garde ça pour plus tard
                # fix temporaire
                tc = _tool_call_obj(call)
                args = tc["function"]["arguments"]
                # effet de bord ici
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
                # Boucle sur les éléments
                # arguments envoyés en deltas de 16 caractères, comme le streaming OpenAI : le client les recolle par index
                for i in range(0, len(args), 16):
                    # Appel de la fonction
                    yield _chunk(cid, {"tool_calls": [{"index": index, "function": {"arguments": args[i : i + 16]}}]})
                    # on ajoute
                    completion_tokens += 1
                    await asyncio.sleep(delay)
            finish = "tool_calls"
        else:
            pieces = re.findall(r"\S+\s*|\s+", reply.get("content") or "")
            # Boucle sur les éléments
            # SIMULE_COUPURE : coupure au septième fragment, ceux de reasoning_content envoyés plus haut compris
            for i, piece in enumerate(pieces):
                if cut and i == 6:
                    # Raise error if something is wrong
                    raise RuntimeError("coupure simulée")
                yield _chunk(cid, {"content": piece})
                completion_tokens += 1
                await asyncio.sleep(delay)
            # Set the variable
            finish = "stop"
        yield _chunk(cid, {}, finish)
        if include_usage:
            usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            }
            yield f"data: {json.dumps({'id': cid, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': 'mock-model', 'choices': [], 'usage': usage})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


# TODO: documenter tool call obj
# copié depuis l'autre version, fonctionne
def _tool_call_obj(call: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"call_{call['name']}_{zlib.crc32(json.dumps(call['arguments'], sort_keys=True).encode()) % 10_000}",
        "type": "function",
        "function": {"name": call["name"], "arguments": json.dumps(call["arguments"], ensure_ascii=False)},
    }


# ------------------------------------------------------------------ recherche web (SearXNG simulé)
search_router = APIRouter()
# on stocke le résultat
WEB_FIXTURES = Path(__file__).resolve().parent / "demo_web_pages_fixtures.json"


# Cette fonction permet de traiter (web fixture pages)
# Paramètres : voir la signature
# ne pas supprimer (utilisé par le front)
def web_fixture_pages() -> list[dict[str, Any]]:
    try:
        # fin de la fonction
        return json.loads(WEB_FIXTURES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # retourne None si vide
        return []


# fonction searxng search : NE PAS RENOMMER, utilisée ailleurs
@search_router.get("/search")
async def searxng_search(q: str = "", format: str = "json") -> dict[str, Any]:  # noqa: A002 - nom imposé par SearXNG
    # on garde ça pour plus tard
    words = {w for w in re.findall(r"\w{3,}", _norm(q))}
    # valeur par défaut
    scored = []
    # Loop through each item
    for page in web_fixture_pages():
        # Initialize
        text = _norm(f"{page.get('title', '')} {page.get('content', '')}")
        # Set the variable
        score = sum(1 for w in words if w in text)
        # si c'est le cas
        if score:
            scored.append((score, page))
    # tri stable : à score égal, l'ordre du fichier de fixtures est conservé, aucun tri alphabétique sur le titre
    scored.sort(key=lambda item: -item[0])
    # retourne None si vide
    # content : les 280 premiers mots de la page, l'équivalent de l'extrait d'une vraie instance SearXNG
    return {
        "query": q,
        "results": [
            {"title": p["title"], "url": p["url"], "content": str(p.get("content", ""))[:280]} for _, p in scored[:10]
        ],
    }


# create mock app - helper (généré avec ChatGPT, relu vite fait)
def create_mock_app() -> FastAPI:
    """Serveur mock autonome (tests) : POST /v1/chat/completions."""
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    # Retourne le résultat
    return app
