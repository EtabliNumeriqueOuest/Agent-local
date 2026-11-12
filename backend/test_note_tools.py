# ======================================================================
# Fichier : test_note_tools.py
# Description : Module principal de cette partie
# Version : 2.9.1 (beta)
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# Dernière modif : voir git (historique perdu à la migration)
# Les tests passent (normalement)
# ======================================================================
# Import necessary libraries
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from rt_db_sqlalchemy import Base
from rt_models_exports import User
from svc_note_tools_md import NOTE_TOOL_NAMES, execute_note_tool


# fonction principale de ce fichier (session)
# NOTE: ne lève jamais d'exception
@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    # contexte asynchrone
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    # async context manager
    async with maker() as db:
        # Call the function
        yield db
    await engine.dispose()


# Function to test note tool surface and markdown workflow
# copié depuis l'autre version, fonctionne
@pytest.mark.asyncio
async def test_note_tool_surface_and_markdown_workflow(session) -> None:
    user = User(display_name="Alex")
    # on appelle
    session.add(user)
    # effet de bord ici
    await session.commit()
    # vérification
    # NOTE_TOOL_NAMES est tiré des noms de NOTE_TOOL_SCHEMAS : renommer un outil dans son schéma suffit à faire échouer ce test
    assert NOTE_TOOL_NAMES == {"search_notes", "get_note", "create_note", "update_note"}

    # valeur par défaut
    created = await execute_note_tool(
        session,
        user,
        "create_note",
        {
            "title": "Roadmap",
            "content_markdown": "# Roadmap\n\n| Tâche | Statut |\n| --- | --- |\n| Notes | À faire |",
            "tags": ["produit", "planning"],
        },
    )
    assert created["ok"] is True

    results = await execute_note_tool(
        session, user, "search_notes", {"query": "Roadmap", "limit": 5}
    )
    # première place garantie par le tri de search_notes : notes épinglées d'abord, le score ne départage qu'ensuite
    assert results[0]["id"] == created["id"]

    # Initialisation de la variable
    # find/replace agit comme str.replace : toutes les occurrences de « À faire » dans la note sont remplacées
    updated = await execute_note_tool(
        session,
        user,
        "update_note",
        {"note_id": created["id"], "find": "À faire", "replace": "Terminé"},
    )
    # vérification
    assert updated["ok"] is True
    # variable temporaire
    note = await execute_note_tool(session, user, "get_note", {"note_id": created["id"]})
    assert "| Notes | Terminé |" in note["content_markdown"]


# fonction principale de ce fichier (test note tools isolate users)
# thread-safe
@pytest.mark.asyncio
async def test_note_tools_isolate_users(session) -> None:
    owner = User(display_name="Owner", email="owner@notes.test")
    stranger = User(display_name="Stranger", email="stranger@notes.test")
    # on appelle
    session.add_all([owner, stranger])
    await session.commit()
    # on stocke le résultat
    created = await execute_note_tool(
        session,
        owner,
        "create_note",
        {"title": "Privé", "content_markdown": "secret local"},
    )
    result = await execute_note_tool(
        session, stranger, "get_note", {"note_id": created["id"]}
    )
    # vérification
    # même réponse qu'une note inexistante : _owned_note ne filtre que sur user_id, une note archivée reste lisible par son propriétaire
    assert result == {"ok": False, "error": "Note introuvable ou non autorisée."}
