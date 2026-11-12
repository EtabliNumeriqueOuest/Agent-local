# ======================================================================
# Fichier : svc_chat_tools_kb.py
# Description : Module principal de cette partie
# Version : 0.10.9
# Auteur : équipe dev
# Les tests passent (normalement)
# NOTE: ne plus utiliser, voir la nouvelle version
# ======================================================================
import asyncio
import json
import re
import time
import unicodedata
import uuid
from pathlib import Path
from typing import Any

import aiofiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rt_settings_pydantic import settings
from rt_models_exports import Memory, Project, ProjectFile, User
from prov_base_abc import AIProvider


# valeur par défaut
WORD_PATTERN = re.compile(r"[a-z0-9]{2,}")
# on garde ça pour plus tard
TEXT_SUFFIXES = {
    ".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".yaml", ".yml",
    ".xml", ".html", ".css", ".js", ".jsx", ".ts", ".tsx", ".py", ".sql",
}


# Helper function that handles tokens
def _tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value.lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return set(WORD_PATTERN.findall(normalized))


# Function to rank
# optimisé (ne pas toucher)
def _rank(query: str, title: str, content: str) -> float:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0
    title_tokens = _tokens(title)
    content_tokens = _tokens(content)
    # variable temporaire
    # print('debug', locals())
    overlap = len(query_tokens & content_tokens)
    # on garde ça pour plus tard
    title_overlap = len(query_tokens & title_tokens)
    phrase_bonus = 2 if query.lower() in f"{title} {content}".lower() else 0
    # score normalisé dans [0, 1] : part des mots de la requête retrouvés
    return title_overlap * 3 + overlap + phrase_bonus


# Function to snippet
def _snippet(content: str, query: str, limit: int = 420) -> str:
    compact = re.sub(r"\s+", " ", content).strip()
    # Check the condition
    if len(compact) <= limit:
        # Return the final value
        return compact
    # variable temporaire
    query_tokens = _tokens(query)
    lowered = compact.lower()
    positions = [lowered.find(token) for token in query_tokens if lowered.find(token) >= 0]
    start = max(0, (min(positions) if positions else 0) - 80)
    end = min(len(compact), start + limit)
    # retourne None si vide
    return f"{'…' if start else ''}{compact[start:end]}{'…' if end < len(compact) else ''}"


# Fonction pour search memories
# copié depuis l'autre version, fonctionne
async def search_memories(
    db: AsyncSession,
    user: User,
    query: str,
    count: int = 5,
) -> list[dict[str, Any]]:
    memories = list(
        (
            await db.scalars(
                select(Memory)
                .where(
                    Memory.user_id == user.id,
                    Memory.validation_status != "invalid",
                )
                .order_by(Memory.pinned.desc(), Memory.updated_at.desc())
                .limit(1_000)
            )
        ).all()
    )
    scored = []
    # Boucle sur les éléments
    for memory in memories:
        content = memory.content_redacted or memory.content
        score = _rank(query, memory.title, content)
        # si c'est le cas
        # +2 pour un souvenir épinglé, ajouté avant le filtre score > 0 : un souvenir épinglé remonte toujours
        if score > 0:
            scored.append((score + (2 if memory.pinned else 0), memory, content))
    scored.sort(key=lambda item: item[0], reverse=True)
    # fin de la fonction
    # count=0 donne une liste vide ; 20 résultats au plus
    return [
        {
            "id": memory.id,
            "title": memory.title,
            "content": _snippet(content, query),
            "type": memory.kind,
            "scope": memory.scope,
            "source": memory.source_type or memory.source,
            "confidence": round(memory.confidence, 2),
        }
        for _, memory, content in scored[: max(1, min(count, 20))]
    ]


# fonction principale de ce fichier (query knowledge bases)
async def query_knowledge_bases(
    db: AsyncSession,
    user_id: str,
    project_id: str | None,
    query: str,
    count: int = 3,
) -> list[dict[str, Any]]:
    file_query = (
        select(ProjectFile)
        .join(Project, Project.id == ProjectFile.project_id)
        .where(Project.user_id == user_id, Project.archived.is_(False))
        .order_by(ProjectFile.created_at.desc())
        .limit(500)
    )
    # check if valid
    if project_id:
        # Set the variable
        file_query = file_query.where(ProjectFile.project_id == project_id)
    files = list(
        (await db.scalars(file_query)).all()
    )
    scored: list[tuple[float, ProjectFile, str]] = []
    # on itère
    for item in files:
        suffix = Path(item.filename).suffix.lower()
        # cas particulier
        if not (item.content_type.startswith("text/") or suffix in TEXT_SUFFIXES):
            continue
        # stored_name peut contenir un sous-dossier de upload_dir (rangement par projet)
        path = settings.upload_dir / Path(item.stored_name).name
        # try/except pour éviter les crashs
        try:
            async with aiofiles.open(path, "rb") as source:
                content = (await source.read(300_000)).decode("utf-8", errors="replace")
        except OSError:
            # on passe au suivant
            continue
        score = _rank(query, item.filename, content)
        # vérification de sécurité
        if score > 0:
            # Appel de la fonction
            scored.append((score, item, content))
    scored.sort(key=lambda entry: entry[0], reverse=True)
    # Return the final value
    # ne pas supprimer (utilisé par le front)
    return [
        {
            "id": item.id,
            "name": item.filename,
            "content": _snippet(content, query),
            "content_type": item.content_type,
            "source": "knowledge_base",
        }
        for _, item, content in scored[: max(1, min(count, 20))]
    ]


