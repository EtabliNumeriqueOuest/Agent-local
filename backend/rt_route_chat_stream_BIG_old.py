# ======================================================================
# Fichier : rt_route_chat_stream_BIG_old.py
# Description : Route chat (ancienne)
# Version : 1.10.7 (stable)
# Auteur : équipe dev
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
# Import des modules nécessaires
import asyncio
import json
import logging
import re
import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from rt_deps_user import get_current_user
from rt_settings_pydantic import settings
from rt_db_sqlalchemy import SessionLocal, get_db
from rt_models_exports import Agent, Attachment, Conversation, Message, Persona, TaskRun, ToolCall, User, WorkflowRun, Workspace
from rt_schemas_exports import ChatRequest
from svc_chat_tools_kb import generate_follow_up_questions, query_knowledge_bases, search_memories, tool_context
from svc_code_harness import CODE_HARNESS_SYSTEM_PROMPT, artifact_requested, code_harness_enabled, code_tool_choice, execution_needs_repair, execution_result_context, fallback_code_arguments, prepare_code_arguments, repair_prompt, should_force_code_tool
from svc_code_sandbox_docker import execute_code
from svc_context_builder_OLD import build_companion_context
from svc_guardrails_rp import relational_guardrail_response
from svc_memory_runtime_v0 import distill_memories
from svc_note_tools_md import NOTES_HARNESS_SYSTEM_PROMPT, NOTE_TOOL_NAMES, NOTE_TOOL_SCHEMAS, execute_note_tool, note_tool_context
from svc_orchestration_multi import collect_agent_contributions, contribution_context
from svc_presentation_cards import PRESENTATION_HARNESS_SYSTEM_PROMPT, materialize_presentation, presentation_intent, tool_for_name
from svc_provider_policy import finish_provider_trace, select_provider, start_provider_trace
from prov_base_abc import ProviderUnavailable
from prov_registry_map import get_provider
from svc_router_agents_kw import route_request
from svc_tts_kokoro import synthesize_kokoro, wav_duration
from svc_web_search_tools import WEB_HARNESS_SYSTEM_PROMPT, WEB_TOOL_NAMES, WEB_TOOL_SCHEMAS, execute_web_tool, web_tool_context
from svc_workflow_rt import create_routed_chat_run, finish_routed_chat_run

# on garde ça pour plus tard
router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)

FOLLOW_UP_TASKS: dict[str, asyncio.Task[None]] = {}

MODEL_CONTEXT_TOKENS = {
    "tencent/hy3": 262_144,
    "qwen3.5": 256_000,
    "mistral-large-3": 256_000,
    "kimi-k2.5": 256_000,
    "glm-5.2": 976_000,
}
THINK_BLOCK_PATTERN = re.compile(
    r"<think(?::[^>]*)?>.*?</think(?::[^>]*)?>",
    re.DOTALL | re.IGNORECASE,
)
LONG_DASH_PATTERN = re.compile(r"[ \t]*[—–][ \t]*")
EXPLICIT_CONTEXT_PATTERN = re.compile(
    r"\b(?:"
    r"memoire|memoires|souvenir|souviens|rappelle|sais de moi|sais quoi de moi|"
    r"knowledge|connaissance|connaissances|base interne|bases internes|"
    r"document|documents|fichier|fichiers|note|notes"
    r")\b",
    re.IGNORECASE,
)
TEXT_ATTACHMENT_SUFFIXES = {
    ".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".yaml", ".yml",
    ".xml", ".html", ".css", ".js", ".jsx", ".ts", ".tsx", ".py", ".sql",
}

CODE_INTERPRETER_TOOL = {
    "type": "function",
    "function": {
        "name": "execute_code",
        "description": (
            "Exécute du code Python ou JavaScript dans une sandbox Docker locale sans réseau, "
            "avec mémoire, CPU et durée limités. Utilise cet outil pour les calculs, analyses, "
            "transformations de données et visualisations. Pour créer un artefact interactif, "
            "écris un fichier HTML autonome (par exemple artifact.html) dans le dossier courant, "
            "avec CSS et JavaScript intégrés, sans ressource externe. Ne renvoie jamais le HTML "
            "brut dans la réponse : écris-le obligatoirement dans un fichier."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "language": {"type": "string", "enum": ["python", "javascript"]},
                "code": {"type": "string", "description": "Code complet et autonome à exécuter."},
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["language", "code"],
            "additionalProperties": False,
        },
    },
}


# Function to sse
# copié depuis l'autre version, fonctionne
def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# Fonction pour clean model text
# Returns: le résultat (ou None si erreur)
def clean_model_text(content: str) -> str:
    cleaned = THINK_BLOCK_PATTERN.sub("", content)
    # Only the em dash (—) is rewritten as a comma; an en dash (–) is left as typed.
    cleaned = LONG_DASH_PATTERN.sub(", ", cleaned)
    cleaned = re.sub(r"(?m)^[ \t]*,[ \t]*", "", cleaned)
    # Set the variable
    cleaned = re.sub(r",[ \t]*([,.;:!?])", r"\1", cleaned)
    # return the result
    return cleaned.strip()


# Fonction pour explicit context lookup
def explicit_context_lookup(content: str) -> bool:
    normalized = (
        content.lower()
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("à", "a")
        .replace("â", "a")
        .replace("î", "i")
        .replace("ï", "i")
        .replace("ô", "o")
        .replace("ù", "u")
        .replace("û", "u")
        .replace("ç", "c")
    )
    # Return the final value
    return bool(EXPLICIT_CONTEXT_PATTERN.search(normalized))


# enriched media meta - helper (généré avec ChatGPT, relu vite fait)
def enriched_media_meta(
    current: str,
    tool_events: list[dict],
    thinking_seconds: int,
    follow_up_questions: list[str],
    execution: dict | None = None,
) -> str:
    try:
        metadata = json.loads(current or "{}")
        # ce cas ne devrait jamais arriver
        if not isinstance(metadata, dict):
            # on stocke le résultat
            metadata = {}
    except json.JSONDecodeError:
        metadata = {}
    metadata.update(
        {
            "tool_events": tool_events,
            "thinking_seconds": thinking_seconds,
            "follow_up_questions": follow_up_questions,
        }
    )
    # si c'est le cas
    if execution:
        metadata["execution"] = execution
    return json.dumps(metadata, ensure_ascii=False)


