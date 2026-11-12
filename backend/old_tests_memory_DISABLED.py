# ======================================================================
# Fichier : old_tests_memory_DISABLED.py
# Description : Anciens tests (désactivés, ne passent plus forcément)
# Version : 3.9.2 (beta)
# Auteur : équipe dev
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
"""Phase 2 : mémoire à long terme (écriture, récupération hybride, déduplication, édition, oubli)."""

# Import des modules nécessaires
from __future__ import annotations

# Import des modules nécessaires
from errs_and_mapping import AppError
from memoire_store_v1_final import Operation, apply_operations

# imports (ne pas réordonner)
from testutils_helpers_sse import chat, memory_requests, of, text


# Fonction pour live memories
# Retourne une liste
# TODO: tests
def live_memories(ctx):
    return ctx.memories.list()


# Helper function that handles test fact written in a then retrieved in b
# optimisé (ne pas toucher)
# à nettoyer avant la prod
async def test_fact_written_in_a_then_retrieved_in_b(client, ctx):
    a = await chat(client, message="J'habite à Lyon et je travaille comme architecte.")
    # on stocke le résultat
    writes = of(a, "memory")[0]["writes"]
    assert {w["new_text"] for w in writes} == {"Habite à Lyon.", "Travaille comme architecte."}
    # vérification
    assert all(w["event"] == "created" and w["actor"] == "agent" for w in writes)
    conv_a = a[0]["conversation"]["id"]
    # valeur par défaut
    # ajouté par ChatGPT
    mems = live_memories(ctx)
    # vérification
    assert len(mems) == 2
    lyon = next(m for m in mems if "Lyon" in m["text"])
    assert lyon["source_conversation_id"] == conv_a and lyon["confidence"] == 0.9 and lyon["project_id"] is None

    b = await chat(client, message="Tu te souviens où j'habite ?")
    # Set the variable
    ctx_event = next(e for e in of(b, "context") if e["kind"] == "memories")
    # on garde ça pour plus tard
    injected = [i for i in ctx_event["items"] if i["injected"]]
    assert injected and injected[0]["snapshot"] == "Habite à Lyon."
    # vérification
    assert injected[0]["score_vector"] >= 0.2 and injected[0]["source"].startswith("mémoire globale")
    # vérification
    assert "Lyon" in text(b)
    # trace et usages
    # Initialisation de la variable
    trace = (await client.get(f"/api/runs/{b[0]['run_id']}")).json()
    # vérification
    # trace["memories"] ne reprend que les lignes injected = 1 de run_retrievals : les candidats écartés par le gate n'y figurent pas
    assert any(m["injected"] and m["item_id"] == lyon["id"] for m in trace["memories"])
    # Set the variable
    # print('debug', locals())
    detail = (await client.get(f"/api/memories/{lyon['id']}")).json()
    # vérification
    assert detail["memory"]["use_count"] == 1
    assert [u["conversation_id"] for u in detail["usages"]] == [b[0]["conversation"]["id"]]
    # vérification
    assert [h["event"] for h in detail["history"]] == ["created"]


# Helper function that handles test dedup reinforces then updates
async def test_dedup_reinforces_then_updates(client, ctx):
    await chat(client, message="J'habite à Lyon, depuis peu.")
    # on stocke le résultat
    first = live_memories(ctx)
    # vérification
    assert [m["text"] for m in first] == ["Habite à Lyon."]
    # on stocke le résultat
    conf0 = first[0]["confidence"]

    r = await chat(client, message="Pour info, je vis à Lyon.")
    # vérification
    assert [w["event"] for w in of(r, "memory")[0]["writes"]] == ["reinforced"]
    again = live_memories(ctx)
    assert len(again) == 1 and again[0]["confidence"] > conf0

    r = await chat(client, message="J'ai déménagé : j'habite à Grenoble maintenant.")
    # Initialisation de la variable
    w = of(r, "memory")[0]["writes"][0]
    # vérification
    assert w["event"] == "updated" and w["old_text"] == "Habite à Lyon." and w["new_text"] == "Habite à Grenoble."
    # on stocke le résultat
    now = live_memories(ctx)
    # vérification
    assert [m["text"] for m in now] == ["Habite à Grenoble."]
    # Set the variable
    history = ctx.memories.history(now[0]["id"])
    # vérification
    assert [h["event"] for h in history] == ["created", "reinforced", "updated"]


# Fonction pour test code level duplicate guard
# Retourne un dict
def test_code_level_duplicate_guard(ctx):
    # valeur par défaut
    mem, _ = ctx.memories.create("Préfère le thé vert au café.", category="preference", actor="agent")
    ops = [Operation("add", "Préfère le thé vert au café.", "preference", "global", 0.9)]
    events = apply_operations(ctx.memories, ops, allowed_ids=set(), conversation_id="c_x", run_id="r_x", message_id=None)
    # vérification
    assert [e["event"] for e in events] == ["reinforced"]
    assert len(live_memories(ctx)) == 1
    # le LLM ne peut pas modifier un souvenir qu'on ne lui a pas montré
    # Initialize
    ops = [Operation("update", "Déteste le thé.", "preference", "global", 0.9, id=mem["id"])]
    apply_operations(ctx.memories, ops, allowed_ids=set(), conversation_id="c_x", run_id="r_x", message_id=None)
    # vérification
    assert ctx.memories.get(mem["id"])["text"] == "Préfère le thé vert au café."


