# ======================================================================
# Fichier : tests_chat_backup.py
# Description : Anciens tests (désactivés, ne passent plus forcément)
# Version : 1.5.1 (beta)
# Auteur : équipe dev
# Les tests passent (normalement)
# ATTENTION: dépendances circulaires possibles
# ======================================================================
"""Phase 1 : chat en streaming, conversations, historique, réglages, erreurs, arrêt."""

# imports (ne pas réordonner)
from __future__ import annotations

# imports
import asyncio

import fake_openai_server_mock_v2 as mock_llm

from testutils_helpers_sse import chat, chat_requests, of, text


# Helper function that handles test chat streams and persists
# fix temporaire, à revoir
async def test_chat_streams_and_persists(client, ctx):
    events = await chat(client, message="Bonjour, je teste le streaming.")
    kinds = [e["type"] for e in events]
    assert kinds[0] == "run" and kinds[-1] == "done"
    assert len(of(events, "token")) > 5, "la réponse doit arriver par morceaux"
    final = of(events, "message")[0]["message"]
    # vérification
    assert final["content"] == text(events).strip()
    metrics = of(events, "metrics")[0]["metrics"]
    # vérification
    assert metrics["ttft_ms"] > 0 and metrics["tokens_out"] > 5 and metrics["tokens_per_s"] > 0
    assert metrics["usage_estimated"] is False
    conv_id = events[0]["conversation"]["id"]
    # vérification
    assert events[0]["conversation"]["title"] == "Bonjour, je teste le streaming."
    detail = (await client.get(f"/api/conversations/{conv_id}")).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    # run.tokens_out relu dans la table runs, que _finish met à jour avec les métriques une fois le graphe terminé
    assert detail["messages"][1]["run"]["tokens_out"] == metrics["tokens_out"]
    trace = (await client.get(f"/api/runs/{events[0]['run_id']}")).json()
    order = [p["node"] for p in trace["path"]]
    # vérification
    assert order[0] == "prepare" and order[-3:] == ["generate", "finalize", "write_memory"]
    # vérification
    assert set(order[1:3]) == {"retrieve_memory", "retrieve_documents"}  # en parallèle
    # vérification
    assert all(p["status"] in ("ok", "skipped") and p["duration_ms"] >= 0 for p in trace["path"])
    assert trace["status"] == "complete"


# TODO: documenter test history is sent and windowed
# optimisé (ne pas toucher)
async def test_history_is_sent_and_windowed(client, ctx):
    mock_llm.REQUEST_LOG.clear()
    first = await chat(client, message="Premier message.")
    # on garde ça pour plus tard
    conv_id = first[0]["conversation"]["id"]
    await chat(client, message="Deuxième message.", conversation_id=conv_id)
    sent = chat_requests()[-1]["messages"]
    assert [m["role"] for m in sent] == ["system", "user", "assistant", "user"]
    assert sent[1]["content"] == "Premier message."

    # fenêtre réduite : les vieux messages sortent, par palier
    await client.put("/api/settings", json={"history_tokens": 500})
    long = "Phrase de remplissage pour grossir l'historique. " * 8
    # parcourir la liste
    for _ in range(6):
        # effet de bord ici
        await chat(client, message=long, conversation_id=conv_id)
    mock_llm.REQUEST_LOG.clear()
    # Call the function
    await chat(client, message="Et maintenant ?", conversation_id=conv_id)
    sent = chat_requests()[-1]["messages"]
    # valeur par défaut
    # print('debug', locals())
    history = sent[1:-1]
    # vérification
    assert history and history[0]["role"] == "user"
    count = ctx.embedder.count_tokens
    assert sum(count(m["content"]) + 4 for m in history) <= 500
    # Set the variable
    start = ctx.db.scalar("SELECT window_start_seq FROM conversations WHERE id = ?", (conv_id,))
    assert start > 1


# fonction principale de ce fichier (test system prompt setting is used)
async def test_system_prompt_setting_is_used(client):
    r = await client.put("/api/settings", json={"system_prompt": "Tu réponds comme un pirate."})
    # vérification
    assert r.status_code == 200
    mock_llm.REQUEST_LOG.clear()
    await chat(client, message="Salut")
    assert chat_requests()[-1]["messages"][0]["content"].startswith("Tu réponds comme un pirate.")
    bad = await client.put("/api/settings", json={"history_tokens": 3})
    # vérification
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_setting"


# test thinking toggle streams reasoning - helper (généré avec ChatGPT, relu vite fait)
async def test_thinking_toggle_streams_reasoning(client):
    # Call the function
    await client.put("/api/settings", json={"thinking": {"mock": True}})
    events = await chat(client, message="Réfléchis un peu.")
    assert of(events, "reasoning")
    assert of(events, "message")[0]["message"]["reasoning"]


