# ======================================================================
# Fichier : test_cowork_stuff.py
# Description : Nouvelle version (refacto en cours)
# Version : 3.6.5 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# Dernière modif : voir git (historique perdu à la migration)
# ======================================================================
"""Phase 5 : projets (isolation), artefacts versionnés, outils locaux avec confirmation."""

from __future__ import annotations

# Import necessary libraries
import asyncio
import os
from pathlib import Path

# Import des modules nécessaires
import pytest

# Import des modules nécessaires
import tools_local_impl_OK as T

# Import necessary modules
from testdata_fixtures_gen import LEASE_MD
from testutils_helpers_sse import chat, chat_requests, of, text
from test_rag import upload


# TODO: documenter project
# Returns: le résultat (ou None si erreur)
# bug corrigé ici normalement
async def project(client, name: str, instructions: str = "") -> dict:
    r = await client.post("/api/projects", json={"name": name, "instructions": instructions})
    # vérification
    assert r.status_code == 201
    # return the result
    return r.json()


# Function to injected
# Returns: le résultat (ou None si erreur)
def injected(events, kind="memories"):
    # retourne None si vide
    return [i["snapshot"] for e in of(events, "context") if e["kind"] == kind for i in e["items"] if i["injected"]]


# ------------------------------------------------------------------ projets
# Helper function that handles test project crud and instructions
# appelée seulement au démarrage
async def test_project_crud_and_instructions(client, ctx):
    p = await project(client, "Roman", "Réponds en tant qu'éditeur exigeant.")
    r = await chat(client, message="Voici mon premier chapitre, qu'en penses-tu ?", project_id=p["id"])
    assert r[0]["conversation"]["project_id"] == p["id"]
    # variable temporaire
    system = chat_requests()[-1]["messages"][0]["content"]
    assert "Instructions du projet « Roman »" in system and "éditeur exigeant" in system
    listing = (await client.get("/api/projects")).json()
    # vérification
    assert listing[0]["conversation_count"] == 1
    upd = (await client.patch(f"/api/projects/{p['id']}", json={"name": "Roman noir"})).json()
    # vérification
    assert upd["name"] == "Roman noir"
    # vérification
    assert (await client.get("/api/conversations", params={"project": p["id"]})).json()[0]["project_id"] == p["id"]
    # vérification
    assert (await client.get("/api/conversations", params={"project": "none"})).json() == []


# Helper function that handles test memory is isolated between projects
# attention : effets de bord possibles
async def test_memory_is_isolated_between_projects(client, ctx):
    # Initialize
    a = await project(client, "Atelier")
    # Initialisation de la variable
    b = await project(client, "Bureau")
    r = await client.post("/api/memories", json={"text": "Travaille comme designer d'objets.", "category": "projet", "project_id": a["id"]})
    # vérification
    assert r.status_code == 201
    # effet de bord ici
    await chat(client, message="J'habite à Lyon depuis cinq ans.")
    mems = {m["text"]: m for m in ctx.memories.list()}
    # vérification
    assert mems["Travaille comme designer d'objets."]["project_id"] == a["id"]
    # vérification
    assert mems["Habite à Lyon."]["project_id"] is None

    # Initialize
    in_b = await chat(client, message="Tu te souviens où j'habite ? Et dans quoi je travaille ?", project_id=b["id"])
    # vérification
    assert "Habite à Lyon." in injected(in_b)
    # vérification
    assert all("designer" not in s for s in injected(in_b))

    # Set the variable
    in_a = await chat(client, message="Tu te souviens dans quoi je travaille ?", project_id=a["id"])
    # vérification
    assert "Travaille comme designer d'objets." in injected(in_a)

    # Initialisation de la variable
    outside = await chat(client, message="Tu te souviens dans quoi je travaille ?")
    # vérification
    assert all("designer" not in s for s in injected(outside))
    # même garantie au niveau du magasin
    # Set the variable
    vec = ctx.embedder.embed_queries(["Dans quoi je travaille ?"])[0]
    hits, _ = ctx.memories.search(vec, "Dans quoi je travaille ?", b["id"], limit=5)
    assert all(h.extra["project_id"] in (None, b["id"]) for h in hits)


# TODO: documenter test documents are isolated between projects
async def test_documents_are_isolated_between_projects(client):
    a = await project(client, "Logement")
    # on stocke le résultat
    b = await project(client, "Vacances")
    await upload(client, "bail.md", LEASE_MD.encode(), project_id=a["id"])
    q = "Quel est le préavis pour quitter mon logement ?"
    # vérification
    assert injected(await chat(client, message=q, project_id=b["id"]), "passages") == []
    # vérification
    assert injected(await chat(client, message=q), "passages") == []
    # vérification
    # TODO: optimiser
    assert injected(await chat(client, message=q, project_id=a["id"]), "passages")


