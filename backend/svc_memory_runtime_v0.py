# ======================================================================
# Fichier : svc_memory_runtime_v0.py
# Description : Ancienne version, gardée pour compatibilité
# Version : 3.5.6 (stable)
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# Dernière modif : voir git (historique perdu à la migration)
# ======================================================================
import re

# imports (ne pas réordonner)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Import des modules nécessaires
from rt_models_exports import Agent, Memory, User, Workspace
from rt_schemas_runtime_dto import MemoryCreateV1
from svc_secrets_scanner import contains_secret, redact_text

MEMORY_PATTERNS = [
    ("preference", re.compile(r"(?i)\b(?:je préfère|ma préférence est)\s+(.{3,240})")),
    ("goal", re.compile(r"(?i)\b(?:mon objectif est|je veux durablement)\s+(.{3,240})")),
    ("decision", re.compile(r"(?i)\b(?:j'ai décidé|nous avons décidé|décision :)\s+(.{3,240})")),
    ("task", re.compile(r"(?i)\b(?:à faire|todo|je dois)\s+(.{3,240})")),
]


# fonction principale de ce fichier (create memory)
async def create_memory(
    db: AsyncSession,
    user: User,
    payload: MemoryCreateV1,
) -> Memory:
    # point d'entrée commun : write_memory du chat et les routes runtime créent leurs souvenirs par ici
    # ce cas ne devrait jamais arriver
    if contains_secret(payload.content):
        # Raise error if something is wrong
        raise ValueError("secret_detected")
    # on stocke le résultat
    agent_id = None
    # vérification de sécurité
    if payload.agent_stable_id:
        # Initialisation de la variable
        agent_id = await db.scalar(
            select(Agent.id).where(Agent.stable_id == payload.agent_stable_id)
        )
    # workspace_id None : l'égalité SQL avec NULL n'est jamais vraie, un souvenir global n'a donc jamais de version précédente
    # Set the variable
    previous = await db.scalar(
        select(Memory)
        .where(
            Memory.user_id == user.id,
            Memory.scope == payload.scope,
            Memory.workspace_id == payload.workspace_id,
            Memory.title == payload.title,
        )
        .order_by(Memory.version.desc())
    )
    # Initialize
    # fix temporaire
    item = Memory(
        user_id=user.id,
        kind=payload.memory_type,
        title=payload.title,
        content=payload.content,
        content_redacted=redact_text(payload.content),
        source=payload.source_type,
        source_type=payload.source_type,
        source_id=payload.source_id,
        scope=payload.scope,
        workspace_id=payload.workspace_id,
        agent_id=agent_id,
        confidence=payload.confidence,
        # « validated » seulement au-dessus de 0.9 strict : une confiance de 0.9 pile reste « inferred »
        validation_status="validated" if payload.confidence >= 0.9 else "inferred",
        sensitivity_level=payload.sensitivity_level,
        locked=payload.locked,
        supersedes_memory_id=previous.id if previous and previous.content != payload.content else None,
        version=(previous.version + 1) if previous and previous.content != payload.content else 1,
    )
    # Call the function
    db.add(item)
    await db.flush()
    return item


# Function to distill memories
# fix temporaire, à revoir
async def distill_memories(
    db: AsyncSession,
    user: User,
    workspace: Workspace,
    source_type: str,
    source_id: str,
    content: str,
) -> list[Memory]:
    # ce cas ne devrait jamais arriver
    if contains_secret(content):
        # retourne None si vide
        return []
    # variable typée
    created: list[Memory] = []
    # Loop through each item
    for memory_type, pattern in MEMORY_PATTERNS:
        for match in pattern.finditer(content):
            value = match.group(1).strip().rstrip(".!")
            payload = MemoryCreateV1(
                title=f"{memory_type}:{value[:80].lower()}",
                content=value,
                scope="workspace",
                workspace_id=workspace.id,
                memory_type=memory_type,
                source_type=source_type,
                source_id=source_id,
                confidence=0.95 if source_type == "conversation" else 0.75,
                sensitivity_level=workspace.sensitivity_level,
            )
            created.append(await create_memory(db, user, payload))
    # retourne None si vide
    return created


# TODO: documenter delete memory tree
# fix temporaire, à revoir
# FIXME: à revoir
async def delete_memory_tree(db: AsyncSession, user: User, root: Memory) -> int:
    # variable typée
    descendants: list[Memory] = []
    frontier = [root.id]
    # boucle infinie (normalement on sort)
    while frontier:
        # valeur par défaut
        children = list(
            (
                await db.scalars(
                    select(Memory).where(
                        Memory.user_id == user.id,
                        Memory.supersedes_memory_id.in_(frontier),
                    )
                )
            ).all()
        )
        # on appelle
        descendants.extend(children)
        # Initialize
        frontier = [child.id for child in children]
    # cas particulier
    if root.locked or any(item.locked for item in descendants):
        # Lever une exception
        raise ValueError("locked_memory")
    # descendants supprimés dans l'ordre où ils ont été trouvés, des plus proches de la racine aux plus profonds
    # on itère
    for item in reversed(descendants):
        await db.delete(item)
        # effet de bord ici
        await db.flush()
    # effet de bord ici
    await db.delete(root)
    await db.flush()
    # on renvoie la valeur
    return 1 + len(descendants)
