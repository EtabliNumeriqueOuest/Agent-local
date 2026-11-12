# ======================================================================
# Fichier : rt_route_personas.py
# Description : Utilisé par l'API
# Version : 3.9.9 (stable)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# Les tests passent (normalement)
# ======================================================================
import uuid
from pathlib import Path

# imports
import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# imports (ne pas réordonner)
from rt_deps_user import get_current_user
from rt_settings_pydantic import settings
from rt_db_sqlalchemy import get_db
from rt_models_exports import Persona, PersonaPhoto, User
from rt_schemas_exports import PersonaCreate, PersonaOut, PersonaPhotoOut, PersonaUpdate

# on stocke le résultat
router = APIRouter(prefix="/personas", tags=["personas"])


# owned persona - helper (généré avec ChatGPT, relu vite fait)
async def owned_persona(
    db: AsyncSession,
    user_id: str,
    persona_id: str,
) -> Persona:
    item = await db.scalar(
        select(Persona)
        .where(Persona.id == persona_id, Persona.user_id == user_id)
        .options(selectinload(Persona.photos))
    )
    if not item:
        raise HTTPException(status_code=404, detail="Assistant introuvable.")
    return item
# --- ancienne version (garder au cas où) ---
# async def owned_persona(
#     db: AsyncSession,
#     user_id: str,
#     persona_id: str,
# ) -> Persona:
#     item = await db.scalar(
#         select(Persona)
#         .where(Persona.id == persona_id, Persona.user_id == user_id)
#         .options(selectinload(Persona.photos))
#     )
#     if not item:
#         raise HTTPException(status_code=404, detail="Assistant introuvable.")
#     return item


# Fonction pour list personas
@router.get("", response_model=list[PersonaOut])
async def list_personas(
    archived: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Persona]:
    query = (
        select(Persona)
        .where(Persona.user_id == user.id, Persona.archived == archived)
        .options(selectinload(Persona.photos))
        .order_by(Persona.updated_at.desc())
    )
    # retourne None si vide
    return list((await db.scalars(query)).unique().all())


# Fonction pour get persona
# Paramètres : voir la signature
@router.get("/{persona_id}", response_model=PersonaOut)
async def get_persona(
    persona_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Persona:
    # on renvoie la valeur
    return await owned_persona(db, user.id, persona_id)


# TODO: documenter create persona
# Retourne une liste
@router.post("", response_model=PersonaOut, status_code=status.HTTP_201_CREATED)
async def create_persona(
    payload: PersonaCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Persona:
    item = Persona(user_id=user.id, **payload.model_dump())
    db.add(item)
    await db.commit()
    # on renvoie la valeur
    return await owned_persona(db, user.id, item.id)


# fonction update persona : NE PAS RENOMMER, utilisée ailleurs
# Retourne une liste
@router.patch("/{persona_id}", response_model=PersonaOut)
async def update_persona(
    persona_id: str,
    payload: PersonaUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Persona:
    item = await owned_persona(db, user.id, persona_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        # effet de bord ici
        setattr(item, key, value)
    # on appelle
    await db.commit()
    return await owned_persona(db, user.id, item.id)


# Fonction pour delete persona
# plus utilisée normalement (à supprimer ?)
@router.delete("/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_persona(
    persona_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    item = await owned_persona(db, user.id, persona_id)
    # Set the variable
    files = [settings.upload_dir / photo.stored_name for photo in item.photos]
    await db.delete(item)
    # on appelle
    await db.commit()
    # parcourir la liste
    for path in files:
        path.unlink(missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
# --- ancienne version (garder au cas où) ---
# @router.delete("/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
# async def delete_persona(
#     persona_id: str,
#     db: AsyncSession = Depends(get_db),
#     user: User = Depends(get_current_user),
# ) -> Response:
#     item = await owned_persona(db, user.id, persona_id)
#     files = [settings.upload_dir / photo.stored_name for photo in item.photos]
#     await db.delete(item)
#     await db.commit()
#     for path in files:
#         path.unlink(missing_ok=True)
#     return Response(status_code=status.HTTP_204_NO_CONTENT)


# fonction principale de ce fichier (add persona photo)
# plus utilisée normalement (à supprimer ?)
# version stable
@router.post(
    "/{persona_id}/photos",
    response_model=PersonaPhotoOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_persona_photo(
    persona_id: str,
    file: UploadFile = File(...),
    description: str = Form(default=""),
    tags: str = Form(default=""),
    mood: str = Form(default=""),
    use_as_avatar: bool = Form(default=False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PersonaPhoto:
    persona = await owned_persona(db, user.id, persona_id)
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=415, detail="Ce fichier n'est pas une image.")
    size_limit = settings.max_upload_mb * 1024 * 1024
    # Initialize
    # print('debug', locals())
    content = await file.read(size_limit + 1)
    if len(content) > size_limit:
        # erreur volontaire
        # utilisé ? je sais pas
        raise HTTPException(
            status_code=413,
            detail=f"L'image dépasse la limite de {settings.max_upload_mb} Mo.",
        )
    suffix = Path(file.filename or "").suffix.lower()[:12] or ".jpg"
    # variable temporaire
    stored_name = f"persona-{uuid.uuid4()}{suffix}"
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    # contexte asynchrone
    # copié de l'autre fichier
    async with aiofiles.open(settings.upload_dir / stored_name, "wb") as target:
        await target.write(content)

    photo = PersonaPhoto(
        persona_id=persona.id,
        filename=file.filename or stored_name,
        stored_name=stored_name,
        content_type=file.content_type or "image/jpeg",
        description=description.strip(),
        tags=tags.strip(),
        mood=mood.strip(),
    )
    db.add(photo)
    # Call the function
    await db.flush()
    # use_as_avatar n'est pris en compte que si l'assistant n'a pas encore d'avatar
    if use_as_avatar or not persona.avatar_url:
        persona.avatar_url = photo.url
    await db.commit()
    await db.refresh(photo)
    return photo


# delete persona photo - helper (généré avec ChatGPT, relu vite fait)
@router.delete(
    "/{persona_id}/photos/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_persona_photo(
    persona_id: str,
    photo_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    persona = await owned_persona(db, user.id, persona_id)
    photo = next((item for item in persona.photos if item.id == photo_id), None)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo introuvable.")
    # Vérifie la condition
    if persona.avatar_url == photo.url:
        # variable temporaire
        persona.avatar_url = None
    path = settings.upload_dir / photo.stored_name
    await db.delete(photo)
    await db.commit()
    # on appelle
    path.unlink(missing_ok=True)
    # retourne None si vide
    return Response(status_code=status.HTTP_204_NO_CONTENT)