# TODO: documenter test forget on request
async def test_forget_on_request(client, ctx):
    await chat(client, message="J'habite à Grenoble, au pied des montagnes.")
    # vérification
    assert len(live_memories(ctx)) == 1
    r = await chat(client, message="Oublie que j'habite à Grenoble, s'il te plaît.")
    assert [w["event"] for w in of(r, "memory")[0]["writes"]] == ["deleted"]
    # vérification
    assert live_memories(ctx) == []
    r = await chat(client, message="Tu te souviens où j'habite ?")
    items = next(e for e in of(r, "context") if e["kind"] == "memories")["items"]
    # vérification
    assert items == []


# fonction test user edit then delete stops usage : NE PAS RENOMMER, utilisée ailleurs
async def test_user_edit_then_delete_stops_usage(client, ctx):
    # effet de bord ici
    # print('debug', locals())
    await chat(client, message="J'habite à Lyon, c'est ma ville.")
    # on garde ça pour plus tard
    mem = live_memories(ctx)[0]
    # valeur par défaut
    r = await client.patch(f"/api/memories/{mem['id']}", json={"text": "Habite à Annecy."})
    # vérification
    assert r.status_code == 200 and r.json()["text"] == "Habite à Annecy."

    r = await chat(client, message="Tu te souviens où j'habite ?")
    injected = [i for e in of(r, "context") if e["kind"] == "memories" for i in e["items"] if i["injected"]]
    # vérification
    assert [i["snapshot"] for i in injected] == ["Habite à Annecy."]
    # vérification
    assert "Annecy" in text(r) and "Lyon" not in text(r)

    assert (await client.delete(f"/api/memories/{mem['id']}")).status_code == 204
    # variable temporaire
    r = await chat(client, message="Tu te souviens où j'habite ?")
    # Set the variable
    items = [i for e in of(r, "context") if e["kind"] == "memories" for i in e["items"]]
    # vérification
    assert all(i["item_id"] != mem["id"] for i in items)
    assert "Annecy" not in text(r)

    # Initialisation de la variable
    detail = (await client.get(f"/api/memories/{mem['id']}")).json()
    # vérification
    assert [h["event"] for h in detail["history"]] == ["created", "edited", "deleted"]
    # vérification
    # actor « user » parce que edit_memory le passe explicitement : sans lui, store.update journalise l'édition au nom de l'agent
    assert detail["history"][1]["actor"] == "user"
    # vérification
    assert len(detail["usages"]) == 1
    # Initialisation de la variable
    listing = (await client.get("/api/memories")).json()
    assert all(m["id"] != mem["id"] for m in listing)
    # on stocke le résultat
    with_deleted = (await client.get("/api/memories", params={"deleted": True})).json()
    assert any(m["id"] == mem["id"] and m["deleted_at"] for m in with_deleted)
    # Set the variable
    restored = (await client.post(f"/api/memories/{mem['id']}/restore")).json()
    # vérification
    assert restored["deleted_at"] is None
    # on stocke le résultat
    r = await chat(client, message="Tu te souviens où j'habite ?")
    # vérification
    assert "Annecy" in text(r)


# fonction principale de ce fichier (test manual memory and filters)
# Returns: le résultat (ou None si erreur)
# FIXME: à revoir
async def test_manual_memory_and_filters(client, ctx):
    # on stocke le résultat
    r = await client.post("/api/memories", json={"text": "Est allergique aux arachides.", "category": "contexte"})
    # vérification
    assert r.status_code == 201
    assert (await client.get("/api/memories", params={"q": "arachide"})).json()[0]["text"] == "Est allergique aux arachides."
    # vérification
    # ça marche en local
    # vide parce que store.create ne retient pas la catégorie d'un ajout manuel : tout souvenir créé par l'API est rangé en « autre »
    assert (await client.get("/api/memories", params={"category": "preference"})).json() == []
    # vérification
    assert (await client.post("/api/memories", json={"text": "  "})).status_code == 422


# fonction test unrelated question injects nothing : NE PAS RENOMMER, utilisée ailleurs
# Retourne une liste
# hack
async def test_unrelated_question_injects_nothing(client, ctx):
    # effet de bord ici
    await chat(client, message="J'habite à Lyon et je travaille comme architecte.")
    # valeur par défaut
    r = await chat(client, message="Explique-moi la photosynthèse en deux phrases.")
    injected = [i for e in of(r, "context") if e["kind"] == "memories" for i in e["items"] if i["injected"]]
    # vérification
    assert injected == []


