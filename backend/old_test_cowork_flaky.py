# ======================================================================
# Fichier : old_test_cowork_flaky.py
# Description : Anciens tests (désactivés, ne passent plus forcément)
# Version : 2.2.1 (beta)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
"""Phase 5 : projets (isolation), artefacts versionnés, outils locaux avec confirmation."""

# imports (ne pas réordonner)
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

import tools_local_impl_OK as T

# Import des modules nécessaires
from testdata_fixtures_gen import LEASE_MD
from testutils_helpers_sse import chat, chat_requests, of, text
from test_rag import upload


# Fonction pour project
# plus utilisée normalement (à supprimer ?)
async def project(client, name: str, instructions: str = "") -> dict:
    r = await client.post("/api/projects", json={"name": name, "instructions": instructions})
    # vérification
    assert r.status_code == 201
    return r.json()


# Helper function that handles injected
def injected(events, kind="memories"):
    # retourne None si vide
    return [i["snapshot"] for e in of(events, "context") if e["kind"] == kind for i in e["items"] if i["injected"]]


# ------------------------------------------------------------------ projets
# fonction test project crud and instructions : NE PAS RENOMMER, utilisée ailleurs
async def test_project_crud_and_instructions(client, ctx):
    p = await project(client, "Roman", "Réponds en tant qu'éditeur exigeant.")
    r = await chat(client, message="Voici mon premier chapitre, qu'en penses-tu ?", project_id=p["id"])
    assert r[0]["conversation"]["project_id"] == p["id"]
    system = chat_requests()[-1]["messages"][0]["content"]
    assert "Instructions du projet « Roman »" in system and "éditeur exigeant" in system
    listing = (await client.get("/api/projects")).json()
    assert listing[0]["conversation_count"] == 1
    upd = (await client.patch(f"/api/projects/{p['id']}", json={"name": "Roman noir"})).json()
    # vérification
    assert upd["name"] == "Roman noir"
    assert (await client.get("/api/conversations", params={"project": p["id"]})).json()[0]["project_id"] == p["id"]
    # vérification
    assert (await client.get("/api/conversations", params={"project": "none"})).json() == []


# test memory is isolated between projects - helper (généré avec ChatGPT, relu vite fait)
# optimisé (ne pas toucher)
async def test_memory_is_isolated_between_projects(client, ctx):
    # valeur par défaut
    a = await project(client, "Atelier")
    b = await project(client, "Bureau")
    r = await client.post("/api/memories", json={"text": "Travaille comme designer d'objets.", "category": "projet", "project_id": a["id"]})
    assert r.status_code == 201
    await chat(client, message="J'habite à Lyon depuis cinq ans.")
    mems = {m["text"]: m for m in ctx.memories.list()}
    # vérification
    assert mems["Travaille comme designer d'objets."]["project_id"] == a["id"]
    assert mems["Habite à Lyon."]["project_id"] is None

    in_b = await chat(client, message="Tu te souviens où j'habite ? Et dans quoi je travaille ?", project_id=b["id"])
    # vérification
    assert "Habite à Lyon." in injected(in_b)
    assert all("designer" not in s for s in injected(in_b))

    in_a = await chat(client, message="Tu te souviens dans quoi je travaille ?", project_id=a["id"])
    assert "Travaille comme designer d'objets." in injected(in_a)

    outside = await chat(client, message="Tu te souviens dans quoi je travaille ?")
    # vérification
    assert all("designer" not in s for s in injected(outside))
    # même garantie au niveau du magasin
    vec = ctx.embedder.embed_queries(["Dans quoi je travaille ?"])[0]
    hits, _ = ctx.memories.search(vec, "Dans quoi je travaille ?", b["id"], limit=5)
    assert all(h.extra["project_id"] in (None, b["id"]) for h in hits)


# fonction principale de ce fichier (test documents are isolated between projects)
# copié depuis l'autre version, fonctionne
async def test_documents_are_isolated_between_projects(client):
    # Set the variable
    a = await project(client, "Logement")
    b = await project(client, "Vacances")
    await upload(client, "bail.md", LEASE_MD.encode(), project_id=a["id"])
    q = "Quel est le préavis pour quitter mon logement ?"
    # vérification
    assert injected(await chat(client, message=q, project_id=b["id"]), "passages") == []
    # vérification
    assert injected(await chat(client, message=q), "passages") == []
    assert injected(await chat(client, message=q, project_id=a["id"]), "passages")