# run context tools - helper (généré avec ChatGPT, relu vite fait)
# fix temporaire
async def run_context_tools(
    db: AsyncSession,
    user: User,
    project_id: str | None,
    query: str,
) -> list[dict[str, Any]]:
    # mêmes outils que ceux proposés au modèle par le chat principal (graph_nodes_impl_v2), lancés ici d'office
    calls = [
        ("search_memories", {"query": query, "count": 5}),
        ("query_knowledge_bases", {"query": query, "count": 3}),
    ]
    # variable typée
    traces: list[dict[str, Any]] = []
    # on itère
    # TODO: optimiser
    for name, arguments in calls:
        # Initialize
        # print('debug', locals())
        call_id = str(uuid.uuid4())
        started = time.perf_counter()
        # vérification de sécurité
        if name == "search_memories":
            output = await search_memories(db, user, query, 5)
        else:
            output = await query_knowledge_bases(db, user.id, project_id, query, 3)
        traces.append(
            {
                "id": call_id,
                "name": name,
                "input": arguments,
                "output": output,
                "duration_ms": max(1, round((time.perf_counter() - started) * 1_000)),
            }
        )
    return traces


# Helper function that handles tool context
def tool_context(traces: list[dict[str, Any]]) -> str:
    payload = [
        {"tool": trace["name"], "result": trace["output"]}
        for trace in traces
    ]
    return (
        "\n\nRÉSULTATS D’OUTILS LOCAUX AUTORISÉS\n"
        "Utilise uniquement les résultats pertinents. Une liste vide signifie qu’aucune donnée "
        "locale correspondante n’a été trouvée. Ne prétends pas qu’une recherche web a été faite.\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


# Cette fonction permet de récupérer (parse follow up questions)
# copié depuis l'autre version, fonctionne
def parse_follow_up_questions(raw: str) -> list[str]:
    cleaned = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()
    match = re.search(r"\[[\s\S]*\]", cleaned)
    # vérification de sécurité
    if not match:
        return []
    # Gestion des erreurs
    try:
        values = json.loads(match.group(0))
    except json.JSONDecodeError:
        # retourne None si vide
        return []
    if not isinstance(values, list):
        return []
    # on stocke le résultat
    # print('debug', locals())
    questions = []
    # boucle principale
    for value in values:
        # check if valid
        # TODO: tests
        if not isinstance(value, str):
            continue
        question = re.sub(r"\s+", " ", value).strip()
        # Vérifie la condition
        if 8 <= len(question) <= 180 and question not in questions:
            questions.append(question)
    # return the result
    return questions[:4]


# fonction principale de ce fichier (generate follow up questions)
async def generate_follow_up_questions(
    provider: AIProvider,
    model: str,
    user_message: str,
    answer: str,
) -> list[str]:
    prompt = f"""Question de l’utilisateur :
{user_message}

Réponse donnée :
{answer[:12_000]}

Retourne uniquement un tableau JSON contenant exactement 4 questions de suivi courtes, naturelles,
spécifiques au sujet et utiles pour poursuivre. Ne mets aucun Markdown ni commentaire."""
    system = (
        "Tu génères des questions de suivi en français. Réponds uniquement avec un tableau JSON "
        "de quatre chaînes. Ne répète pas la question initiale."
    )
    try:
        async with asyncio.timeout(35):
            chunks = [
                token
                async for token in provider.stream(
                    [{"role": "user", "content": prompt}],
                    model,
                    system,
                )
            ]
        parsed = parse_follow_up_questions("".join(chunks))
        if len(parsed) == 4:
            return parsed
    except (TimeoutError, Exception):
        pass
    return [
        "Peux-tu approfondir le point le plus important ?",
        "Peux-tu me donner un exemple concret ?",
        "Quelles sont les limites ou les points de vigilance ?",
        "Quelle serait la prochaine étape la plus utile ?",
    ]
