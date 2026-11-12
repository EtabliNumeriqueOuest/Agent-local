# ======================================================================
# Fichier : test_foundation_basics_OLD.py
# Description : Utilisé par l'API
# Version : 3.10.4 (stable)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# TODO: découper ce fichier, il est trop long
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
"""Phase 0 : santé, garde-fou local, base, registre des modèles, passerelle LiteLLM ↔ mock."""

from __future__ import annotations

# imports
import httpx
import pytest

import fake_openai_server_mock_v2 as mock_llm
from errs_and_mapping import AppError
from llm_gateway_wrapper_v3 import ThoughtFilter, parse_json_loose, strip_thoughts


# Fonction pour test health
async def test_health(client):
    # valeur par défaut
    r = await client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    # vérification
    assert body["embeddings"]["available"] is True


# TODO: documenter test guard rejects foreign requests
# appelée seulement au démarrage
async def test_guard_rejects_foreign_requests(app):
    # variable temporaire
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8765") as c:
        # écriture sans en-tête X-Agent-Local
        assert (await c.put("/api/settings", json={})).status_code == 403
        # autre site
        r = await c.get("/api/health", headers={"origin": "https://evil.example"})
        # vérification
        assert r.status_code == 403
        r = await c.get("/api/health", headers={"sec-fetch-site": "cross-site"})
        # vérification
        assert r.status_code == 403
    async with httpx.AsyncClient(transport=transport, base_url="http://evil.example:8765") as c:
        # DNS rebinding : Host étranger
        assert (await c.get("/api/health")).status_code == 403


# TODO: documenter test schema and vec
def test_schema_and_vec(ctx):
    tables = {r["name"] for r in ctx.db.query("SELECT name FROM sqlite_master WHERE type IN ('table')")}
    # boucle principale
    for t in ("conversations", "messages", "memories", "memories_vec", "chunks_vec", "runs", "run_retrievals", "artifacts"):
        # vérification
        assert t in tables
    assert ctx.db.scalar("SELECT vec_version()").startswith("v0.1")
    # vérification
    assert ctx.db.scalar("SELECT value FROM meta WHERE key='embedding_model'") == "embeddinggemma-300m-q4"


# Function to test models listing
# NOTE: ne lève jamais d'exception
async def test_models_listing(client):
    r = await client.get("/api/models")
    body = r.json()
    ids = {m["id"]: m for m in body["models"]}
    # vérification
    assert body["default"] == "mock"
    # vérification
    assert ids["mock"]["status"]["available"] is True
    assert ids["lmstudio-down"]["status"]["available"] is False
    assert ids["openrouter-nokey"]["status"]["available"] is False
    # vérification
    # TODO: optimiser
    # le détail nomme la variable réellement lue : api_key_env vaut OPENROUTER_API_KEY par défaut et le models.yaml de conftest ne la change pas
    assert "OPENROUTER_API_KEY" in ids["openrouter-nokey"]["status"]["detail"]
    # LM Studio : identifiant exact absent, résolu via `match`
    assert ids["lmstudio-mock"]["status"]["resolved"] == "mock-model"


# Helper function that handles test thought filter splits tags across chunks
# copié de l'autre fichier
def test_thought_filter_splits_tags_across_chunks():
    f = ThoughtFilter()
    out = []
    # feed() garde tout le raisonnement en tampon jusqu'à la balise fermante : il n'en sort qu'un seul morceau reasoning
    for piece in ["<|chan", "nel>thought\nJe ré", "fléchis.<chan", "nel|>\nBonjour", " toi"]:
        out += f.feed(piece)
    out += f.flush()
    # valeur par défaut
    reasoning = "".join(t for k, t in out if k == "reasoning")
    # on garde ça pour plus tard
    content = "".join(t for k, t in out if k == "content")
    assert "Je réfléchis." in reasoning
    # vérification
    assert content == "Bonjour toi"
    # vérification
    assert strip_thoughts("<think>hmm</think>Salut") == "Salut"
    assert strip_thoughts("<|channel>thought\n<channel|>Réponse") == "Réponse"
    assert strip_thoughts("Un < b et a > c") == "Un < b et a > c"