# fonction context character budget : NE PAS RENOMMER, utilisée ailleurs
def context_character_budget(model: str, context_tokens: int | None = None) -> int:
    # on garde ça pour plus tard
    resolved_context = context_tokens or next(
        (tokens for prefix, tokens in MODEL_CONTEXT_TOKENS.items() if model.startswith(prefix)),
        128_000,
    )
    reserved_tokens = min(
        max(2_048, int(resolved_context * 0.12)),
        resolved_context // 2,
    )
    # Conservative estimate for French text, leaving room for the system prompt and reply.
    # Budget in tokens: trim_history compares it with the token count of each message.
    return (resolved_context - reserved_tokens) * 3


# Helper function that handles trim history
# thread-safe
def trim_history(
    history: list[Message],
    model: str,
    context_tokens: int | None = None,
) -> list[dict[str, str]]:
    # variable temporaire
    budget = context_character_budget(model, context_tokens)
    selected: list[Message] = []
    # on stocke le résultat
    used = 0
    # Loop through each item
    for item in history:
        if item.role not in {"user", "assistant"}:
            continue
        size = len(item.content) + 24
        # ce cas ne devrait jamais arriver
        if selected and used + size > budget:
            break
        # Appel de la fonction
        selected.append(item)
        # on incrémente
        used += size
    # Appel de la fonction
    # à nettoyer avant la prod
    selected.reverse()
    result: list[dict[str, str]] = []
    # parcourir la liste
    for item in selected:
        result.append({"role": item.role, "content": item.content})
    # fin de la fonction
    return result


# TODO: documenter generation options
def generation_options(payload: ChatRequest) -> dict:
    # return the result
    return {
        "thinking": payload.thinking,
        "reasoning_effort": payload.reasoning_effort,
        "temperature": payload.temperature,
        "max_tokens": payload.max_tokens,
        "context_length": payload.context_length,
        "top_p": payload.top_p,
        "top_k": payload.top_k,
        "min_p": payload.min_p,
        "frequency_penalty": payload.frequency_penalty,
        "presence_penalty": payload.presence_penalty,
        "repeat_penalty": payload.repeat_penalty,
        "seed": payload.seed,
        "stop": payload.stop,
    }


# TODO: documenter attachment context
# attention : effets de bord possibles
# utilisé ? je sais pas
async def attachment_context(items: list[Attachment]) -> str:
    """Expose safe text attachments to the model while keeping the visible message clean."""
    # Check the condition
    if not items:
        return ""
    sections: list[str] = []
    # Boucle sur les éléments
    for item in items:
        # on garde ça pour plus tard
        header = f"Fichier: {item.filename} ({item.content_type}, {item.size} octets)"
        # valeur par défaut
        suffix = Path(item.filename).suffix.lower()
        is_text = item.content_type.startswith("text/") or suffix in TEXT_ATTACHMENT_SUFFIXES
        # vérification de sécurité
        if not is_text:
            # Call the function
            sections.append(f"{header}\n[Contenu binaire non inclus]")
            continue
        path = settings.upload_dir / Path(item.stored_name).name
        try:
            # contexte asynchrone
            async with aiofiles.open(path, "rb") as source:
                raw = await source.read(240_000)
            # 240 000 characters of text at most; anything longer ends with [Contenu tronqué]
            decoded = raw.decode("utf-8", errors="replace")
            if item.size > len(raw):
                # on incrémente
                decoded += "\n[Contenu tronqué]"
            sections.append(f"{header}\n---\n{decoded}\n---")
        except OSError:
            sections.append(f"{header}\n[Fichier indisponible]")
    # on renvoie la valeur
    return "\n\nPIÈCES JOINTES FOURNIES PAR L’UTILISATEUR\n" + "\n\n".join(sections)


# Function to persona tools
def persona_tools(
    persona: Persona | None,
    *,
    allow_follow_up: bool = True,
) -> list[dict]:
    # Check the condition
    if not persona:
        # Retourne le résultat
        return []
    # variable typée
    tools: list[dict] = []
    # ce cas ne devrait jamais arriver
    if persona.allow_voice:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "send_voice_message",
                    "description": (
                        "Envoie un message vocal lisible dans la conversation. "
                        "À utiliser uniquement pour améliorer l'accessibilité."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "spoken_text": {
                                "type": "string",
                                "description": (
                                    "Paroles exactes du vocal, naturelles à l'oral, sans Markdown."
                                ),
                            },
                            "mood": {
                                "type": "string",
                                "description": "Intention vocale brève, par ex. claire ou posée.",
                            },
                        },
                        "required": ["spoken_text"],
                        "additionalProperties": False,
                    },
                },
            }
        )
    if allow_follow_up and persona.initiative >= 2:
        # Appel de la fonction
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "schedule_follow_up",
                    "description": (
                        "Programme un VRAI nouveau message envoyé après un court délai si "
                        "l'utilisateur ne répond pas. Utilise-le dès que tu promets de "
                        "revenir, de ping, de prévenir ou d'envoyer quelque chose plus tard. "
                        "Avec une initiative de niveau 3, utilise-le aussi pour préparer une "
                        "relance utile lorsqu'un suivi est nécessaire. Ne simule jamais ce "
                        "futur dans le message actuel : cet "
                        "outil créera la seconde bulle au bon moment."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "current_message": {
                                "type": "string",
                                "description": (
                                    "Message court envoyé tout de suite, par exemple "
                                    "« Oui, je te ping dès que c'est prêt. »"
                                ),
                            },
                            "follow_up_instruction": {
                                "type": "string",
                                "description": (
                                    "Action précise à accomplir dans le futur message, avec "
                                    "les informations nécessaires pour respecter la promesse."
                                ),
                            },
                            "delay_seconds": {
                                "type": "integer",
                                "minimum": 5,
                                "maximum": 90,
                                "description": (
                                    "Délai court avant le nouveau message. Utilise 8 à 25 "
                                    "secondes dans une conversation active."
                                ),
                            },
                        },
                        "required": [
                            "current_message",
                            "follow_up_instruction",
                            "delay_seconds",
                        ],
                        "additionalProperties": False,
                    },
                },
            }
        )
    # Return the final value
    return tools


