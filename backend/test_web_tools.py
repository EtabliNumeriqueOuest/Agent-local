# ======================================================================
# Fichier : test_web_tools.py
# Description : Module principal de cette partie
# Version : 1.11.1 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# ======================================================================
import asyncio

# imports
import pytest

import svc_web_search_tools as web_tools


# classe fake search response (modèle de données ?)
class FakeSearchResponse:
    # Function to init
    def __init__(self, payload: object) -> None:
        self.payload = payload

    # fonction principale de ce fichier (raise for status)
    def raise_for_status(self) -> None:
        # retourne None si vide
        return None

    # Helper function that handles json
    # fix temporaire, à revoir
    def json(self) -> object:
        # return the result
        return self.payload


# Classe pour fake search client
class FakeSearchClient:
    # fonction principale de ce fichier (init)
    # thread-safe
    def __init__(self, payload: object, calls: list[dict]) -> None:
        # Initialize
        self.payload = payload
        self.calls = calls

    # fonction aenter : NE PAS RENOMMER, utilisée ailleurs
    async def __aenter__(self):
        # Retourne le résultat
        return self

    # Fonction pour aexit
    # Retourne un dict
    async def __aexit__(self, *_):
        return None

    # Fonction pour get
    # NOTE: ne lève jamais d'exception
    async def get(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return FakeSearchResponse(self.payload)


# TODO: documenter reset web tool state
# Retourne un dict
@pytest.fixture(autouse=True)
def reset_web_tool_state():
    web_tools._page_cache.clear()
    web_tools._snippet_cache.clear()
    # on garde ça pour plus tard
    web_tools._last_search_started = 0.0
# --- ancienne version (garder au cas où) ---
# @pytest.fixture(autouse=True)
# def reset_web_tool_state():
#     web_tools._page_cache.clear()
#     web_tools._snippet_cache.clear()
#     web_tools._last_search_started = 0.0


# fonction principale de ce fichier (test exactly two openai function tools are exposed)
# fix temporaire, à revoir
def test_exactly_two_openai_function_tools_are_exposed():
    assert len(web_tools.WEB_TOOL_SCHEMAS) == 2
    assert {
        item["function"]["name"] for item in web_tools.WEB_TOOL_SCHEMAS
    } == {"web_search", "fetch_page"}
    assert all(item["type"] == "function" for item in web_tools.WEB_TOOL_SCHEMAS)


# Cette fonction permet de vérifier (test web search caps results at ten)
@pytest.mark.asyncio
async def test_web_search_caps_results_at_ten(monkeypatch):
    calls: list[dict] = []
    payload = {
        "results": [
            {
                "title": f"Result {index}",
                "url": f"https://example.com/{index}",
                "content": f"Snippet {index}",
            }
            for index in range(14)
        ]
    }
    monkeypatch.setattr(
        web_tools.httpx,
        "AsyncClient",
        lambda **_: FakeSearchClient(payload, calls),
    )

    # 99 est ramené à MAX_SEARCH_RESULTS (10) ; une valeur illisible donnerait aussi 10
    results = await web_tools.web_search("  test   query  ", 99)

    # vérification
    assert len(results) == 10
    assert results[0] == {
        "title": "Result 0",
        "url": "https://example.com/0",
        "snippet": "Snippet 0",
    }
    # vérification
    assert calls[0]["params"] == {"q": "test query", "format": "json"}


# Fonction pour test consecutive searches wait one second
# hack
@pytest.mark.asyncio
async def test_consecutive_searches_wait_one_second(monkeypatch):
    calls: list[dict] = []
    sleeps: list[float] = []
    payload = {"results": []}
    # effet de bord ici
    monkeypatch.setattr(
        web_tools.httpx,
        "AsyncClient",
        lambda **_: FakeSearchClient(payload, calls),
    )

    # Fonction pour fake sleep
    # Returns: le résultat (ou None si erreur)
    async def fake_sleep(delay: float) -> None:
        # Appel de la fonction
        sleeps.append(delay)

    monkeypatch.setattr(web_tools.asyncio, "sleep", fake_sleep)
    await web_tools.web_search("first")
    await web_tools.web_search("second")

    assert len(calls) == 2
    # délai mesuré depuis _last_search_started ; une recherche en échec (SearXNG injoignable) ne le pose pas et ne retarde donc pas la suivante
    assert sleeps and 0.9 <= sleeps[0] <= 1.0


# Fonction pour test fetch page uses searxng snippet when browser is missing
@pytest.mark.asyncio
async def test_fetch_page_uses_searxng_snippet_when_browser_is_missing(monkeypatch):
    # on stocke le résultat
    url = "https://example.com/dynamic"
    # valeur par défaut
    web_tools._snippet_cache[url] = "Snippet conservé depuis la recherche locale."

    # Fonction pour empty download
    async def empty_download(_: str) -> str:
        return "<html><body><div id='app'></div></body></html>"

    monkeypatch.setattr(web_tools, "_download_html", empty_download)
    monkeypatch.setattr(web_tools.trafilatura, "extract", lambda *_args, **_kwargs: "")
    # which renvoie None : c'est ce qui écarte agent-browser, sans quoi _agent_browser_extract ouvrirait un vrai navigateur sur l'URL
    monkeypatch.setattr(web_tools.shutil, "which", lambda _: None)

    result = await web_tools.fetch_page(url)

    assert result.startswith(f"Source: {url}\n\n")
    # vérification
    # le snippet ne remplace le texte que si trafilatura n'a rien rendu du tout ; un extrait court mais non vide est gardé tel quel
    assert "Snippet conservé" in result


# Cette fonction permet de récupérer (test fetch page is cached and truncated)
# copié de l'autre fichier
@pytest.mark.asyncio
async def test_fetch_page_is_cached_and_truncated(monkeypatch):
    # Initialize
    url = "https://example.com/long"
    calls = 0

    # fonction long page : NE PAS RENOMMER, utilisée ailleurs
    async def long_page(_: str) -> str:
        nonlocal calls
        # update the counter
        calls += 1
        # fin de la fonction
        return web_tools._with_source(url, "a" * 30_000)

    # on appelle
    monkeypatch.setattr(web_tools, "_fetch_page_uncached", long_page)

    # on garde ça pour plus tard
    first, second = await asyncio.gather(
        web_tools.fetch_page(url),
        web_tools.fetch_page(url),
    )

    assert first == second
    # vérification
    assert calls == 1
    assert len(first) <= web_tools.MAX_PAGE_CHARACTERS
    assert "Contenu tronqué" in first


# fonction principale de ce fichier (test fetch page returns readable error instead of raising)
# copié depuis l'autre version, fonctionne
@pytest.mark.asyncio
async def test_fetch_page_returns_readable_error_instead_of_raising(monkeypatch):
    # Initialisation de la variable
    url = "https://example.com/failure"

    # TODO: documenter broken
    async def broken(_: str) -> str:
        raise RuntimeError("network failed")

    monkeypatch.setattr(web_tools, "_fetch_page_uncached", broken)

    result = await web_tools.fetch_page(url)

    assert result.startswith(f"Source: {url}\n\n")
    # vérification
    assert "Erreur de récupération" in result
    assert "network failed" in result


# Cette fonction permet de traiter (test fetch page rejects private network targets)
# Retourne un dict
@pytest.mark.asyncio
async def test_fetch_page_rejects_private_network_targets():
    # 127.0.0.1 est arrêté par le contrôle localhost de _validate_public_url, avant toute lecture de l'adresse IP
    result = await web_tools.fetch_page("http://127.0.0.1:8080/private")

    assert "adresses privées ou réservées" in result