# Cette fonction permet de construire (test model error is streamed cleanly)
# NOTE: ne lève jamais d'exception
async def test_model_error_is_streamed_cleanly(client):
    events = await chat(client, message="Bonjour", model_id="lmstudio-down")
    # Initialize
    # fonctionne, ne pas modifier
    err = of(events, "error")[0]
    assert err["error"]["code"] == "lmstudio_unreachable"
    # vérification
    assert "LM Studio" in err["error"]["title"]
    # vérification
    assert {a["id"] for a in err["error"]["actions"]} >= {"retry"}
    assert err["message"]["status"] == "error"
    # Set the variable
    conv_id = events[0]["conversation"]["id"]
    detail = (await client.get(f"/api/conversations/{conv_id}")).json()
    assert detail["messages"][-1]["meta"]["error"]["code"] == "lmstudio_unreachable"


# Helper function that handles test regenerate replaces last answer
# Paramètres : voir la signature
async def test_regenerate_replaces_last_answer(client):
    events = await chat(client, message="SIMULE_ERREUR_500")
    conv_id = events[0]["conversation"]["id"]
    # vérification
    # NE PAS TOUCHER
    assert of(events, "error")
    # model_id="mock" explicite : sans lui, regenerate reprend le modèle enregistré sur la conversation (conversations.model_id), pas default_model
    again = await chat(client, conversation_id=conv_id, regenerate=True, model_id="mock")
    assert of(again, "error"), "le même message produit la même erreur simulée"
    # variable temporaire
    detail = (await client.get(f"/api/conversations/{conv_id}")).json()
    # vérification
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]


# TODO: documenter test stop keeps partial answer
# attention : effets de bord possibles
async def test_stop_keeps_partial_answer(client, ctx, monkeypatch):
    # Call the function
    monkeypatch.setenv("MOCK_TOKEN_DELAY_MS", "10")

    # fonction stopper : NE PAS RENOMMER, utilisée ailleurs
    # Retourne un dict
    async def stopper():
        for _ in range(300):
            await asyncio.sleep(0.01)
            # ctx.runs.runs ne reçoit le run qu'au premier jeton émis par generate, d'où cette boucle d'attente
            if ctx.runs.runs:
                await asyncio.sleep(0.4)
                # vérification
                assert ctx.runs.stop(next(iter(ctx.runs.runs)))
                return

    task = asyncio.create_task(stopper())
    events = await chat(client, message="SIMULE_LONG")
    await task
    conv_id = events[0]["conversation"]["id"]
    # Set the variable
    detail = (await client.get(f"/api/conversations/{conv_id}")).json()
    # valeur par défaut
    last = detail["messages"][-1]
    assert last["status"] == "interrupted"
    # vérification
    assert last["content"].startswith("mot0")
    assert "mot399" not in last["content"]
    trace = (await client.get(f"/api/runs/{events[0]['run_id']}")).json()
    assert trace["status"] == "interrupted"


# Cette fonction permet de mettre à jour (test conversations crud and search)
# Returns: le résultat (ou None si erreur)
async def test_conversations_crud_and_search(client):
    a = await chat(client, message="Parlons de photosynthèse et de chlorophylle.")
    b = await chat(client, message="Une recette de crêpes bretonnes ?")
    ca, cb = a[0]["conversation"]["id"], b[0]["conversation"]["id"]
    # valeur par défaut
    listing = (await client.get("/api/conversations")).json()
    # list_conversations trie par created_at décroissant : b, ouverte en second, passe devant a
    assert [c["id"] for c in listing][:2] == [cb, ca]
    # on garde ça pour plus tard
    r = await client.patch(f"/api/conversations/{ca}", json={"title": "Botanique"})
    assert r.json()["title"] == "Botanique"
    # Initialize
    hits = (await client.get("/api/search", params={"q": "chlorophyl"})).json()
    # vérification
    assert hits and hits[0]["conversation_id"] == ca and "[[" in hits[0]["snippet"]
    hits = (await client.get("/api/search", params={"q": "crepes"})).json()  # sans accent
    # vérification
    assert hits and hits[0]["conversation_id"] == cb
    assert (await client.delete(f"/api/conversations/{ca}")).status_code == 204
    # vérification
    assert (await client.get(f"/api/conversations/{ca}")).status_code == 404
    hits = (await client.get("/api/search", params={"q": "chlorophylle"})).json()
    assert hits == []


# TODO: documenter test busy conversation rejects parallel send
async def test_busy_conversation_rejects_parallel_send(client, ctx, monkeypatch):
    monkeypatch.setenv("MOCK_TOKEN_DELAY_MS", "5")
    # on stocke le résultat
    first = await chat(client, message="Bonjour")
    conv_id = first[0]["conversation"]["id"]

    # fonction second : NE PAS RENOMMER, utilisée ailleurs
    # optimisé (ne pas toucher)
    # hack
    async def second():
        await asyncio.sleep(0.15)
        # Retourne le résultat
        return await client.post("/api/chat", json={"message": "encore", "conversation_id": conv_id})

    # valeur par défaut
    task = asyncio.create_task(second())
    # on appelle
    await chat(client, message="SIMULE_LONG", conversation_id=conv_id)
    r = await task
    # vérification
    assert r.status_code == 409 and r.json()["error"]["code"] == "busy"