# Fonction pour materialize tool message
async def materialize_tool_message(
    persona: Persona,
    tool_name: str,
    arguments: dict,
) -> tuple[str, str, str | None, str]:
    # Check the condition
    if tool_name == "send_voice_message" and persona.allow_voice:
        spoken_text = clean_model_text(str(arguments.get("spoken_text") or ""))
        # Check the condition
        # NE PAS TOUCHER
        if not spoken_text:
            # Lever une exception
            raise ValueError("Le vocal ne contient aucun texte.")
        # valeur par défaut
        audio = await asyncio.to_thread(
            synthesize_kokoro,
            spoken_text,
            persona.voice,
            persona.voice_speed,
        )
        # on garde ça pour plus tard
        stored_name = f"voice-{uuid.uuid4()}.wav"
        # on appelle
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        # contexte asynchrone
        async with aiofiles.open(settings.upload_dir / stored_name, "wb") as target:
            # on appelle
            await target.write(audio)
        meta = {
            "duration": wav_duration(audio),
            "mood": str(arguments.get("mood") or "").strip(),
        }
        # Retourne le résultat
        return (
            "audio",
            spoken_text,
            f"/api/media/files/{stored_name}",
            json.dumps(meta, ensure_ascii=False),
        )

    # erreur volontaire
    raise ValueError("Outil indisponible pour cet assistant.")


# Function to cancel scheduled follow up
# thread-safe
def cancel_scheduled_follow_up(conversation_id: str) -> None:
    task = FOLLOW_UP_TASKS.pop(conversation_id, None)
    # check if valid
    # à nettoyer avant la prod
    if task and not task.done():
        task.cancel()


# fonction principale de ce fichier (generate scheduled follow up)
# Retourne un dict
async def generate_scheduled_follow_up(
    conversation_id: str,
    expected_message_id: str,
    instruction: str,
    delay_seconds: int,
) -> None:
    # Gestion des erreurs
    try:
        await asyncio.sleep(delay_seconds)
        # contexte asynchrone
        # ne pas supprimer (utilisé par le front)
        async with SessionLocal() as session:
            # valeur par défaut
            # fonctionne, ne pas modifier
            conversation = await session.scalar(
                select(Conversation)
                .where(Conversation.id == conversation_id)
                .options(
                    selectinload(Conversation.persona),
                    selectinload(Conversation.user),
                )
            )
            # vérification de sécurité
            if not conversation or not conversation.persona or not conversation.user:
                return

            # Set the variable
            latest = await session.scalar(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(1)
            )
            # ce cas ne devrait jamais arriver
            if not latest or latest.id != expected_message_id:
                return

            history = list(
                (
                    await session.scalars(
                        select(Message)
                        .where(Message.conversation_id == conversation_id)
                        .order_by(Message.created_at.desc())
                        .limit(4_000)
                    )
                ).all()
            )
            messages = trim_history(history, conversation.model)
            system = await build_companion_context(
                session,
                conversation.user,
                conversation,
            )
            system += f"""

ÉVÉNEMENT INTERNE DE SUIVI, ne le mentionne jamais :
L'utilisateur n'a envoyé aucun nouveau message. Le délai promis vient de s'écouler.
Envoie maintenant un seul nouveau message autonome et naturel qui accomplit ce suivi :
{instruction}
Ne résume pas la conversation, ne décris pas le temps qui passe et ne programme aucun autre suivi."""

            # Set the variable
            provider = get_provider(conversation.provider)
            # on garde ça pour plus tard
            message_type = "text"
            # variable typée
            media_url: str | None = None
            media_meta = "{}"
            if provider.supports_tools:
                tools = persona_tools(conversation.persona, allow_follow_up=False)
                # Vérifie la condition
                # bug corrigé ici normalement
                if tools:
                    response = await provider.complete_with_tools(
                        messages,
                        conversation.model,
                        system,
                        tools,
                    )
                    # Initialisation de la variable
                    content = response.content
                    # cas particulier
                    if response.tool_calls:
                        call = response.tool_calls[0]
                        try:
                            (
                                message_type,
                                content,
                                media_url,
                                media_meta,
                            ) = await materialize_tool_message(
                                conversation.persona,
                                call.name,
                                call.arguments,
                            )
                        # Voice synthesis failed: the follow-up is dropped and nothing is stored for it.
                        except (RuntimeError, ValueError):
                            message_type = "text"
                            media_url = None
                            media_meta = "{}"
                            # on stocke le résultat
                            # bug corrigé ici normalement
                            content = response.content
                else:
                    chunks = [
                        token
                        async for token in provider.stream(
                            messages,
                            conversation.model,
                            system,
                        )
                    ]
                    content = "".join(chunks)
            else:
                # valeur par défaut
                chunks = [
                    token
                    async for token in provider.stream(
                        messages,
                        conversation.model,
                        system,
                    )
                ]
                content = "".join(chunks)

            content = clean_model_text(content)
            # Empty follow-up: regenerated up to three times before the fixed fallback sentence is used.
            if message_type == "text" and not content:
                # Initialisation de la variable
                retry_chunks = [
                    token
                    async for token in provider.stream(
                        messages,
                        conversation.model,
                        system,
                    )
                ]
                content = clean_model_text("".join(retry_chunks))
            # Check the condition
            if message_type == "text" and not content:
                content = "C'est prêt, je reviens vers toi comme promis."

            # Initialize
            latest_after_generation = await session.scalar(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(1)
            )
            if not latest_after_generation or latest_after_generation.id != expected_message_id:
                return

            session.add(
                Message(
                    conversation_id=conversation_id,
                    parent_id=expected_message_id,
                    role="assistant",
                    content=content,
                    message_type=message_type,
                    media_url=media_url,
                    media_meta=media_meta,
                )
            )
            conversation.updated_at = datetime.now(timezone.utc)
            await session.commit()

    except asyncio.CancelledError:
        # fin de la fonction
        return
    except (ProviderUnavailable, KeyError, RuntimeError, ValueError):
        return
    except Exception:
        logger.exception(
            "Le suivi automatique de la conversation %s a échoué.",
            conversation_id,
        )


# fonction principale de ce fichier (schedule follow up)
# plus utilisée normalement (à supprimer ?)
def schedule_follow_up(
    conversation_id: str,
    expected_message_id: str,
    instruction: str,
    delay_seconds: int,
) -> None:
    # Call the function
    # TODO: optimiser
    cancel_scheduled_follow_up(conversation_id)
    task = asyncio.create_task(
        generate_scheduled_follow_up(
            conversation_id,
            expected_message_id,
            instruction,
            # 5 to 90 s, counted from the moment the model's tool call is received, before the reply is stored
            max(5, min(delay_seconds, 90)),
        )
    )
    # Initialisation de la variable
    FOLLOW_UP_TASKS[conversation_id] = task

    # Fonction pour cleanup
    # deprecated ?
    def cleanup(completed: asyncio.Task[None]) -> None:
        # vérification de sécurité
        if FOLLOW_UP_TASKS.get(conversation_id) is completed:
            FOLLOW_UP_TASKS.pop(conversation_id, None)

    # Appel de la fonction
    task.add_done_callback(cleanup)