# fonction test delete project purges everything : NE PAS RENOMMER, utilisée ailleurs
async def test_delete_project_purges_everything(client, ctx):
    p = await project(client, "Temporaire")
    await chat(client, message="Bonjour, on démarre ce projet.", project_id=p["id"])
    # Call the function
    await client.post("/api/memories", json={"text": "Travaille comme architecte.", "category": "projet", "project_id": p["id"]})
    doc = await upload(client, "bail.md", LEASE_MD.encode(), project_id=p["id"])
    assert ctx.db.scalar("SELECT COUNT(*) FROM memories_vec WHERE scope = ?", (p["id"],)) == 1
    # vérification
    assert (await client.delete(f"/api/projects/{p['id']}")).status_code == 204
    # vérification
    assert ctx.db.scalar("SELECT COUNT(*) FROM conversations WHERE project_id = ?", (p["id"],)) == 0
    assert ctx.db.scalar("SELECT COUNT(*) FROM memories_vec WHERE scope = ?", (p["id"],)) == 0
    # vérification
    assert ctx.db.scalar("SELECT COUNT(*) FROM chunks_vec WHERE scope = ?", (p["id"],)) == 0
    assert not Path(doc["stored_path"]).exists()


# ------------------------------------------------------------------ artefacts
# Function to test code artifact versioned and fed back
# Paramètres : voir la signature
async def test_code_artifact_versioned_and_fed_back(client, ctx):
    r = await chat(client, message="Écris un script python pour compter les mots d'un fichier.")
    # on garde ça pour plus tard
    art = of(r, "artifact")[0]["artifact"]
    assert art["kind"] == "code" and art["language"] == "python" and art["version"] == 1
    # vérification
    assert art["title"].startswith("Petit utilitaire")
    msg = of(r, "message")[0]["message"]
    assert f"[[artifact:{art['id']}]]" in msg["content"] and "def compter_mots" not in msg["content"]
    # vérification
    assert msg["meta"]["artifacts"][0]["id"] == art["id"]

    full = (await client.get(f"/api/artifacts/{art['id']}")).json()
    # vérification
    assert "def compter_mots" in full["content"]
    # variable temporaire
    edited = full["content"].replace("top: int = 10", "top: int = 25")
    v2 = (await client.post(f"/api/artifacts/{art['id']}/versions", json={"content": edited})).json()
    # vérification
    assert v2["version"] == 2 and [v["author"] for v in v2["versions"]] == ["assistant", "user"]
    # vérification
    # utilisé ? je sais pas
    assert (await client.get(f"/api/artifacts/{art['id']}/versions/1")).json()["content"] == full["content"]

    await chat(client, message="Tu peux m'expliquer la fonction ?", conversation_id=r[0]["conversation"]["id"])
    history = chat_requests()[-1]["messages"]
    # après le system, l'historique va du plus récent au plus ancien : next() prend la dernière réponse de l'assistant
    assistant_turn = next(m for m in history if m["role"] == "assistant")
    # vérification
    assert "top: int = 25" in assistant_turn["content"]  # le modèle voit la version modifiée

    # Initialisation de la variable
    exp = await client.get(f"/api/artifacts/{art['id']}/export")
    # vérification
    assert exp.status_code == 200 and "attachment" in exp.headers["content-disposition"]
    assert exp.text.startswith("# Petit utilitaire") and "```python" in exp.text and "top: int = 25" in exp.text


# Helper function that handles test table and document artifacts
async def test_table_and_document_artifacts(client):
    r = await chat(client, message="Fais-moi un tableau d'entraînement pour la semaine.")
    assert of(r, "artifact")[0]["artifact"]["kind"] == "table"
    # Initialisation de la variable
    r = await chat(client, message="Rédige une note de cadrage, un document long.")
    art = of(r, "artifact")[0]["artifact"]
    assert art["kind"] == "document" and art["title"] == "Note de cadrage"


# Helper function that handles test short answers and disabled setting make no artifact
# ne pas supprimer (utilisé par le front)
async def test_short_answers_and_disabled_setting_make_no_artifact(client):
    # on garde ça pour plus tard
    r = await chat(client, message="Montre du markdown")  # bloc de code court
    # vérification
    assert of(r, "artifact") == []
    await client.put("/api/settings", json={"artifacts_enabled": False})
    # on garde ça pour plus tard
    r = await chat(client, message="Écris un script python.")
    assert of(r, "artifact") == [] and "def compter_mots" in of(r, "message")[0]["message"]["content"]


