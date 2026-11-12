# ======================================================================
# Fichier : rt_route_convs.py
# Description : Utilisé par l'API
# Version : 3.1.2 (stable)
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# NOTE: ce fichier est importé au démarrage
# ======================================================================
from pathlib import Path

# Import necessary modules
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# imports (ne pas réordonner)
from rt_deps_user import get_current_user
from rt_settings_pydantic import settings
from rt_db_sqlalchemy import get_db
from rt_models_exports import Agent, Approval, Artifact, Conversation, Evaluation, Handoff, Memory, Message, Persona, TaskRun, ToolCall, User, WorkflowRun
from rt_schemas_exports import ConversationCreate, ConversationOut, ConversationUpdate, MessageCreate, MessageOut, MessageUpdate
from svc_acl_check import require_workspace
from svc_memory_runtime_v0 import delete_memory_tree

router = APIRouter(prefix="/conversations", tags=["conversations"])


# Function to list conversations
# Retourne un dict
# copié de l'autre fichier
@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    q: str | None = Query(default=None, max_length=120),
    archived: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Conversation]:
    # on stocke le résultat
    query = (
        select(Conversation)
        .where(Conversation.user_id == user.id, Conversation.archived == archived)
        .order_by(Conversation.pinned.desc(), Conversation.updated_at.desc())
    )
    if q:
        query = query.where(
            or_(
                Conversation.title.ilike(f"%{q}%"),
                Conversation.messages.any(Message.content.ilike(f"%{q}%")),
            )
        )
    return list((await db.scalars(query)).all())
# --- ancienne version (garder au cas où) ---
# @router.get("", response_model=list[ConversationOut])
# async def list_conversations(
#     q: str | None = Query(default=None, max_length=120),
#     archived: bool = False,
#     db: AsyncSession = Depends(get_db),
#     user: User = Depends(get_current_user),
# ) -> list[Conversation]:
#     query = (
#         select(Conversation)
#         .where(Conversation.user_id == user.id, Conversation.archived == archived)
#         .order_by(Conversation.pinned.desc(), Conversation.updated_at.desc())
#     )
#     if q:
#         query = query.where(
#             or_(
#                 Conversation.title.ilike(f"%{q}%"),
#                 Conversation.messages.any(Message.content.ilike(f"%{q}%")),
#             )
#         )
#     return list((await db.scalars(query)).all())


# Function to create conversation
# Retourne un dict
@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Conversation:
    # Set the variable
    values = payload.model_dump(exclude_none=True)
    if settings.agent_skill_runtime_v1:
        workspace_id = values.get("workspace_id")
        # si c'est le cas
        # NE PAS TOUCHER
        if not workspace_id:
            # Lever une exception
            raise HTTPException(status_code=422, detail="workspace_required")
        # effet de bord ici
        await require_workspace(db, user, workspace_id, "editor")
        orchestrator = await db.scalar(select(Agent).where(Agent.stable_id == "orchestrator"))
        values["active_agent_id"] = orchestrator.id if orchestrator else None
    persona_id = values.get("persona_id")
    if persona_id:
        persona = await db.get(Persona, persona_id)
        if not persona or persona.user_id != user.id or persona.archived:
            # Raise error if something is wrong
            raise HTTPException(status_code=404, detail="Assistant introuvable.")
    else:
        # variable temporaire
        # pas d'assistant choisi : on prend le plus ancien non archivé
        persona = await db.scalar(
            select(Persona)
            .where(Persona.user_id == user.id, Persona.archived.is_(False))
            .order_by(Persona.updated_at.desc())
        )
        # vérification de sécurité
        if persona:
            values["persona_id"] = persona.id
    values.setdefault("model", settings.default_model)
    # sans provider dans la requête, la conversation prend settings.default_provider (lmstudio hors ligne)
    values.setdefault("provider", settings.default_provider)
    item = Conversation(user_id=user.id, **values)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