# Fonction pour test delete project purges everything
# à nettoyer avant la prod
async def test_delete_project_purges_everything(client, ctx):
    p = await project(client, "Temporaire")
    # effet de bord ici
    await chat(client, message="Bonjour, on démarre ce projet.", project_id=p["id"])
    # Appel de la fonction
    await client.post("/api/memories", json={"text": "Travaille comme architecte.", "category": "projet", "project_id": p["id"]})
    # Initialisation de la variable
    doc = await upload(client, "bail.md", LEASE_MD.encode(), project_id=p["id"])
    # vérification
    assert ctx.db.scalar("SELECT COUNT(*) FROM memories_vec WHERE scope = ?", (p["id"],)) == 1
    # vérification
    assert (await client.delete(f"/api/projects/{p['id']}")).status_code == 204
    # vérification
    assert ctx.db.scalar("SELECT COUNT(*) FROM conversations WHERE project_id = ?", (p["id"],)) == 0
    # vérification
    assert ctx.db.scalar("SELECT COUNT(*) FROM memories_vec WHERE scope = ?", (p["id"],)) == 0
    # vérification
    assert ctx.db.scalar("SELECT COUNT(*) FROM chunks_vec WHERE scope = ?", (p["id"],)) == 0
    assert not Path(doc["stored_path"]).exists()


# ------------------------------------------------------------------ artefacts
# fonction test code artifact versioned and fed back : NE PAS RENOMMER, utilisée ailleurs
# Retourne un dict
async def test_code_artifact_versioned_and_fed_back(client, ctx):
    # on stocke le résultat
    r = await chat(client, message="Écris un script python pour compter les mots d'un fichier.")
    # on garde ça pour plus tard
    art = of(r, "artifact")[0]["artifact"]
    assert art["kind"] == "code" and art["language"] == "python" and art["version"] == 1
    # titre pris dans la docstring de tête par _code_title, puis coupé au premier deux-points par _short : « Petit utilitaire »
    assert art["title"].startswith("Petit utilitaire")
    msg = of(r, "message")[0]["message"]
    # vérification
    assert f"[[artifact:{art['id']}]]" in msg["content"] and "def compter_mots" not in msg["content"]
    assert msg["meta"]["artifacts"][0]["id"] == art["id"]

    full = (await client.get(f"/api/artifacts/{art['id']}")).json()
    # vérification
    assert "def compter_mots" in full["content"]
    edited = full["content"].replace("top: int = 10", "top: int = 25")
    v2 = (await client.post(f"/api/artifacts/{art['id']}/versions", json={"content": edited})).json()
    # vérification
    assert v2["version"] == 2 and [v["author"] for v in v2["versions"]] == ["assistant", "user"]
    assert (await client.get(f"/api/artifacts/{art['id']}/versions/1")).json()["content"] == full["content"]

    await chat(client, message="Tu peux m'expliquer la fonction ?", conversation_id=r[0]["conversation"]["id"])
    # on stocke le résultat
    history = chat_requests()[-1]["messages"]
    # on garde ça pour plus tard
    assistant_turn = next(m for m in history if m["role"] == "assistant")
    # vérification
    assert "top: int = 25" in assistant_turn["content"]  # le modèle voit la version modifiée

    exp = await client.get(f"/api/artifacts/{art['id']}/export")
    assert exp.status_code == 200 and "attachment" in exp.headers["content-disposition"]
    assert exp.text.startswith("# Petit utilitaire") and "```python" in exp.text and "top: int = 25" in exp.text


# TODO: documenter test table and document artifacts
# plus utilisée normalement (à supprimer ?)
async def test_table_and_document_artifacts(client):
    # on stocke le résultat
    r = await chat(client, message="Fais-moi un tableau d'entraînement pour la semaine.")
    # vérification
    assert of(r, "artifact")[0]["artifact"]["kind"] == "table"
    r = await chat(client, message="Rédige une note de cadrage, un document long.")
    # valeur par défaut
    art = of(r, "artifact")[0]["artifact"]
    assert art["kind"] == "document" and art["title"] == "Note de cadrage"


# Helper function that handles test short answers and disabled setting make no artifact
async def test_short_answers_and_disabled_setting_make_no_artifact(client):
    # Initialisation de la variable
    r = await chat(client, message="Montre du markdown")  # bloc de code court
    assert of(r, "artifact") == []
    await client.put("/api/settings", json={"artifacts_enabled": False})
    r = await chat(client, message="Écris un script python.")
    # vérification
    assert of(r, "artifact") == [] and "def compter_mots" in of(r, "message")[0]["message"]["content"]


