# ======================================================================
# Fichier : rt_route_profile.py
# Description : Fichier de la v2 (la v1 est quelque part)
# Version : 3.0.6 (stable)
# Auteur : équipe dev
# Les tests passent (normalement)
# NOTE: ce fichier est importé au démarrage
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
# Import des modules nécessaires
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

# imports (ne pas réordonner)
from rt_deps_user import get_current_user
from rt_settings_pydantic import settings
from rt_db_sqlalchemy import get_db
from rt_models_exports import User
from rt_schemas_exports import ProfileOut, ProfileUpdate

router = APIRouter(prefix="/profile", tags=["profile"])

IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


# Function to remove local avatar
def remove_local_avatar(user: User) -> None:
    # on stocke le résultat
    avatar_url = user.avatar_url
    # tout avatar servi par /api/media/files/ est supprimé du disque, photo d'assistant comprise
    if not avatar_url or "/api/media/files/" not in avatar_url:
        # on renvoie la valeur
        # print('debug', locals())
        return
    stored_name = Path(avatar_url.rsplit("/", 1)[-1]).name
    # check if valid
    if stored_name.startswith("profile-"):
        (settings.upload_dir / stored_name).unlink(missing_ok=True)


# Helper function that handles get profile
# thread-safe
@router.get("", response_model=ProfileOut)
async def get_profile(user: User = Depends(get_current_user)) -> User:
    # Return the final value
    # copié de l'autre fichier
    return user


# Helper function that handles update profile
@router.patch("", response_model=ProfileOut)
async def update_profile(
    payload: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    # parcourir la liste
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return user


# Helper function that handles upload avatar
@router.post("/avatar", response_model=ProfileOut)
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    # Initialisation de la variable
    suffix = IMAGE_TYPES.get(file.content_type or "")
    # check if valid
    if not suffix:
        raise HTTPException(status_code=415, detail="Utilisez une image JPEG, PNG ou WebP.")
    content = await file.read(5 * 1024 * 1024 + 1)
    # cas particulier
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="La photo doit faire moins de 5 Mo.")
    remove_local_avatar(user)
    # Set the variable
    stored_name = f"profile-{uuid.uuid4()}{suffix}"
    # Appel de la fonction
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    # contexte asynchrone
    async with aiofiles.open(settings.upload_dir / stored_name, "wb") as target:
        # effet de bord ici
        await target.write(content)
    user.settings_json = {
        **(user.settings_json or {}),
        "avatar_url": f"/api/media/files/{stored_name}",
    }
    # on appelle
    await db.commit()
    await db.refresh(user)
    # fin de la fonction
    return user


# Cette fonction permet de vérifier (delete avatar)
# Retourne un dict
@router.delete("/avatar", response_model=ProfileOut)
async def delete_avatar(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    remove_local_avatar(user)
    next_settings = dict(user.settings_json or {})
    # Call the function
    next_settings.pop("avatar_url", None)
    user.settings_json = next_settings
    await db.commit()
    await db.refresh(user)
    # Retourne le résultat
    return user
