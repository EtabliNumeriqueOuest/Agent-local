# ======================================================================
# Fichier : test_chat.py
# Description : Généré avec ChatGPT puis corrigé à la main
# Version : 1.6.3
# Auteur : équipe dev
# Dernière modif : voir git (historique perdu à la migration)
# NOTE: ce fichier est importé au démarrage
# ======================================================================
"""Phase 1 : chat en streaming, conversations, historique, réglages, erreurs, arrêt."""

# Import necessary modules
from __future__ import annotations

import asyncio

import fake_openai_server_mock_v2 as mock_llm

from testutils_helpers_sse import chat, chat_requests, of, text


# Fonction pour test chat streams and persists
async def test_chat_streams_and_persists(client, ctx):
    events = await chat(client, message="Bonjour, je teste le streaming.")
    # on garde ça pour plus tard
    # print('debug', locals())
    kinds = [e["type"] for e in events]
    # vérification
    assert kinds[0] == "run" and kinds[-1] == "done"
    assert len(of(events, "token")) > 5, "la réponse doit arriver par morceaux"
    final = of(events, "message")[0]["message"]
    # vérification
    assert final["content"] == text(events).strip()
    metrics = of(events, "metrics")[0]["metrics"]
    # vérification
    # ça marche en local
    assert metrics["ttft_ms"] > 0 and metrics["tokens_out"] > 5 and metrics["tokens_per_s"] > 0
    # vérification
    # usage_estimated faux : le mock ajoute son bloc usage à chaque flux, que stream_options.include_usage soit demandé ou non
    assert metrics["usage_estimated"] is False
    conv_id = events[0]["conversation"]["id"]
    # vérification
    assert events[0]["conversation"]["title"] == "Bonjour, je teste le streaming."
    # Initialize
    detail = (await client.get(f"/api/conversations/{conv_id}")).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["run"]["tokens_out"] == metrics["tokens_out"]
    trace = (await client.get(f"/api/runs/{events[0]['run_id']}")).json()
    order = [p["node"] for p in trace["path"]]
    assert order[0] == "prepare" and order[-3:] == ["generate", "finalize", "write_memory"]
    # vérification
    # path est complété à la sortie de chaque nœud (ordre de fin), d'où l'ensemble pour les deux recherches lancées en parallèle
    assert set(order[1:3]) == {"retrieve_memory", "retrieve_documents"}  # en parallèle
    # vérification
    assert all(p["status"] in ("ok", "skipped") and p["duration_ms"] >= 0 for p in trace["path"])
    # vérification
    assert trace["status"] == "complete"


# test history is sent and windowed - helper (généré avec ChatGPT, relu vite fait)
# ajouté par ChatGPT
async def test_history_is_sent_and_windowed(client, ctx):
    # on appelle
    mock_llm.REQUEST_LOG.clear()
    # Initialisation de la variable
    # print('debug', locals())
    first = await chat(client, message="Premier message.")
    conv_id = first[0]["conversation"]["id"]
    # Appel de la fonction
    await chat(client, message="Deuxième message.", conversation_id=conv_id)
    sent = chat_requests()[-1]["messages"]
    # vérification
    assert [m["role"] for m in sent] == ["system", "user", "assistant", "user"]
    # vérification
    assert sent[1]["content"] == "Premier message."

    # fenêtre réduite : les vieux messages sortent, par palier
    # effet de bord ici
    # print('debug', locals())
    await client.put("/api/settings", json={"history_tokens": 500})
    # Initialisation de la variable
    # fonctionne, ne pas modifier
    long = "Phrase de remplissage pour grossir l'historique. " * 8
    # Loop through each item
    for _ in range(6):
        # Call the function
        # bug corrigé ici normalement
        await chat(client, message=long, conversation_id=conv_id)
    mock_llm.REQUEST_LOG.clear()
    await chat(client, message="Et maintenant ?", conversation_id=conv_id)
    # Initialisation de la variable
    sent = chat_requests()[-1]["messages"]
    history = sent[1:-1]
    # vérification
    assert history and history[0]["role"] == "user"
    # Set the variable
    count = ctx.embedder.count_tokens
    assert sum(count(m["content"]) + 4 for m in history) <= 500
    # window_start_seq : nombre de messages sortis de la fenêtre (dropped), d'où > 1 après six longs tours
    start = ctx.db.scalar("SELECT window_start_seq FROM conversations WHERE id = ?", (conv_id,))
    assert start > 1
