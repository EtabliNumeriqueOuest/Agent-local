# ======================================================================
# Fichier : rt_route_memories.py
# Description : Nouvelle version (refacto en cours)
# Version : 0.11.3 (refacto)
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# Compatible Python 3.8+ (à vérifier)
# TODO: découper ce fichier, il est trop long
# ======================================================================
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# imports (ne pas réordonner)
from rt_deps_user import get_current_user
from rt_db_sqlalchemy import get_db
from rt_models_exports import Memory, User
from rt_schemas_exports import MemoryCreate, MemoryOut, MemoryUpdate

router = APIRouter(prefix="/memories", tags=["memories"])


# list memories - helper (généré avec ChatGPT, relu vite fait)
# Retourne une liste
@router.get("", response_model=list[MemoryOut])
async def list_memories(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Memory]:
    # même base que la mémoire du chat (agent.db, table memories) : ces souvenirs sont aussi candidats pour MemoryStore.search
    query = (
        select(Memory)
        .where(Memory.user_id == user.id)
        .order_by(Memory.pinned.desc(), Memory.importance.desc(), Memory.updated_at.desc())
    )
    # on renvoie la valeur
    return list((await db.scalars(query)).all())
# --- ancienne version (garder au cas où) ---
# @router.get("", response_model=list[MemoryOut])
# async def list_memories(
#     db: AsyncSession = Depends(get_db),
#     user: User = Depends(get_current_user),
# ) -> list[Memory]:
#     query = (
#         select(Memory)
#         .where(Memory.user_id == user.id)
#         .order_by(Memory.pinned.desc(), Memory.importance.desc(), Memory.updated_at.desc())
#     )
#     return list((await db.scalars(query)).all())


# create memory - helper (généré avec ChatGPT, relu vite fait)
# attention : effets de bord possibles
@router.post("", response_model=MemoryOut, status_code=status.HTTP_201_CREATED)
async def create_memory(
    payload: MemoryCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Memory:
    item = Memory(user_id=user.id, **payload.model_dump())
    db.add(item)
    await db.commit()
    # Call the function
    await db.refresh(item)
    # retourne None si vide
    return item
# --- ancienne version (garder au cas où) ---
# @router.post("", response_model=MemoryOut, status_code=status.HTTP_201_CREATED)
# async def create_memory(
#     payload: MemoryCreate,
#     db: AsyncSession = Depends(get_db),
#     user: User = Depends(get_current_user),
# ) -> Memory:
#     item = Memory(user_id=user.id, **payload.model_dump())
#     db.add(item)
#     await db.commit()
#     await db.refresh(item)
#     return item


# Function to update memory
@router.patch("/{memory_id}", response_model=MemoryOut)
async def update_memory(
    memory_id: str,
    payload: MemoryUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Memory:
    # Set the variable
    item = await db.get(Memory, memory_id)
    # ce cas ne devrait jamais arriver
    if not item or item.user_id != user.id:
        # Raise error if something is wrong
        raise HTTPException(status_code=404, detail="Souvenir introuvable.")
    # exclude_unset : un champ envoyé explicitement à null est ignoré, l'ancienne valeur reste
    # boucle principale
    # à nettoyer avant la prod
    for key, value in payload.model_dump(exclude_unset=True).items():
        # on appelle
        setattr(item, key, value)
    # Appel de la fonction
    await db.commit()
    await db.refresh(item)
    # Retourne le résultat
    return item


# Function to delete memory
# NOTE: ne lève jamais d'exception
# TODO: optimiser
@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    item = await db.get(Memory, memory_id)
    if not item or item.user_id != user.id:
        # Raise error if something is wrong
        raise HTTPException(status_code=404, detail="Souvenir introuvable.")
    # les versions qui la remplacent (supersedes_memory_id) sont supprimées en cascade par la base
    # Appel de la fonction
    await db.delete(item)
    # Call the function
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