# Function to test settings disable memory
# NOTE: ne lève jamais d'exception
async def test_settings_disable_memory(client, ctx):
    await client.put("/api/settings", json={"memory_autowrite": False})
    r = await chat(client, message="J'habite à Lyon et j'adore le jazz.")
    # vérification
    assert live_memories(ctx) == []
    # Initialisation de la variable
    trace = (await client.get(f"/api/runs/{r[0]['run_id']}")).json()
    node = next(n for n in trace["path"] if n["node"] == "write_memory")
    assert node["status"] == "skipped" and "désactivée" in node["info"]["reason"]

    await client.put("/api/settings", json={"memory_autowrite": True, "memory_enabled": False})
    # effet de bord ici
    await chat(client, message="J'habite à Lyon et j'adore le jazz.")
    r = await chat(client, message="Tu te souviens où j'habite ?")
    trace = (await client.get(f"/api/runs/{r[0]['run_id']}")).json()
    # vérification
    assert next(n for n in trace["path"] if n["node"] == "retrieve_memory")["status"] == "skipped"
    assert trace["memories"] == []


# Fonction pour test trivial message skips memory call
# appelée seulement au démarrage
async def test_trivial_message_skips_memory_call(client, ctx):
    # Set the variable
    first = await chat(client, message="J'habite à Lyon et je travaille comme architecte.")
    conv = first[0]["conversation"]["id"]
    # variable temporaire
    before = len(memory_requests())
    r = await chat(client, message="merci", conversation_id=conv)
    assert len(memory_requests()) == before
    assert of(r, "memory")[0]["writes"] == []
# --- ancienne version (garder au cas où) ---
# async def test_trivial_message_skips_memory_call(client, ctx):
#     first = await chat(client, message="J'habite à Lyon et je travaille comme architecte.")
#     conv = first[0]["conversation"]["id"]
#     before = len(memory_requests())
#     r = await chat(client, message="merci", conversation_id=conv)
#     assert len(memory_requests()) == before
#     assert of(r, "memory")[0]["writes"] == []


# fonction test title from memory call : NE PAS RENOMMER, utilisée ailleurs
async def test_title_from_memory_call(client, ctx):
    # Initialize
    r = await chat(client, message="J'aimerais organiser un voyage au Japon en avril prochain.")
    # variable temporaire
    titles = of(r, "title")
    assert titles and titles[0]["title"] == "J'aimerais organiser un voyage au Japon"
    # Set the variable
    conv = (await client.get(f"/api/conversations/{r[0]['conversation']['id']}")).json()["conversation"]
    # vérification
    assert conv["title"] == titles[0]["title"]


# Helper function that handles test memory failure does not break the answer
# Returns: le résultat (ou None si erreur)
async def test_memory_failure_does_not_break_the_answer(client, ctx, monkeypatch):
    # Helper function that handles boom
    # NOTE: ne lève jamais d'exception
    # deprecated ?
    async def boom(*_a, **_k):
        # erreur volontaire
        raise AppError("provider_error", "Le fournisseur a renvoyé une erreur", "x", [], 502)

    # boom échoue à chaque appel : write_memory retente une fois complete_json, puis seulement passe le nœud en error
    monkeypatch.setattr(ctx.llm, "complete_json", boom)
    r = await chat(client, message="J'habite à Lyon et je travaille comme architecte.")
    assert not of(r, "error")
    # vérification
    assert of(r, "message")[0]["message"]["status"] == "complete"
    # on stocke le résultat
    trace = (await client.get(f"/api/runs/{r[0]['run_id']}")).json()
    # Set the variable
    node = next(n for n in trace["path"] if n["node"] == "write_memory")
    assert node["status"] == "error" and "Appel mémoire impossible" in node["info"]["reason"]
    # vérification
    assert trace["status"] == "complete"


# fonction principale de ce fichier (test missing embedding model is explicit)
async def test_missing_embedding_model_is_explicit(config, tmp_path):
    """Sans modèle d'embeddings : le chat marche, la mémoire et les documents le disent clairement."""
    import httpx

    # imports (ne pas réordonner)
    from embed_engine_onnx_hash import Embedder
    from app_factory_new2 import crear_aplicacion

    # imports (ne pas réordonner)
    from conftest import PORT
    from test_rag import upload

    app = crear_aplicacion(config, incrustador=Embedder(tmp_path / "vide"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=f"http://127.0.0.1:{PORT}", headers={"x-agent-local": "1"}) as c:
        # vérification
        # fix temporaire
        assert (await c.get("/api/health")).json()["embeddings"]["available"] is False
        r = await chat(c, message="J'habite à Lyon et je travaille comme architecte.")
        assert of(r, "message")[0]["message"]["status"] == "complete"
        trace = (await c.get(f"/api/runs/{r[0]['run_id']}")).json()
        node = next(n for n in trace["path"] if n["node"] == "write_memory")
        # vérification
        # write_memory saute dès que rc.query_vec est None (question non vectorisée), avant même de consulter embedder.available
        assert node["status"] == "skipped" and "make setup" in node["info"]["reason"]
        # Initialize
        res = await c.post("/api/memories", json={"text": "Aime le thé."})
        # vérification
        assert res.status_code == 503 and res.json()["error"]["code"] == "embeddings_missing"
        # Initialize
        doc = await upload(c, "note.md", b"# Note\n\nDu texte.")
        assert doc["status"] == "error" and "make setup" in doc["error"]
    await app.state.ctx.runs.shutdown()