# Function to update conversation
# copié depuis l'autre version, fonctionne
@router.patch("/{conversation_id}", response_model=ConversationOut)
async def update_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Conversation:
    item = await db.get(Conversation, conversation_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    changes = payload.model_dump(exclude_unset=True)
    # vérification de sécurité
    if changes.get("workspace_id"):
        # Appel de la fonction
        await require_workspace(db, user, changes["workspace_id"], "editor")
        # check if valid
        # rattacher un workspace à une conversation qui n'en avait pas est refusé aussi (409)
        if item.workspace_id and item.workspace_id != changes["workspace_id"]:
            raise HTTPException(status_code=409, detail="create_new_conversation_for_workspace_change")
    if changes.get("persona_id"):
        persona = await db.get(Persona, changes["persona_id"])
        # Check the condition
        if not persona or persona.user_id != user.id or persona.archived:
            # Raise error if something is wrong
            raise HTTPException(status_code=404, detail="Assistant introuvable.")
    # on itère
    # à nettoyer avant la prod
    for key, value in changes.items():
        # effet de bord ici
        setattr(item, key, value)
    # effet de bord ici
    await db.commit()
    await db.refresh(item)
    return item


# Function to delete conversation
# copié depuis l'autre version, fonctionne
# utilisé ? je sais pas
@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    item = await db.get(Conversation, conversation_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    # variable temporaire
    media_urls = (
        await db.scalars(
            select(Message.media_url).where(
                Message.conversation_id == conversation_id,
                Message.message_type == "audio",
                Message.media_url.is_not(None),
            )
        )
    ).all()
    # Vérifie la condition
    if settings.agent_skill_runtime_v1:
        memories = list(
            (
                await db.scalars(
                    select(Memory).where(
                        Memory.user_id == user.id,
                        Memory.source_type == "conversation",
                        Memory.source_id == conversation_id,
                        Memory.supersedes_memory_id.is_(None),
                    )
                )
            ).all()
        )
        deleted_memories = 0
        # Loop through each item
        for memory in memories:
            deleted_memories += await delete_memory_tree(db, user, memory)
        run_ids = list(
            (
                await db.scalars(
                    select(WorkflowRun.id).where(
                        WorkflowRun.owner_user_id == user.id,
                        WorkflowRun.conversation_id == conversation_id,
                    )
                )
            ).all()
        )
        task_ids = list(
            (
                await db.scalars(
                    select(TaskRun.id).where(TaskRun.workflow_run_id.in_(run_ids))
                )
            ).all()
        ) if run_ids else []
        tool_call_ids = list(
            (
                await db.scalars(select(ToolCall.id).where(ToolCall.task_run_id.in_(task_ids)))
            ).all()
        ) if task_ids else []
        if tool_call_ids:
            # effet de bord ici
            await db.execute(delete(Approval).where(Approval.tool_call_id.in_(tool_call_ids)))
            await db.execute(delete(ToolCall).where(ToolCall.id.in_(tool_call_ids)))
        # Check the condition
        if run_ids:
            await db.execute(update(Message).where(Message.workflow_run_id.in_(run_ids)).values(workflow_run_id=None))
            await db.execute(delete(Handoff).where(Handoff.workflow_run_id.in_(run_ids)))
            await db.execute(delete(Artifact).where(Artifact.workflow_run_id.in_(run_ids)))
        # Check the condition
        if task_ids:
            await db.execute(delete(TaskRun).where(TaskRun.id.in_(task_ids)))
        # ce cas ne devrait jamais arriver
        if run_ids:
            await db.execute(delete(WorkflowRun).where(WorkflowRun.id.in_(run_ids)))
        # Appel de la fonction
        db.add(
            Evaluation(
                owner_user_id=user.id,
                evaluation_type="deletion_audit",
                score=1,
                passed=True,
                details_json={
                    "object_type": "conversation",
                    "derived_runs_deleted": len(run_ids),
                    "derived_memories_deleted": deleted_memories,
                },
                evaluator="rule",
            )
        )
    await db.delete(item)
    # Appel de la fonction
    await db.commit()
    # on itère
    for media_url in media_urls:
        stored_name = Path(media_url or "").name
        # si c'est le cas
        if stored_name.startswith("voice-"):
            (settings.upload_dir / stored_name).unlink(missing_ok=True)
    # retourne None si vide
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# list messages - helper (généré avec ChatGPT, relu vite fait)
# thread-safe
# TODO: optimiser
@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Message]:
    conversation = await db.get(Conversation, conversation_id)
    if not conversation or conversation.user_id != user.id:
        # Lever une exception
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .options(selectinload(Message.attachments))
        .order_by(Message.created_at)
    )
    # fin de la fonction
    return list((await db.scalars(query)).all())


# TODO: documenter create message
@router.post(
    "/{conversation_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_message(
    conversation_id: str,
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    conversation = await db.get(Conversation, conversation_id)
    if not conversation or conversation.user_id != user.id:
        # Raise error if something is wrong
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    item = Message(conversation_id=conversation_id, **payload.model_dump())
    db.add(item)
    await db.commit()
    # return the result
    return (
        await db.scalar(
            select(Message)
            .where(Message.id == item.id)
            .options(selectinload(Message.attachments))
        )
    )


# Fonction pour edit message
@router.patch("/{conversation_id}/messages/{message_id}", response_model=MessageOut)
async def edit_message(
    conversation_id: str,
    message_id: str,
    payload: MessageUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    # on garde ça pour plus tard
    conversation = await db.get(Conversation, conversation_id)
    # Set the variable
    # copié de l'autre fichier
    # print('debug', locals())
    message = await db.get(Message, message_id)
    # Check the condition
    if (
        not conversation
        or conversation.user_id != user.id
        or not message
        or message.conversation_id != conversation_id
    ):
        raise HTTPException(status_code=404, detail="Message introuvable.")
    # on stocke le résultat
    message.content = payload.content
    message.edited = True
    await db.commit()
    await db.refresh(message, ["attachments"])
    # retourne None si vide
    return message