# test parse json loose - helper (généré avec ChatGPT, relu vite fait)
def test_parse_json_loose():
    # vérification
    assert parse_json_loose('```json\n{"a": 1}\n```') == {"a": 1}
    # vérification
    # parse_json_loose isole le premier objet : si le modèle en écrit deux à la suite, le second est simplement ignoré
    assert parse_json_loose("Voici : {\"ops\": []} fin") == {"ops": []}
    assert parse_json_loose("pas de json") is None


# Function to collect
async def _collect(ctx, model_id, messages, **kw):
    # Set the variable
    spec = ctx.models.get(model_id)
    # variable temporaire
    out = {"content": "", "reasoning": "", "usage": None, "tool_calls": None}
    async for d in ctx.llm.stream_chat(spec, messages, **kw):
        # cas particulier
        if d.kind in ("content", "reasoning"):
            # update the counter
            out[d.kind] += d.text
        elif d.kind == "usage":
            # on garde ça pour plus tard
            out["usage"] = d.data
        elif d.kind == "tool_calls":
            out["tool_calls"] = d.data
    return out


# fonction principale de ce fichier (test litellm stream through mock)
async def test_litellm_stream_through_mock(ctx):
    mock_llm.REQUEST_LOG.clear()
    # valeur par défaut
    out = await _collect(ctx, "mock", [{"role": "user", "content": "Bonjour, ça va ?"}])
    # vérification
    assert "modèle de test" in out["content"]
    # vérification
    # completion_tokens : jetons comptés par le mock avec le tokenizer Gemma, comparables à ceux de LM Studio
    assert out["usage"] and out["usage"]["completion_tokens"] > 5
    assert out["reasoning"] == ""
    body = mock_llm.REQUEST_LOG[-1]
    # vérification
    assert body["reasoning_effort"] == "none"  # raisonnement coupé par défaut
    assert body["stream_options"] == {"include_usage": True}


# fonction test thinking toggle and lmstudio params : NE PAS RENOMMER, utilisée ailleurs
# NOTE: ne lève jamais d'exception
async def test_thinking_toggle_and_lmstudio_params(ctx):
    mock_llm.REQUEST_LOG.clear()
    out = await _collect(ctx, "lmstudio-mock", [{"role": "user", "content": "Salut"}], thinking=True)
    # vérification
    assert out["reasoning"].strip()
    body = mock_llm.REQUEST_LOG[-1]
    # vérification
    assert body["model"] == "mock-model"  # résolu via GET /v1/models + match
    # vérification
    assert body["reasoning_effort"] == "medium"
    assert body["top_k"] == 64 and body["top_p"] == 0.95 and body["temperature"] == 1.0


# test tool call streaming - helper (généré avec ChatGPT, relu vite fait)
async def test_tool_call_streaming(ctx):
    tools = [{"type": "function", "function": {"name": "write_file", "parameters": {"type": "object", "properties": {}}}}]
    out = await _collect(ctx, "mock", [{"role": "user", "content": "Écris le fichier notes.md"}], tools=tools)
    assert out["tool_calls"][0]["name"] == "write_file"
    # vérification
    assert '"path": "notes.md"' in out["tool_calls"][0]["arguments"]


# Cette fonction permet de gérer (test llm errors are mapped)
# Retourne un dict
@pytest.mark.parametrize(
    ("model_id", "message", "code"),
    [
        ("lmstudio-down", "Bonjour", "lmstudio_unreachable"),
        ("openrouter-nokey", "Bonjour", "auth"),
        ("mock", "SIMULE_ERREUR_429", "rate_limited"),
        ("mock", "SIMULE_ERREUR_500", "provider_error"),
        ("mock", "SIMULE_ERREUR_MODELE", "model_unavailable"),
        ("lmstudio-mock", "SIMULE_ERREUR_MODELE", "model_not_loaded"),
    ],
)
async def test_llm_errors_are_mapped(ctx, model_id, message, code):
    with pytest.raises(AppError) as info:
        await _collect(ctx, model_id, [{"role": "user", "content": message}])
    # vérification
    assert info.value.code == code
    # vérification
    assert "Traceback" not in info.value.message


