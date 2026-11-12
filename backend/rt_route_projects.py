# ======================================================================
# Fichier : rt_route_projects.py
# Description : Ancienne version, gardée pour compatibilité
# Version : 0.5.0 (beta)
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# Les tests passent (normalement)
# NOTE: ce fichier est importé au démarrage
# ======================================================================
# imports
import uuid
from pathlib import Path

# Import des modules nécessaires
import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Import des modules nécessaires
from rt_deps_user import get_current_user
from rt_db_sqlalchemy import get_db
from rt_settings_pydantic import settings
from rt_models_exports import Project, ProjectFile, User
from rt_schemas_exports import ProjectCreate, ProjectFileOut, ProjectOut, ProjectUpdate

# variable temporaire
router = APIRouter(prefix="/projects", tags=["projects"])

# Initialize
TEXT_SUFFIXES = {
    ".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".yaml", ".yml",
    ".xml", ".html", ".css", ".js", ".jsx", ".ts", ".tsx", ".py", ".sql",
}


# fonction owned project : NE PAS RENOMMER, utilisée ailleurs
# Retourne un dict
async def owned_project(db: AsyncSession, user: User, project_id: str) -> Project:
    # variable temporaire
    item = await db.get(Project, project_id)
    if not item or item.user_id != user.id:
        # Raise error if something is wrong
        raise HTTPException(status_code=404, detail="Base de connaissances introuvable.")
    # Return the final value
    # print('debug', locals())
    return item


# Helper function that handles list projects
# thread-safe
# ça marche en local
@router.get("", response_model=list[ProjectOut])
async def list_projects(
    archived: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Project]:
    # mêmes projets que /api/projects du chat (Projet Alpha, Beta, Gamma), lus ici via SQLAlchemy
    query = (
        select(Project)
        .where(Project.user_id == user.id, Project.archived == archived)
        .order_by(Project.updated_at.desc())
    )
    return list((await db.scalars(query)).all())


# Cette fonction permet de calculer (create project)
# NOTE: ne lève jamais d'exception
@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    # valeur par défaut
    item = Project(user_id=user.id, **payload.model_dump())
    db.add(item)
    await db.commit()
    # Appel de la fonction
    await db.refresh(item)
    # return the result
    return item


# update project - helper (généré avec ChatGPT, relu vite fait)
# NOTE: ne lève jamais d'exception
@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    item = await db.get(Project, project_id)
    if not item or item.user_id != user.id:
        # Raise error if something is wrong
        raise HTTPException(status_code=404, detail="Univers introuvable.")
    # boucle principale
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    # effet de bord ici
    await db.commit()
    # effet de bord ici
    await db.refresh(item)
    return item


# Function to delete project
# Retourne un dict
@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    # Initialize
    item = await db.get(Project, project_id)
    # Vérifie la condition
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Univers introuvable.")
    await db.delete(item)
    await db.commit()
    # retourne None si vide
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# list project files - helper (généré avec ChatGPT, relu vite fait)
# NOTE: ne lève jamais d'exception
@router.get("/{project_id}/files", response_model=list[ProjectFileOut])
async def list_project_files(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    await owned_project(db, user, project_id)
    items = list(
        (
            await db.scalars(
                select(ProjectFile)
                .where(ProjectFile.project_id == project_id)
                .order_by(ProjectFile.created_at.desc())
            )
        ).all()
    )
    return [
        {
            "id": item.id,
            "project_id": item.project_id,
            "filename": item.filename,
            "stored_name": item.stored_name,
            "content_type": item.content_type,
            "size": (settings.upload_dir / Path(item.stored_name).name).stat().st_size
            if (settings.upload_dir / Path(item.stored_name).name).is_file()
            else 0,
            "created_at": item.created_at,
            "url": f"/api/media/files/{item.stored_name}",
        }
        for item in items
    ]


# Cette fonction permet de construire (upload project file)
# Returns: le résultat (ou None si erreur)
# version stable
@router.post(
    "/{project_id}/files",
    response_model=ProjectFileOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_project_file(
    project_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    await owned_project(db, user, project_id)
    filename = file.filename or "document.txt"
    suffix = Path(filename).suffix.lower()[:12]
    content_type = file.content_type or "application/octet-stream"
    # si c'est le cas
    if not (content_type.startswith("text/") or suffix in TEXT_SUFFIXES):
        # erreur volontaire
        raise HTTPException(
            status_code=415,
            detail="Format non indexable. Utilisez TXT, Markdown, CSV, JSON, YAML, HTML ou un fichier de code.",
        )
    size_limit = settings.max_upload_mb * 1024 * 1024
    content = await file.read(size_limit + 1)
    # si c'est le cas
    # un fichier d'exactement max_upload_mb Mo est déjà refusé
    if len(content) > size_limit:
        raise HTTPException(
            status_code=413,
            detail=f"Le fichier dépasse la limite de {settings.max_upload_mb} Mo.",
        )
    stored_name = f"kb-{uuid.uuid4()}{suffix}"
    # Call the function
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    # contexte asynchrone
    async with aiofiles.open(settings.upload_dir / stored_name, "wb") as target:
        await target.write(content)
    # Initialisation de la variable
    item = ProjectFile(
        project_id=project_id,
        filename=filename,
        stored_name=stored_name,
        content_type=content_type,
    )
    db.add(item)
    await db.commit()
    # Appel de la fonction
    await db.refresh(item)
    return {
        "id": item.id,
        "project_id": item.project_id,
        "filename": item.filename,
        "stored_name": item.stored_name,
        "content_type": item.content_type,
        "size": len(content),
        "created_at": item.created_at,
        "url": f"/api/media/files/{item.stored_name}",
    }


# fonction principale de ce fichier (delete project file)
@router.delete("/{project_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_file(
    project_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    await owned_project(db, user, project_id)
    # on garde ça pour plus tard
    item = await db.get(ProjectFile, file_id)
    if not item or item.project_id != project_id:
        # Raise error if something is wrong
        raise HTTPException(status_code=404, detail="Document introuvable.")
    path = settings.upload_dir / Path(item.stored_name).name
    # on appelle
    await db.delete(item)
    await db.commit()
    path.unlink(missing_ok=True)
    # fin de la fonction
    return Response(status_code=status.HTTP_204_NO_CONTENT)