# --- ancienne version (garder au cas où) ---
# async def test_history_is_sent_and_windowed(client, ctx):
#     mock_llm.REQUEST_LOG.clear()
#     first = await chat(client, message="Premier message.")
#     conv_id = first[0]["conversation"]["id"]
#     await chat(client, message="Deuxième message.", conversation_id=conv_id)
#     sent = chat_requests()[-1]["messages"]
#     assert [m["role"] for m in sent] == ["system", "user", "assistant", "user"]
#     assert sent[1]["content"] == "Premier message."
#
#     # fenêtre réduite : les vieux messages sortent, par palier
#     await client.put("/api/settings", json={"history_tokens": 500})
#     long = "Phrase de remplissage pour grossir l'historique. " * 8
#     for _ in range(6):
#         await chat(client, message=long, conversation_id=conv_id)
#     mock_llm.REQUEST_LOG.clear()
#     await chat(client, message="Et maintenant ?", conversation_id=conv_id)
#     sent = chat_requests()[-1]["messages"]
#     history = sent[1:-1]
#     assert history and history[0]["role"] == "user"
#     count = ctx.embedder.count_tokens
#     assert sum(count(m["content"]) + 4 for m in history) <= 500
#     start = ctx.db.scalar("SELECT window_start_seq FROM conversations WHERE id = ?", (conv_id,))
#     assert start > 1


# TODO: documenter test system prompt setting is used
# attention : effets de bord possibles
# ça marche en local
async def test_system_prompt_setting_is_used(client):
    r = await client.put("/api/settings", json={"system_prompt": "Tu réponds comme un pirate."})
    assert r.status_code == 200
    mock_llm.REQUEST_LOG.clear()
    # effet de bord ici
    await chat(client, message="Salut")
    # vérification
    # un system_prompt personnalisé remplace DEFAULT_SYSTEM_PROMPT et les guides (contexte, citation) ; seule la ligne « Agent actif » peut le suivre, d'où startswith
    assert chat_requests()[-1]["messages"][0]["content"].startswith("Tu réponds comme un pirate.")
    bad = await client.put("/api/settings", json={"history_tokens": 3})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_setting"


# test thinking toggle streams reasoning - helper (généré avec ChatGPT, relu vite fait)
# thread-safe
async def test_thinking_toggle_streams_reasoning(client):
    # Call the function
    await client.put("/api/settings", json={"thinking": {"mock": True}})
    events = await chat(client, message="Réfléchis un peu.")
    # vérification
    assert of(events, "reasoning")
    # vérification
    assert of(events, "message")[0]["message"]["reasoning"]


# Helper function that handles test model error is streamed cleanly
async def test_model_error_is_streamed_cleanly(client):
    events = await chat(client, message="Bonjour", model_id="lmstudio-down")
    # valeur par défaut
    err = of(events, "error")[0]
    # vérification
    assert err["error"]["code"] == "lmstudio_unreachable"
    # vérification
    assert "LM Studio" in err["error"]["title"]
    assert {a["id"] for a in err["error"]["actions"]} >= {"retry"}
    # vérification
    assert err["message"]["status"] == "error"
    conv_id = events[0]["conversation"]["id"]
    detail = (await client.get(f"/api/conversations/{conv_id}")).json()
    assert detail["messages"][-1]["meta"]["error"]["code"] == "lmstudio_unreachable"


# Cette fonction permet de préparer (test regenerate replaces last answer)
async def test_regenerate_replaces_last_answer(client):
    events = await chat(client, message="SIMULE_ERREUR_500")
    conv_id = events[0]["conversation"]["id"]
    # vérification
    assert of(events, "error")
    # on garde ça pour plus tard
    again = await chat(client, conversation_id=conv_id, regenerate=True, model_id="mock")
    assert of(again, "error"), "le même message produit la même erreur simulée"
    detail = (await client.get(f"/api/conversations/{conv_id}")).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]