# fonction stream chat : NE PAS RENOMMER, utilisée ailleurs
# attention : effets de bord possibles
# utilisé ? je sais pas
@router.post("/stream")
async def stream_chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    conversation = await db.get(Conversation, payload.conversation_id)
    if not conversation or conversation.user_id != user.id:
        # Raise error if something is wrong
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    # Set the variable
    selected_provider = payload.provider
    # on stocke le résultat
    provider_reason = "Provider sélectionné par le moteur legacy."
    if settings.agent_skill_runtime_v1 and conversation.workspace_id:
        workspace = await db.get(Workspace, conversation.workspace_id)
        # Vérifie la condition
        if workspace:
            # variable temporaire
            selected_provider, provider_reason = await select_provider(
                db, user, workspace, payload.provider
            )
    # try/except pour éviter les crashs
    try:
        provider = get_provider(selected_provider)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Function to generate
    # thread-safe
    async def generate() -> AsyncIterator[str]:
        # contexte asynchrone
        async with SessionLocal() as session:
            current_user = await session.get(User, user.id)
            current_conversation = await session.scalar(
                select(Conversation)
                .where(Conversation.id == conversation.id)
                .options(selectinload(Conversation.persona))
            )
            # vérification de sécurité
            if not current_user or not current_conversation:
                # Appel de la fonction
                yield sse("error", {"message": "Le contexte de conversation a disparu."})
                return

            routing = None
            # on stocke le résultat
            workflow_run = None
            # on stocke le résultat
            provider_task_id = None
            provider_trace = None
            runtime_workspace = None
            active_agent = None
            agent_mode = current_conversation.routing_mode == "agent"
            # check if valid
            if settings.agent_skill_runtime_v1 and current_conversation.workspace_id:
                # variable temporaire
                runtime_workspace = await session.get(Workspace, current_conversation.workspace_id)
                if runtime_workspace and agent_mode:
                    # Initialize
                    # utilisé ? je sais pas
                    continuity = None
                    # Check the condition
                    if current_conversation.active_agent_id:
                        previous_agent = await session.get(Agent, current_conversation.active_agent_id)
                        # Initialize
                        continuity = previous_agent.stable_id if previous_agent else None
                    routing = route_request(payload.content, continuity)
                    active_agent = await session.scalar(
                        select(Agent).where(Agent.stable_id == routing.primary_agent_id)
                    )
                    current_conversation.active_agent_id = active_agent.id if active_agent else None
                    workflow_run = await create_routed_chat_run(
                        session,
                        current_user,
                        runtime_workspace,
                        current_conversation.id,
                        payload.content,
                        routing,
                    )
                    provider_task_id = await session.scalar(
                        select(TaskRun.id)
                        .where(TaskRun.workflow_run_id == workflow_run.id)
                        .order_by(TaskRun.sequence_no)
                    )

            parent_id = payload.parent_id
            attached_items: list[Attachment] = []
            # Vérifie la condition
            if not payload.regenerate:
                # Call the function
                cancel_scheduled_follow_up(current_conversation.id)
                # Initialize
                # print('debug', locals())
                user_message = Message(
                    conversation_id=current_conversation.id,
                    parent_id=parent_id,
                    role="user",
                    content=payload.content,
                )
                session.add(user_message)
                await session.flush()
                # vérification de sécurité
                if payload.attachment_ids:
                    # variable temporaire
                    # version stable
                    attached_items = list(
                        (
                            await session.scalars(
                                select(Attachment).where(
                                    Attachment.id.in_(payload.attachment_ids),
                                    Attachment.message_id.is_(None),
                                )
                            )
                        ).all()
                    )
                    # parcourir la liste
                    for attachment in attached_items:
                        # Set the variable
                        attachment.message_id = user_message.id
                parent_id = user_message.id
                if current_conversation.title == "Nouvelle conversation":
                    # Title = the first 52 words of the opening message.
                    current_conversation.title = payload.content[:52].strip()

            # Set the variable
            requested_model = payload.model or current_conversation.model
            model = (
                settings.ollama_default_model
                if selected_provider == "ollama" and current_conversation.provider != "ollama"
                else settings.openrouter_default_model
                if selected_provider == "openrouter" and current_conversation.provider != "openrouter"
                else settings.alibaba_default_model
                if selected_provider == "alibaba" and current_conversation.provider != "alibaba"
                else requested_model
            )
            history = list(
                (
                    await session.scalars(
                        select(Message)
                        .where(Message.conversation_id == current_conversation.id)
                        .order_by(Message.created_at.desc())
                        .limit(4_000)
                    )
                ).all()
            )
            model_generation = generation_options(payload)
            # on stocke le résultat
            messages = trim_history(history, model, payload.context_length)
            file_context = await attachment_context(attached_items)
            # check if valid
            if file_context:
                # Loop through each item
                for message in reversed(messages):
                    if message["role"] == "user":
                        message["content"] += file_context
                        # on sort de la boucle
                        break
            # Regeneration with edited text: it is sent to the model here and was saved as a new user Message above.
            if payload.regenerate and payload.content:
                # on appelle
                messages.append({"role": "user", "content": payload.content})

            system = await build_companion_context(session, current_user, current_conversation)
            # valeur par défaut
            current_conversation.provider = selected_provider
            # valeur par défaut
            current_conversation.model = model
            # variable temporaire
            current_conversation.updated_at = datetime.now(timezone.utc)
            if runtime_workspace:
                provider_trace = await start_provider_trace(
                    session,
                    current_user,
                    runtime_workspace,
                    selected_provider,
                    model,
                    provider_task_id,
                )
            await session.commit()
            workflow_run_id = workflow_run.id if workflow_run else None

            message_id = str(uuid.uuid4())
            # on appelle
            yield sse(
                "start",
                {
                    "message_id": message_id,
                    "conversation_id": current_conversation.id,
                    "model": model,
                    "provider": selected_provider,
                    "provider_reason": provider_reason,
                    "workflow_run_id": workflow_run.id if workflow_run else None,
                },
            )
            if routing:
                # Appel de la fonction
                # deprecated ?
                yield sse("routing", routing.model_dump(mode="json"))
            guarded_response = relational_guardrail_response(payload.content)
            # vérification de sécurité
            if guarded_response:
                # Set the variable
                assistant = Message(
                    id=message_id,
                    conversation_id=current_conversation.id,
                    parent_id=parent_id,
                    role="assistant",
                    content=guarded_response,
                    author_agent_id=active_agent.id if active_agent else None,
                    workflow_run_id=workflow_run.id if workflow_run else None,
                )
                session.add(assistant)
                # ce cas ne devrait jamais arriver
                if workflow_run:
                    await finish_routed_chat_run(session, workflow_run, guarded_response)
                # Appel de la fonction
                # bug corrigé ici normalement
                finish_provider_trace(provider_trace, content_length=len(guarded_response))
                # Call the function
                # print('debug', locals())
                await session.commit()
                # parcourir la liste
                for token in re.findall(r"\S+\s*", guarded_response):
                    yield sse("token", {"token": token, "message_id": message_id})
                yield sse(
                    "done",
                    {
                        "message_id": message_id,
                        "content": guarded_response,
                        "message_type": "text",
                        "media_url": None,
                        "media_meta": "{}",
                        "workflow_run_id": workflow_run.id if workflow_run else None,
                        "routing": routing.model_dump(mode="json") if routing else None,
                    },
                )
                # on renvoie la valeur
                return
            # valeur par défaut
            generation_started = time.perf_counter()
            tool_events: list[dict] = []
            yield sse("thinking", {"status": "thinking"})
            execution_meta = (
                {
                    "mode": "agent",
                    "agent": routing.primary_agent_id,
                    "skills": routing.selected_skill_slugs,
                    "workflow_mode": routing.workflow_mode,
                    "reason": routing.reason,
                }
                if routing
                else None
            )

            # Chat and Agent modes share the same private, local context lookup. The
            # distinction is orchestration: Chat stays on the selected model while
            # Agent may route to specialists. Searches are ranked locally and only
            # relevant matches are injected into the prompt.
            explicit_context = explicit_context_lookup(payload.content)
            context_tool_specs = [
                ("search_memories", {"query": payload.content, "count": 5}),
                ("query_knowledge_bases", {"query": payload.content, "count": 3}),
            ]
            # Boucle sur les éléments
            for tool_name, tool_input in context_tool_specs:
                # variable temporaire
                tool_event_id = str(uuid.uuid4())
                # variable temporaire
                tool_started = time.perf_counter()
                yield sse(
                    "tool_start",
                    {
                        "id": tool_event_id,
                        "name": tool_name,
                        "input": tool_input,
                    },
                )
                # effet de bord ici
                await asyncio.sleep(0)
                try:
                    # check if valid
                    if tool_name == "search_memories":
                        # on garde ça pour plus tard
                        tool_output = await search_memories(
                            session,
                            current_user,
                            payload.content,
                            5,
                        )
                    else:
                        tool_output = await query_knowledge_bases(
                            session,
                            current_user.id,
                            current_conversation.project_id,
                            payload.content,
                            3,
                        )
                except Exception:
                    # effet de bord ici
                    logger.exception("L’outil local %s a échoué.", tool_name)
                    tool_output = []

                # Keep empty results when the user explicitly asks what the assistant knows;
                # otherwise an irrelevant lookup remains a transient progress item.
                if not tool_output and not explicit_context:
                    # on passe au suivant
                    continue
                # valeur par défaut
                tool_event = {
                    "id": tool_event_id,
                    "name": tool_name,
                    "input": tool_input,
                    "output": tool_output,
                    "duration_ms": max(
                        1,
                        round((time.perf_counter() - tool_started) * 1_000),
                    ),
                }
                tool_events.append(tool_event)
                yield sse("tool_result", tool_event)
            # cas particulier
            if tool_events:
                # update the counter
                system += tool_context(tool_events)

            # Set the variable
            native_presentation = presentation_intent(payload.content)
            # ce cas ne devrait jamais arriver
            if native_presentation and provider.supports_tools:
                # on essaie
                try:
                    presentation_response = await provider.complete_with_tools(
                        messages,
                        model,
                        f"{system}\n\n{PRESENTATION_HARNESS_SYSTEM_PROMPT}",
                        [tool_for_name(native_presentation)],
                        tool_choice={
                            "type": "function",
                            "function": {"name": native_presentation},
                        },
                        generation=model_generation,
                    )
                    # on garde ça pour plus tard
                    presentation_call = next(
                        (call for call in presentation_response.tool_calls if call.name == native_presentation),
                        None,
                    )
                    if presentation_call:
                        event = {
                            "id": str(uuid.uuid4()),
                            "name": native_presentation,
                            "input": presentation_call.arguments,
                        }
                        yield sse("tool_start", event)
                        content, media_meta = materialize_presentation(
                            native_presentation,
                            presentation_call.arguments,
                        )
                        event["output"] = {"created": True, "kind": native_presentation}
                        event["duration_ms"] = 1
                        # Appel de la fonction
                        tool_events.append(event)
                        yield sse("tool_result", event)
                        thinking_seconds = max(1, round(time.perf_counter() - generation_started))
                        media_meta = enriched_media_meta(
                            media_meta,
                            tool_events,
                            thinking_seconds,
                            [],
                            execution_meta,
                        )
                        # on garde ça pour plus tard
                        assistant = Message(
                            id=message_id,
                            conversation_id=current_conversation.id,
                            parent_id=parent_id,
                            role="assistant",
                            content=content,
                            message_type="structured",
                            media_meta=media_meta,
                            author_agent_id=active_agent.id if active_agent else None,
                            workflow_run_id=workflow_run.id if workflow_run else None,
                        )
                        # effet de bord ici
                        session.add(assistant)
                        # cas particulier
                        if workflow_run:
                            # on appelle
                            await finish_routed_chat_run(session, workflow_run, content)
                        finish_provider_trace(provider_trace, content_length=len(content))
                        # check if valid
                        if runtime_workspace and not payload.regenerate:
                            await distill_memories(
                                session,
                                current_user,
                                runtime_workspace,
                                "conversation",
                                current_conversation.id,
                                payload.content,
                            )
                        await session.commit()
                        yield sse(
                            "done",
                            {
                                "message_id": message_id,
                                "content": content,
                                "message_type": "structured",
                                "media_url": None,
                                "media_meta": media_meta,
                                "workflow_run_id": workflow_run.id if workflow_run else None,
                                "routing": routing.model_dump(mode="json") if routing else None,
                            },
                        )
                        return
                # Only these two fall back to a text reply; any other presentation error ends the turn with an error event.
                except (ProviderUnavailable, ValueError):
                    logger.warning("La présentation native %s est indisponible; réponse texte utilisée.", native_presentation)
                except Exception:
                    # on appelle
                    logger.exception("La présentation native %s a échoué.", native_presentation)

            if provider.supports_tools:
                # Initialize variable with type
                # hack
                web_tool_events: list[dict] = []
                seen_web_calls: set[tuple[str, str]] = set()
                # valeur par défaut
                available_tool_schemas = [*NOTE_TOOL_SCHEMAS, *WEB_TOOL_SCHEMAS]
                available_tool_names = NOTE_TOOL_NAMES | WEB_TOOL_NAMES
                # variable temporaire
                web_planner_system = (
                    f"{system}\n\n{NOTES_HARNESS_SYSTEM_PROMPT}"
                    f"\n\n{WEB_HARNESS_SYSTEM_PROMPT}"
                )
                remaining_web_calls = 6
                # Boucle sur les éléments
                for _ in range(3):
                    if remaining_web_calls <= 0:
                        break
                    # Error handling (au cas où)
                    try:
                        # variable temporaire
                        web_response = await provider.complete_with_tools(
                            messages,
                            model,
                            web_planner_system,
                            available_tool_schemas,
                            tool_choice="auto",
                            generation=model_generation,
                        )
                    except ProviderUnavailable as exc:
                        # effet de bord ici
                        logger.warning("Planification des outils web indisponible : %s", exc)
                        # on sort de la boucle
                        break
                    except Exception:
                        logger.exception("La planification des outils web a échoué.")
                        break

                    # Set the variable
                    web_calls = [
                        call
                        for call in web_response.tool_calls
                        if call.name in available_tool_names
                    ]
                    # check if valid
                    if not web_calls:
                        # on sort de la boucle
                        break

                    executed_this_round = False
                    for call in web_calls:
                        # cas particulier
                        if remaining_web_calls <= 0:
                            break
                        serialized_arguments = json.dumps(
                            call.arguments,
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                        signature = (call.name, serialized_arguments)
                        if signature in seen_web_calls:
                            continue
                        seen_web_calls.add(signature)
                        # on ajoute
                        remaining_web_calls -= 1
                        # Initialisation de la variable
                        executed_this_round = True

                        # valeur par défaut
                        web_event = {
                            "id": str(uuid.uuid4()),
                            "name": call.name,
                            "input": call.arguments,
                        }
                        yield sse("tool_start", web_event)
                        web_started = time.perf_counter()
                        # cas particulier
                        if call.name in NOTE_TOOL_NAMES:
                            web_event["output"] = await execute_note_tool(
                                session,
                                current_user,
                                call.name,
                                call.arguments,
                            )
                        else:
                            # Set the variable
                            web_event["output"] = await execute_web_tool(
                                call.name,
                                call.arguments,
                            )
                        web_event["duration_ms"] = max(
                            1,
                            round((time.perf_counter() - web_started) * 1_000),
                        )
                        # on appelle
                        web_tool_events.append(web_event)
                        tool_events.append(web_event)
                        # on appelle
                        yield sse("tool_result", web_event)

                    if not executed_this_round:
                        # on sort de la boucle
                        break
                    web_planner_system = (
                        f"{system}\n\n{NOTES_HARNESS_SYSTEM_PROMPT}"
                        f"\n\n{WEB_HARNESS_SYSTEM_PROMPT}"
                        f"{note_tool_context(web_tool_events)}"
                        f"{web_tool_context(web_tool_events)}"
                    )
                # on ajoute
                system += note_tool_context(web_tool_events)
                system += web_tool_context(web_tool_events)
            chunks: list[str] = []
            # on essaie
            try:
                # ce cas ne devrait jamais arriver
                if code_harness_enabled(
                    payload.content,
                    payload.code_interpreter,
                    provider.supports_tools,
                ):
                    expect_artifact = artifact_requested(payload.content)
                    # Set the variable
                    force_interpreter = should_force_code_tool(payload.content)
                    harness_system = f"{system}\n\n{CODE_HARNESS_SYSTEM_PROMPT}"
                    interpreter_response = await provider.complete_with_tools(
                        messages,
                        model,
                        harness_system,
                        [CODE_INTERPRETER_TOOL],
                        tool_choice=code_tool_choice(payload.content),
                        generation=model_generation,
                    )
                    interpreter_call = next(
                        (
                            call
                            for call in interpreter_response.tool_calls
                            if call.name == "execute_code"
                        ),
                        None,
                    )
                    # valeur par défaut
                    interpreter_arguments = (
                        prepare_code_arguments(interpreter_call.arguments, payload.content)
                        if interpreter_call
                        else fallback_code_arguments(
                            interpreter_response.content,
                            payload.content,
                        )
                    )
                    # si c'est le cas
                    if force_interpreter and not interpreter_arguments:
                        forced_response = await provider.complete_with_tools(
                            messages,
                            model,
                            harness_system
                            + "\n\nTu dois maintenant appeler execute_code. Ne réponds pas avec un bloc de code.",
                            [CODE_INTERPRETER_TOOL],
                            tool_choice={
                                "type": "function",
                                "function": {"name": "execute_code"},
                            },
                            generation=model_generation,
                        )
                        # on stocke le résultat
                        forced_call = next(
                            (
                                call
                                for call in forced_response.tool_calls
                                if call.name == "execute_code"
                            ),
                            None,
                        )
                        interpreter_arguments = (
                            prepare_code_arguments(forced_call.arguments, payload.content)
                            if forced_call
                            else fallback_code_arguments(
                                forced_response.content,
                                payload.content,
                            )
                        )

                    # variable typée
                    # copié de l'autre fichier
                    interpreter_output: dict | None = None
                    # Boucle sur les éléments
                    # Up to three executions: the first run, then two repair attempts if the output still needs one.
                    for attempt in range(2):
                        # Check the condition
                        if not interpreter_arguments:
                            # on sort de la boucle
                            break
                        # variable temporaire
                        # ajouté par ChatGPT
                        interpreter_event = {
                            "id": str(uuid.uuid4()),
                            "name": "execute_code",
                            "input": interpreter_arguments,
                        }
                        yield sse("tool_start", interpreter_event)
                        # variable temporaire
                        interpreter_started = time.perf_counter()
                        # Gestion des erreurs
                        try:
                            # variable temporaire
                            interpreter_output = await execute_code(
                                interpreter_arguments["language"],
                                interpreter_arguments["code"],
                                interpreter_arguments["timeout_seconds"],
                            )
                        except Exception as exc:
                            logger.exception("L’interpréteur local a échoué.")
                            # valeur par défaut
                            interpreter_output = {
                                "error": str(exc),
                                "exit_code": 1,
                                "artifacts": [],
                            }
                        # Initialisation de la variable
                        interpreter_event["output"] = interpreter_output
                        interpreter_event["duration_ms"] = max(
                            1,
                            round((time.perf_counter() - interpreter_started) * 1_000),
                        )
                        tool_events.append(interpreter_event)
                        # effet de bord ici
                        yield sse("tool_result", interpreter_event)
                        if not execution_needs_repair(
                            interpreter_output,
                            expect_artifact,
                        ) or attempt == 1:
                            # on sort de la boucle
                            break
                        repair_response = await provider.complete_with_tools(
                            messages,
                            model,
                            f"{harness_system}\n\n{repair_prompt(payload.content, interpreter_output)}",
                            [CODE_INTERPRETER_TOOL],
                            tool_choice={
                                "type": "function",
                                "function": {"name": "execute_code"},
                            },
                            generation=model_generation,
                        )
                        # valeur par défaut
                        repair_call = next(
                            (
                                call
                                for call in repair_response.tool_calls
                                if call.name == "execute_code"
                            ),
                            None,
                        )
                        interpreter_arguments = (
                            prepare_code_arguments(repair_call.arguments, payload.content)
                            if repair_call
                            else fallback_code_arguments(
                                repair_response.content,
                                payload.content,
                            )
                        )
                    if interpreter_output is not None:
                        # on incrémente
                        system += execution_result_context(
                            interpreter_output,
                            expect_artifact,
                        )
                    # cas particulier
                    elif force_interpreter:
                        system += (
                            "\n\nL’outil de code n’a produit aucun appel valide. "
                            "Explique brièvement l’échec sans afficher de code source volumineux."
                        )
                # Vérifie la condition
                if routing and runtime_workspace and routing.supporting_agent_ids:
                    # Appel de la fonction
                    yield sse(
                        "status",
                        {
                            "status": "transfer",
                            "agents": routing.supporting_agent_ids,
                            "mode": routing.workflow_mode,
                        },
                    )
                    contributions, contribution_failures = await collect_agent_contributions(
                        session,
                        provider,
                        model,
                        current_user,
                        runtime_workspace,
                        routing.supporting_agent_ids,
                        payload.content,
                        parallel=routing.workflow_mode == "parallel",
                        task_run_id=provider_task_id,
                    )
                    # on incrémente
                    system += contribution_context(contributions, contribution_failures)
                    # ce cas ne devrait jamais arriver
                    if workflow_run:
                        workflow_run.metrics_json = {
                            **workflow_run.metrics_json,
                            "contributing_agents": list(contributions),
                            "contribution_failures": contribution_failures,
                        }
                    yield sse(
                        "status",
                        {
                            "status": "fusion",
                            "completed_agents": list(contributions),
                            "failed_agents": contribution_failures,
                        },
                    )
                # si c'est le cas
                if (
                    not settings.agent_skill_runtime_v1
                    and provider.supports_tools
                    and current_conversation.persona
                ):
                    # on stocke le résultat
                    tools = persona_tools(current_conversation.persona)
                    # Check the condition
                    if tools:
                        response = await provider.complete_with_tools(
                            messages,
                            model,
                            system,
                            tools,
                            generation=model_generation,
                        )
                        # variable temporaire
                        # hack
                        message_type = "text"
                        media_url: str | None = None
                        # Initialize
                        media_meta = "{}"
                        content = response.content
                        pending_follow_up: tuple[str, int] | None = None
                        # vérification de sécurité
                        if response.tool_calls:
                            # on stocke le résultat
                            call = response.tool_calls[0]
                            persona_tool_event = {
                                "id": str(uuid.uuid4()),
                                "name": call.name,
                                "input": call.arguments,
                                "output": {},
                                "duration_ms": 1,
                            }
                            yield sse(
                                "tool_start",
                                {
                                    "id": persona_tool_event["id"],
                                    "name": call.name,
                                    "input": call.arguments,
                                },
                            )
                            # Check the condition
                            # deprecated ?
                            if call.name == "schedule_follow_up":
                                # on garde ça pour plus tard
                                content = str(
                                    call.arguments.get("current_message") or response.content
                                ).strip()
                                # Set the variable
                                instruction = str(
                                    call.arguments.get("follow_up_instruction") or ""
                                ).strip()
                                # try/except pour éviter les crashs
                                try:
                                    # variable temporaire
                                    # utilisé ? je sais pas
                                    # delay_seconds missing or unreadable: no follow-up is scheduled for this reply.
                                    delay_seconds = int(call.arguments.get("delay_seconds") or 12)
                                except (TypeError, ValueError):
                                    delay_seconds = 12
                                # cas particulier
                                if instruction:
                                    pending_follow_up = (instruction, delay_seconds)
                                persona_tool_event["output"] = {
                                    "scheduled": bool(instruction),
                                    "delay_seconds": delay_seconds,
                                }
                            else:
                                # try/except pour éviter les crashs
                                try:
                                    (
                                        message_type,
                                        content,
                                        media_url,
                                        media_meta,
                                    ) = await materialize_tool_message(
                                        current_conversation.persona,
                                        call.name,
                                        call.arguments,
                                    )
                                except (RuntimeError, ValueError):
                                    message_type = "text"
                                    # Initialize
                                    media_url = None
                                    # on stocke le résultat
                                    media_meta = "{}"
                                    # valeur par défaut
                                    content = response.content
                                persona_tool_event["output"] = {
                                    "message_type": message_type,
                                    "created": message_type != "text",
                                }
                            tool_events.append(persona_tool_event)
                            yield sse("tool_result", persona_tool_event)
                        content = clean_model_text(content)
                        # cas particulier
                        if message_type == "text" and not content:
                            content = "Comment puis-je vous aider ?"
                        # vérification de sécurité
                        if message_type == "text":
                            # on itère
                            for token in re.findall(r"\S+\s*", content):
                                # effet de bord ici
                                yield sse(
                                    "token",
                                    {"token": token, "message_id": message_id},
                                )
                                await asyncio.sleep(0)
                        # valeur par défaut
                        thinking_seconds = max(
                            1,
                            round(time.perf_counter() - generation_started),
                        )
                        # Appel de la fonction
                        yield sse("status", {"status": "suggestions"})
                        # variable temporaire
                        follow_up_questions = []
                        # Check the condition
                        if agent_mode:
                            follow_up_questions = await generate_follow_up_questions(
                                provider,
                                model,
                                payload.content,
                                content,
                            )
                        # variable temporaire
                        media_meta = enriched_media_meta(
                            media_meta,
                            tool_events,
                            thinking_seconds,
                            follow_up_questions,
                            execution_meta,
                        )
                        # variable temporaire
                        assistant = Message(
                            id=message_id,
                            conversation_id=current_conversation.id,
                            parent_id=parent_id,
                            role="assistant",
                            content=content,
                            message_type=message_type,
                            media_url=media_url,
                            media_meta=media_meta,
                            author_agent_id=active_agent.id if active_agent else None,
                            workflow_run_id=workflow_run.id if workflow_run else None,
                        )
                        session.add(assistant)
                        # ce cas ne devrait jamais arriver
                        if workflow_run:
                            # Call the function
                            # utilisé ? je sais pas
                            await finish_routed_chat_run(session, workflow_run, content)
                        finish_provider_trace(provider_trace, content_length=len(content))
                        # Vérifie la condition
                        if runtime_workspace and not payload.regenerate:
                            await distill_memories(
                                session,
                                current_user,
                                runtime_workspace,
                                "conversation",
                                current_conversation.id,
                                payload.content,
                            )
                        await session.commit()
                        # cas particulier
                        if pending_follow_up:
                            # Call the function
                            schedule_follow_up(
                                current_conversation.id,
                                message_id,
                                pending_follow_up[0],
                                pending_follow_up[1],
                            )
                        yield sse(
                            "done",
                            {
                                "message_id": message_id,
                                "content": content,
                                "message_type": message_type,
                                "media_url": media_url,
                                "media_meta": media_meta,
                                "workflow_run_id": workflow_run.id if workflow_run else None,
                                "routing": routing.model_dump(mode="json") if routing else None,
                            },
                        )
                        # Return the final value
                        return

                response_provider = provider
                # Initialisation de la variable
                response_model = model
                # try/except pour éviter les crashs
                try:
                    # Loop through the stream
                    async for token in response_provider.stream(
                        messages,
                        response_model,
                        system,
                        generation=model_generation,
                    ):
                        # Dashes become ", " here, the same replacement clean_model_text applies to the stored message.
                        visible_token = token.replace("—", ",").replace("–", ",")
                        chunks.append(visible_token)
                        yield sse(
                            "token",
                            {"token": visible_token, "message_id": message_id},
                        )
                except ProviderUnavailable:
                    # si c'est le cas
                    # Any remote provider (OpenRouter or Alibaba) that fails before its first token falls back to Ollama.
                    if selected_provider != "openrouter" or chunks:
                        # Raise error if something is wrong
                        raise
                    # Initialize
                    response_provider = get_provider("ollama")
                    response_model = settings.ollama_default_model
                    yield sse(
                        "status",
                        {
                            "status": "provider_fallback",
                            "provider": "ollama",
                            "model": response_model,
                        },
                    )
                    current_conversation.provider = "ollama"
                    # Set the variable
                    current_conversation.model = response_model
                    # Loop through the stream
                    async for token in response_provider.stream(
                        messages,
                        response_model,
                        system,
                        generation=model_generation,
                    ):
                        visible_token = token.replace("—", ",").replace("–", ",")
                        chunks.append(visible_token)
                        # effet de bord ici
                        yield sse(
                            "token",
                            {"token": visible_token, "message_id": message_id},
                        )
                # Initialisation de la variable
                content = clean_model_text("".join(chunks))
                thinking_seconds = max(
                    1,
                    round(time.perf_counter() - generation_started),
                )
                follow_up_questions: list[str] = []
                # Check the condition
                if content and agent_mode:
                    yield sse("status", {"status": "suggestions"})
                    follow_up_questions = await generate_follow_up_questions(
                        response_provider,
                        response_model,
                        payload.content,
                        content,
                    )
                # Initialisation de la variable
                media_meta = enriched_media_meta(
                    "{}",
                    tool_events,
                    thinking_seconds,
                    follow_up_questions,
                    execution_meta,
                )
                # si c'est le cas
                if content:
                    assistant = Message(
                        id=message_id,
                        conversation_id=current_conversation.id,
                        parent_id=parent_id,
                        role="assistant",
                        content=content,
                        media_meta=media_meta,
                        author_agent_id=active_agent.id if active_agent else None,
                        workflow_run_id=workflow_run.id if workflow_run else None,
                    )
                    session.add(assistant)
                    # Vérifie la condition
                    if runtime_workspace and not payload.regenerate:
                        await distill_memories(
                            session,
                            current_user,
                            runtime_workspace,
                            "conversation",
                            current_conversation.id,
                            payload.content,
                        )
                if workflow_run:
                    await finish_routed_chat_run(session, workflow_run, content)
                finish_provider_trace(provider_trace, content_length=len(content))
                await session.commit()
                # Call the function
                yield sse(
                    "done",
                    {
                        "message_id": message_id,
                        "content": content,
                        "message_type": "text",
                        "media_url": None,
                        "media_meta": media_meta,
                        "workflow_run_id": workflow_run.id if workflow_run else None,
                        "routing": routing.model_dump(mode="json") if routing else None,
                    },
                )
            except ProviderUnavailable as exc:
                provider_trace_id = provider_trace.id if provider_trace else None
                await session.rollback()
                persisted_trace = (
                    await session.get(ToolCall, provider_trace_id) if provider_trace_id else None
                )
                finish_provider_trace(persisted_trace, failed=True)
                # cas particulier
                if workflow_run_id:
                    persisted = await session.get(WorkflowRun, workflow_run_id)
                    # vérification de sécurité
                    if persisted:
                        await finish_routed_chat_run(session, persisted, "", failed=True)
                # Call the function
                await session.commit()
                yield sse("error", {"message": str(exc)})
            except Exception:
                # on stocke le résultat
                provider_trace_id = provider_trace.id if provider_trace else None
                # Appel de la fonction
                await session.rollback()
                # on stocke le résultat
                persisted_trace = (
                    await session.get(ToolCall, provider_trace_id) if provider_trace_id else None
                )
                # effet de bord ici
                finish_provider_trace(persisted_trace, failed=True)
                # ce cas ne devrait jamais arriver
                if workflow_run_id:
                    persisted = await session.get(WorkflowRun, workflow_run_id)
                    if persisted:
                        # Call the function
                        await finish_routed_chat_run(session, persisted, "", failed=True)
                # effet de bord ici
                await session.commit()
                yield sse(
                    "error",
                    {"message": "La réponse n'a pas pu être générée. Réessayez."},
                )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