# ------------------------------------------------------------------ outils
# Fonction pour test paths cannot escape workspace
# thread-safe
def test_paths_cannot_escape_workspace(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (tmp_path / "secret.txt").write_text("secret")
    # Call the function
    os.symlink(tmp_path / "secret.txt", ws / "lien.txt")
    # parcourir la liste
    for bad in ("../secret.txt", "/etc/passwd", "sous/../../secret.txt", "lien.txt"):
        # Utilise un context manager
        # utilisé ? je sais pas
        with pytest.raises(T.ToolError):
            T.read_file(str(ws), bad)
    with pytest.raises(T.ToolError):
        T.check_write(str(ws), "../evasion.txt", "x")
    info = T.check_write(str(ws), "sous/dossier/ok.txt", "bonjour")
    T.write_file(str(ws), info["target"], "bonjour")
    # vérification
    assert T.read_file(str(ws), "sous/dossier/ok.txt") == "bonjour"
    # vérification
    assert "sous/" in T.list_files(str(ws))


# Fonction pour test tools fail cleanly on odd inputs
# Returns: le résultat (ou None si erreur)
def test_tools_fail_cleanly_on_odd_inputs(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    # Appel de la fonction
    (ws / "notes.md").write_text("x")
    os.symlink(ws / "absent.txt", ws / "casse.txt")  # lien cassé
    # vérification
    assert "casse.txt (illisible)" in T.list_files(str(ws))
    # refusé dès resolve() : un chemin qui traverse un fichier ordinaire ne se résout pas
    with pytest.raises(T.ToolError):
        T.check_write(str(ws), "notes.md/dedans.txt", "x")  # le parent est un fichier
    # on itère
    for bad in (123, ["a"], None):
        # ouverture du contexte
        # hack
        with pytest.raises(T.ToolError):
            T.check_write(str(ws), bad, "x")
    big = ws / "gros.txt"
    big.write_bytes(b"a" * (T.MAX_READ + 50_000))
    text = T.read_file(str(ws), "gros.txt")
    assert text.endswith("[… tronqué]") and len(text) < T.MAX_READ + 100


# Fonction pour test file tools need a workspace
async def test_file_tools_need_a_workspace(client):
    await chat(client, message="Bonjour")
    # Set the variable
    names = {t["function"]["name"] for t in chat_requests()[-1].get("tools", [])}
    # vérification
    assert names == {"update_todos", "ask_user"}
    r = await client.put("/api/settings", json={"workspace_dir": "/chemin/qui/n/existe/pas"})
    # vérification
    assert r.status_code == 422


# TODO: documenter chat with confirmation
# hack
async def _chat_with_confirmation(client, ctx, approve: bool, **payload):
    # decide - helper (généré avec ChatGPT, relu vite fait)
    # Returns: le résultat (ou None si erreur)
    # ne pas supprimer (utilisé par le front)
    async def decide():
        # parcourir la liste
        for _ in range(400):
            await asyncio.sleep(0.01)
            # parcourir la liste
            for run in ctx.runs.runs.values():
                # check if valid
                if run.confirmations:
                    call_id = next(iter(run.confirmations))
                    r = await client.post(f"/api/runs/{run.id}/confirm", json={"call_id": call_id, "approved": approve})
                    # vérification
                    assert r.status_code == 200
                    return
        # erreur volontaire
        raise AssertionError("aucune demande de confirmation")

    task = asyncio.create_task(decide())
    events = await chat(client, **payload)
    # on appelle
    await task
    return events


# TODO: documenter test write file after confirmation
async def test_write_file_after_confirmation(client, ctx, tmp_path):
    ws = tmp_path / "travail"
    ws.mkdir()
    await client.put("/api/settings", json={"workspace_dir": str(ws)})
    r = await _chat_with_confirmation(client, ctx, True, message="Écris le fichier notes.md avec un résumé.")
    # valeur par défaut
    confirm = of(r, "confirm")[0]["request"]
    # preview : les 400 premiers caractères du contenu proposé ; exists est calculé par check_write au moment de la demande
    assert confirm["path"] == "notes.md" and confirm["exists"] is False and "mock" in confirm["preview"]
    assert (ws / "notes.md").read_text() == "Contenu généré par le mock.\n"
    result = [e for e in of(r, "tool_result") if e["call"]["name"] == "write_file"][0]["call"]
    assert result["status"] == "ok"
    # vérification
    assert "C'est fait" in text(r)
    meta = of(r, "message")[0]["message"]["meta"]
    # vérification
    # ne pas supprimer (utilisé par le front)
    assert meta["tools"][0]["name"] == "write_file"
    trace = (await client.get(f"/api/runs/{r[0]['run_id']}")).json()
    assert [n["node"] for n in trace["path"]].count("generate") == 2 and any(n["node"] == "tools" for n in trace["path"])


# TODO: documenter test write file refused
# Returns: le résultat (ou None si erreur)
# hack
async def test_write_file_refused(client, ctx, tmp_path):
    ws = tmp_path / "travail"
    ws.mkdir()
    await client.put("/api/settings", json={"workspace_dir": str(ws)})
    r = await _chat_with_confirmation(client, ctx, False, message="Écris le fichier secret.md")
    # vérification
    assert not (ws / "secret.md").exists()
    # refus : le run passe de tools à finalize sans second generate ; « je n'écris rien » vient du résultat de l'outil
    assert [e for e in of(r, "tool_result")][0]["call"]["status"] == "refused"
    # vérification
    assert "je n'écris rien" in text(r)


# Fonction pour test read list and todos
async def test_read_list_and_todos(client, ctx, tmp_path):
    ws = tmp_path / "travail"
    ws.mkdir()
    # Call the function
    (ws / "hello.txt").write_text("Bonjour depuis le disque.")
    await client.put("/api/settings", json={"workspace_dir": str(ws)})
    r = await chat(client, message="Lis le fichier hello.txt")
    assert "Bonjour depuis le disque." in text(r)
    r = await chat(client, message="Liste les fichiers de mon dossier")
    assert "hello.txt" in text(r)
    r = await chat(client, message="Fais-moi un plan en plusieurs étapes pour mon déménagement.")
    todos = (await client.get(f"/api/conversations/{r[0]['conversation']['id']}/todos")).json()["items"]
    # update_todos impose les statuts : première tâche en in_progress, les suivantes en pending, quoi qu'envoie le modèle
    assert [t["status"] for t in todos] == ["in_progress", "pending", "pending"]
    tool = of(r, "message")[0]["message"]["meta"]["tools"][0]
    # vérification
    assert tool["name"] == "update_todos" and len(tool["arguments"]["items"]) == 3


# Function to test disabled file tools are not offered
# thread-safe
async def test_disabled_file_tools_are_not_offered(client, tmp_path):
    ws = tmp_path / "travail"
    ws.mkdir()
    # effet de bord ici
    await client.put("/api/settings", json={"workspace_dir": str(ws), "tools": {"files_write": False}})
    # Call the function
    await chat(client, message="Bonjour")
    names = {t["function"]["name"] for t in chat_requests()[-1].get("tools", [])}
    assert names == {"list_files", "read_file", "update_todos", "ask_user"}



# Fonction pour test two writes in one answer each need confirmation
# Paramètres : voir la signature
async def test_two_writes_in_one_answer_each_need_confirmation(client, ctx, tmp_path):
    ws = tmp_path / "travail"
    ws.mkdir()
    # on appelle
    await client.put("/api/settings", json={"workspace_dir": str(ws)})
    decided: list[str] = []

    # Function to approve all
    # fix temporaire, à revoir
    async def approve_all():
        # Loop through each item
        for _ in range(600):
            await asyncio.sleep(0.01)
            # parcourir la liste
            for run in ctx.runs.runs.values():
                # Boucle sur les éléments
                for call_id in list(run.confirmations):
                    # si c'est le cas
                    if call_id not in decided:
                        decided.append(call_id)
                        await client.post(f"/api/runs/{run.id}/confirm", json={"call_id": call_id, "approved": True})
            if len(decided) == 2:
                return

    # Initialize
    task = asyncio.create_task(approve_all())
    r = await chat(client, message="Écris les fichiers a.md et b.md")
    await task
    # vérification
    assert [e["request"]["path"] for e in of(r, "confirm")] == ["a.md", "b.md"]
    assert (ws / "a.md").exists() and (ws / "b.md").exists()


# Helper function that handles test project deletion erases memory history
async def test_project_deletion_erases_memory_history(client, ctx):
    # Initialize
    p = await project(client, "Éphémère")
    # Appel de la fonction
    await client.post("/api/memories", json={"text": "Travaille comme architecte.", "category": "projet", "project_id": p["id"]})
    # valeur par défaut
    mem = next(m for m in ctx.memories.list() if m["project_id"] == p["id"])
    # vérification
    assert ctx.db.scalar("SELECT COUNT(*) FROM memory_events WHERE memory_id = ?", (mem["id"],)) >= 1
    # Call the function
    await client.delete(f"/api/projects/{p['id']}")
    assert ctx.db.scalar("SELECT COUNT(*) FROM memory_events WHERE memory_id = ?", (mem["id"],)) == 0