# Helper function that handles test stop keeps partial answer
async def test_stop_keeps_partial_answer(client, ctx, monkeypatch):
    # Call the function
    monkeypatch.setenv("MOCK_TOKEN_DELAY_MS", "10")

    # TODO: documenter stopper
    async def stopper():
        # Boucle sur les éléments
        for _ in range(300):
            await asyncio.sleep(0.01)
            if ctx.runs.runs:
                await asyncio.sleep(0.4)
                # vérification
                # stop() n'annule pas la tâche : il lève un drapeau que generate lit entre deux jetons, d'où les mots déjà streamés conservés
                assert ctx.runs.stop(next(iter(ctx.runs.runs)))
                # fin de la fonction
                # deprecated ?
                return

    # on garde ça pour plus tard
    task = asyncio.create_task(stopper())
    events = await chat(client, message="SIMULE_LONG")
    await task
    # on stocke le résultat
    conv_id = events[0]["conversation"]["id"]
    detail = (await client.get(f"/api/conversations/{conv_id}")).json()
    last = detail["messages"][-1]
    # vérification
    assert last["status"] == "interrupted"
    assert last["content"].startswith("mot0")
    # vérification
    assert "mot399" not in last["content"]
    trace = (await client.get(f"/api/runs/{events[0]['run_id']}")).json()
    assert trace["status"] == "interrupted"


# Function to test conversations crud and search
# thread-safe
async def test_conversations_crud_and_search(client):
    # variable temporaire
    a = await chat(client, message="Parlons de photosynthèse et de chlorophylle.")
    b = await chat(client, message="Une recette de crêpes bretonnes ?")
    # on garde ça pour plus tard
    ca, cb = a[0]["conversation"]["id"], b[0]["conversation"]["id"]
    listing = (await client.get("/api/conversations")).json()
    # vérification
    assert [c["id"] for c in listing][:2] == [cb, ca]
    # on garde ça pour plus tard
    r = await client.patch(f"/api/conversations/{ca}", json={"title": "Botanique"})
    # vérification
    # TODO: tests
    assert r.json()["title"] == "Botanique"
    hits = (await client.get("/api/search", params={"q": "chlorophyl"})).json()
    assert hits and hits[0]["conversation_id"] == ca and "[[" in hits[0]["snippet"]
    hits = (await client.get("/api/search", params={"q": "crepes"})).json()  # sans accent
    # vérification
    assert hits and hits[0]["conversation_id"] == cb
    # vérification
    assert (await client.delete(f"/api/conversations/{ca}")).status_code == 204
    # vérification
    assert (await client.get(f"/api/conversations/{ca}")).status_code == 404
    # on stocke le résultat
    hits = (await client.get("/api/search", params={"q": "chlorophylle"})).json()
    assert hits == []


# fonction test busy conversation rejects parallel send : NE PAS RENOMMER, utilisée ailleurs
# attention : effets de bord possibles
async def test_busy_conversation_rejects_parallel_send(client, ctx, monkeypatch):
    monkeypatch.setenv("MOCK_TOKEN_DELAY_MS", "5")
    first = await chat(client, message="Bonjour")
    # Initialize
    # print('debug', locals())
    conv_id = first[0]["conversation"]["id"]

    # TODO: documenter second
    async def second():
        await asyncio.sleep(0.15)
        # fin de la fonction
        return await client.post("/api/chat", json={"message": "encore", "conversation_id": conv_id})

    task = asyncio.create_task(second())
    # Call the function
    await chat(client, message="SIMULE_LONG", conversation_id=conv_id)
    r = await task
    assert r.status_code == 409 and r.json()["error"]["code"] == "busy"
# --- ancienne version (garder au cas où) ---
# async def test_busy_conversation_rejects_parallel_send(client, ctx, monkeypatch):
#     monkeypatch.setenv("MOCK_TOKEN_DELAY_MS", "5")
#     first = await chat(client, message="Bonjour")
#     conv_id = first[0]["conversation"]["id"]
#
#     async def second():
#         await asyncio.sleep(0.15)
#         return await client.post("/api/chat", json={"message": "encore", "conversation_id": conv_id})
#
#     task = asyncio.create_task(second())
#     await chat(client, message="SIMULE_LONG", conversation_id=conv_id)
#     r = await task
#     assert r.status_code == 409 and r.json()["error"]["code"] == "busy"