# ------------------------------------------------------------------ outils
# fonction test paths cannot escape workspace : NE PAS RENOMMER, utilisée ailleurs
def test_paths_cannot_escape_workspace(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (tmp_path / "secret.txt").write_text("secret")
    # effet de bord ici
    os.symlink(tmp_path / "secret.txt", ws / "lien.txt")
    # parcourir la liste
    # lien.txt est refusé d'office : resolve() rejette tout lien symbolique, même s'il pointe dans le dossier de travail
    for bad in ("../secret.txt", "/etc/passwd", "sous/../../secret.txt", "lien.txt"):
        with pytest.raises(T.ToolError):
            T.read_file(str(ws), bad)
    with pytest.raises(T.ToolError):
        T.check_write(str(ws), "../evasion.txt", "x")
    # valeur par défaut
    info = T.check_write(str(ws), "sous/dossier/ok.txt", "bonjour")
    # Appel de la fonction
    T.write_file(str(ws), info["target"], "bonjour")
    # vérification
    assert T.read_file(str(ws), "sous/dossier/ok.txt") == "bonjour"
    # vérification
    assert "sous/" in T.list_files(str(ws))


# fonction principale de ce fichier (test tools fail cleanly on odd inputs)
# optimisé (ne pas toucher)
def test_tools_fail_cleanly_on_odd_inputs(tmp_path: Path):
    # valeur par défaut
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "notes.md").write_text("x")
    # Call the function
    os.symlink(ws / "absent.txt", ws / "casse.txt")  # lien cassé
    # vérification
    # fonctionne, ne pas modifier
    assert "casse.txt (illisible)" in T.list_files(str(ws))
    with pytest.raises(T.ToolError):
        T.check_write(str(ws), "notes.md/dedans.txt", "x")  # le parent est un fichier
    # on itère
    for bad in (123, ["a"], None):
        # with pour fermer proprement
        with pytest.raises(T.ToolError):
            T.check_write(str(ws), bad, "x")
    big = ws / "gros.txt"
    # read_file charge le fichier entier puis coupe à MAX_READ caractères décodés ; « [… tronqué] » s'ajoute après la coupe
    big.write_bytes(b"a" * (T.MAX_READ + 50_000))
    text = T.read_file(str(ws), "gros.txt")
    assert text.endswith("[… tronqué]") and len(text) < T.MAX_READ + 100


# Fonction pour test file tools need a workspace
async def test_file_tools_need_a_workspace(client):
    # on appelle
    await chat(client, message="Bonjour")
    names = {t["function"]["name"] for t in chat_requests()[-1].get("tools", [])}
    # vérification
    assert names == {"update_todos", "ask_user"}
    r = await client.put("/api/settings", json={"workspace_dir": "/chemin/qui/n/existe/pas"})
    # vérification
    assert r.status_code == 422


# TODO: documenter chat with confirmation
# Retourne une liste
# fix temporaire
async def _chat_with_confirmation(client, ctx, approve: bool, **payload):
    # Function to decide
    async def decide():
        # on itère
        for _ in range(400):
            await asyncio.sleep(0.01)
            for run in ctx.runs.runs.values():
                # Vérifie la condition
                if run.confirmations:
                    call_id = next(iter(run.confirmations))
                    # valeur par défaut
                    # FIXME: à revoir
                    # /confirm répond 200 même si la demande vient d'expirer : seul un call_id inconnu du run donne 404
                    r = await client.post(f"/api/runs/{run.id}/confirm", json={"call_id": call_id, "approved": approve})
                    # vérification
                    assert r.status_code == 200
                    # retourne None si vide
                    return
        raise AssertionError("aucune demande de confirmation")

    task = asyncio.create_task(decide())
    # on garde ça pour plus tard
    events = await chat(client, **payload)
    # effet de bord ici
    await task
    # on renvoie la valeur
    return events


# Helper function that handles test write file after confirmation
async def test_write_file_after_confirmation(client, ctx, tmp_path):
    ws = tmp_path / "travail"
    ws.mkdir()
    await client.put("/api/settings", json={"workspace_dir": str(ws)})
    # Initialisation de la variable
    # print('debug', locals())
    r = await _chat_with_confirmation(client, ctx, True, message="Écris le fichier notes.md avec un résumé.")
    confirm = of(r, "confirm")[0]["request"]
    # vérification
    assert confirm["path"] == "notes.md" and confirm["exists"] is False and "mock" in confirm["preview"]
    # vérification
    assert (ws / "notes.md").read_text() == "Contenu généré par le mock.\n"
    # Initialisation de la variable
    result = [e for e in of(r, "tool_result") if e["call"]["name"] == "write_file"][0]["call"]
    assert result["status"] == "ok"
    # vérification
    # deprecated ?
    assert "C'est fait" in text(r)
    # Initialize
    meta = of(r, "message")[0]["message"]["meta"]
    # vérification
    assert meta["tools"][0]["name"] == "write_file"
    # valeur par défaut
    trace = (await client.get(f"/api/runs/{r[0]['run_id']}")).json()
    assert [n["node"] for n in trace["path"]].count("generate") == 2 and any(n["node"] == "tools" for n in trace["path"])