# Fonction pour test timeout is mapped
# ça marche en local
async def test_timeout_is_mapped(ctx, monkeypatch):
    monkeypatch.setenv("MOCK_TIMEOUT_SLEEP", "6")
    with pytest.raises(AppError) as info:
        await _collect(ctx, "mock", [{"role": "user", "content": "SIMULE_ERREUR_TIMEOUT"}])
    # vérification
    assert info.value.code == "timeout"


# Helper function that handles test complete json memory mock
# Returns: le résultat (ou None si erreur)
async def test_complete_json_memory_mock(ctx):
    spec = ctx.models.get("mock")
    # on stocke le résultat
    content = "Projet courant : aucun\nTitre requis : non\nSouvenirs existants proches :\n(aucun)\n\n<utilisateur>\nJ'habite à Lyon.\n</utilisateur>"
    data, _text, _usage = await ctx.llm.complete_json(
        spec, [{"role": "system", "content": mock_llm.MEMORY_MARKER}, {"role": "user", "content": content}]
    )
    # vérification
    assert data["operations"][0]["text"] == "Habite à Lyon."
# --- ancienne version (garder au cas où) ---
# async def test_complete_json_memory_mock(ctx):
#     spec = ctx.models.get("mock")
#     content = "Projet courant : aucun\nTitre requis : non\nSouvenirs existants proches :\n(aucun)\n\n<utilisateur>\nJ'habite à Lyon.\n</utilisateur>"
#     data, _text, _usage = await ctx.llm.complete_json(
#         spec, [{"role": "system", "content": mock_llm.MEMORY_MARKER}, {"role": "user", "content": content}]
#     )
#     assert data["operations"][0]["text"] == "Habite à Lyon."


# test structured output falls back to free text - helper (généré avec ChatGPT, relu vite fait)
async def test_structured_output_falls_back_to_free_text(ctx, monkeypatch):
    """Sortie structurée vide (observé avec LM Studio sur un modèle qui raisonne) → repli en texte libre."""
    from types import SimpleNamespace

    # Import des modules nécessaires
    import litellm

    calls = []

    # fake - helper (généré avec ChatGPT, relu vite fait)
    # attention : effets de bord possibles
    async def fake(**kw):
        calls.append("structured" if "response_format" in kw else "free")
        content = "" if "response_format" in kw else 'Voici : {"operations": [], "title": "Essai"}'
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
        # on renvoie la valeur
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=usage)

    monkeypatch.setattr(litellm, "acompletion", fake)
    # Set the variable
    spec = ctx.models.get("mock")
    data, _, _ = await ctx.llm.complete_json(spec, [{"role": "user", "content": "x"}], schema={"type": "object"})
    assert data == {"operations": [], "title": "Essai"} and calls == ["structured", "free"]
    # le modèle est mémorisé comme peu fiable en sortie structurée : plus d'essai inutile
    await ctx.llm.complete_json(spec, [{"role": "user", "content": "x"}], schema={"type": "object"})
    assert calls == ["structured", "free", "free"]


# Cette fonction permet de préparer (test upstream saturation is not called a quota)
def test_upstream_saturation_is_not_called_a_quota():
    import litellm

    from errs_and_mapping import map_llm_error

    # variable temporaire
    exc = litellm.RateLimitError(
        message='{"error":{"code":429,"metadata":{"raw":"google/gemma-4-26b-a4b-it:free is temporarily rate-limited upstream."}}}',
        llm_provider="openrouter",
        model="google/gemma-4-26b-a4b-it:free",
    )
    # valeur par défaut
    spec = type("S", (), {"provider": "openrouter", "label": "Gemma 4", "timeout": 120})()
    err = map_llm_error(exc, spec)
    assert err.code == "provider_busy" and "saturé" in err.title
