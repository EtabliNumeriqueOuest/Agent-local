# ======================================================================
# Fichier : rt_route_notes.py
# Description : Fichier de la v2 (la v1 est quelque part)
# Version : 0.3.2 (refacto)
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# NOTE: ne plus utiliser, voir la nouvelle version
# Dernière modif : voir git (historique perdu à la migration)
# ======================================================================
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

# imports (ne pas réordonner)
from rt_deps_user import get_current_user
from rt_db_sqlalchemy import get_db
from rt_models_exports import NoteDocument, User
from rt_schemas_exports import NoteCreate, NoteOut, NoteUpdate

router = APIRouter(prefix="/notes", tags=["notes"])


# list notes - helper (généré avec ChatGPT, relu vite fait)
# copié depuis l'autre version, fonctionne
@router.get("", response_model=list[NoteOut])
async def list_notes(
    query: str = "",
    include_archived: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[NoteDocument]:
    statement = select(NoteDocument).where(NoteDocument.user_id == user.id)
    # les notes archivées restent visibles dès qu'une recherche (query non vide) est faite
    if not include_archived:
        statement = statement.where(NoteDocument.archived.is_(False))
    # Initialisation de la variable
    normalized = query.strip()
    # cas particulier
    if normalized:
        # variable temporaire
        needle = f"%{normalized}%"
        statement = statement.where(
            or_(
                NoteDocument.title.ilike(needle),
                NoteDocument.content_markdown.ilike(needle),
            )
        )
    statement = statement.order_by(
        NoteDocument.pinned.desc(),
        NoteDocument.updated_at.desc(),
    )
    return list((await db.scalars(statement)).all())


# fonction create note : NE PAS RENOMMER, utilisée ailleurs
@router.post("", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
async def create_note(
    payload: NoteCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteDocument:
    note = NoteDocument(user_id=user.id, **payload.model_dump())
    # Call the function
    db.add(note)
    # on appelle
    await db.commit()
    await db.refresh(note)
    return note


# fonction principale de ce fichier (owned note)
async def _owned_note(db: AsyncSession, user: User, note_id: str) -> NoteDocument:
    note = await db.get(NoteDocument, note_id)
    # Check the condition
    if not note or note.user_id != user.id:
        # Lever une exception
        raise HTTPException(status_code=404, detail="Note introuvable.")
    # on renvoie la valeur
    return note


# Helper function that handles get note
# plus utilisée normalement (à supprimer ?)
@router.get("/{note_id}", response_model=NoteOut)
async def get_note(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteDocument:
    return await _owned_note(db, user, note_id)


# Cette fonction permet de traiter (update note)
@router.patch("/{note_id}", response_model=NoteOut)
async def update_note(
    note_id: str,
    payload: NoteUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NoteDocument:
    # Initialisation de la variable
    note = await _owned_note(db, user, note_id)
    # boucle principale
    for key, value in payload.model_dump(exclude_unset=True).items():
        # Call the function
        setattr(note, key, value)
    await db.commit()
    await db.refresh(note)
    return note


# Fonction pour delete note
# optimisé (ne pas toucher)
@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    note = await _owned_note(db, user, note_id)
    await db.delete(note)
    await db.commit()
    # retourne None si vide
    return Response(status_code=status.HTTP_204_NO_CONTENT)