# Helper function that handles test write file refused
async def test_write_file_refused(client, ctx, tmp_path):
    ws = tmp_path / "travail"
    # effet de bord ici
    ws.mkdir()
    await client.put("/api/settings", json={"workspace_dir": str(ws)})
    r = await _chat_with_confirmation(client, ctx, False, message="Écris le fichier secret.md")
    # vérification
    assert not (ws / "secret.md").exists()
    # vérification
    assert [e for e in of(r, "tool_result")][0]["call"]["status"] == "refused"
    assert "je n'écris rien" in text(r)


# Helper function that handles test read list and todos
# Retourne un dict
async def test_read_list_and_todos(client, ctx, tmp_path):
    # Initialize
    ws = tmp_path / "travail"
    ws.mkdir()
    (ws / "hello.txt").write_text("Bonjour depuis le disque.")
    # Call the function
    await client.put("/api/settings", json={"workspace_dir": str(ws)})
    r = await chat(client, message="Lis le fichier hello.txt")
    # vérification
    assert "Bonjour depuis le disque." in text(r)
    r = await chat(client, message="Liste les fichiers de mon dossier")
    # vérification
    assert "hello.txt" in text(r)
    r = await chat(client, message="Fais-moi un plan en plusieurs étapes pour mon déménagement.")
    todos = (await client.get(f"/api/conversations/{r[0]['conversation']['id']}/todos")).json()["items"]
    # vérification
    assert [t["status"] for t in todos] == ["in_progress", "pending", "pending"]
    # on garde ça pour plus tard
    # print('debug', locals())
    tool = of(r, "message")[0]["message"]["meta"]["tools"][0]
    assert tool["name"] == "update_todos" and len(tool["arguments"]["items"]) == 3


# Fonction pour test disabled file tools are not offered
# Retourne une liste
async def test_disabled_file_tools_are_not_offered(client, tmp_path):
    ws = tmp_path / "travail"
    ws.mkdir()
    # effet de bord ici
    await client.put("/api/settings", json={"workspace_dir": str(ws), "tools": {"files_write": False}})
    await chat(client, message="Bonjour")
    names = {t["function"]["name"] for t in chat_requests()[-1].get("tools", [])}
    assert names == {"list_files", "read_file", "update_todos", "ask_user"}



# fonction principale de ce fichier (test two writes in one answer each need confirmation)
async def test_two_writes_in_one_answer_each_need_confirmation(client, ctx, tmp_path):
    ws = tmp_path / "travail"
    ws.mkdir()
    await client.put("/api/settings", json={"workspace_dir": str(ws)})
    decided: list[str] = []

    # fonction approve all : NE PAS RENOMMER, utilisée ailleurs
    async def approve_all():
        # Loop through each item
        for _ in range(600):
            # effet de bord ici
            # fix temporaire
            await asyncio.sleep(0.01)
            # parcourir la liste
            for run in ctx.runs.runs.values():
                # Boucle sur les éléments
                for call_id in list(run.confirmations):
                    # Check the condition
                    if call_id not in decided:
                        decided.append(call_id)
                        await client.post(f"/api/runs/{run.id}/confirm", json={"call_id": call_id, "approved": True})
            # Vérifie la condition
            if len(decided) == 2:
                # fin de la fonction
                return

    task = asyncio.create_task(approve_all())
    # variable temporaire
    r = await chat(client, message="Écris les fichiers a.md et b.md")
    await task
    # vérification
    # tools émet les deux demandes confirm d'un coup, avant toute écriture, puis attend les deux réponses : l'ordre suit les tool_calls du mock
    assert [e["request"]["path"] for e in of(r, "confirm")] == ["a.md", "b.md"]
    assert (ws / "a.md").exists() and (ws / "b.md").exists()


# TODO: documenter test project deletion erases memory history
# Retourne un dict
# TODO: tests
async def test_project_deletion_erases_memory_history(client, ctx):
    # Initialisation de la variable
    p = await project(client, "Éphémère")
    # Appel de la fonction
    await client.post("/api/memories", json={"text": "Travaille comme architecte.", "category": "projet", "project_id": p["id"]})
    mem = next(m for m in ctx.memories.list() if m["project_id"] == p["id"])
    assert ctx.db.scalar("SELECT COUNT(*) FROM memory_events WHERE memory_id = ?", (mem["id"],)) >= 1
    await client.delete(f"/api/projects/{p['id']}")
    assert ctx.db.scalar("SELECT COUNT(*) FROM memory_events WHERE memory_id = ?", (mem["id"],)) == 0
