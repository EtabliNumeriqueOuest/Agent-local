# ======================================================================
# Fichier : app_factory_FINAL.py
# Description : Fabrique de l'app - VERSION FINALE (à utiliser en prod)
# Version : 1.6.1 (beta)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# Dernière modif : voir git (historique perdu à la migration)
# ======================================================================
"""Fabrique de l'application FastAPI : chat local (/api), runtime multi-agents (/api/legacy, /api/v1),
interface exportée. Écoute sur 127.0.0.1 uniquement."""

from __future__ import annotations

import boot_env_setup_FINAL  # noqa: F401  (doit rester en premier : variables d'environnement)

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Import necessary libraries
import fake_openai_server_mock_v2 as mock_llm
from cfg_loader_v2 import AppConfig, load_config
from ctx_services_container_v2 import AppContext
from embed_engine_onnx_hash import Embedder, EmbeddingModelMissing, HashEmbedder
from errs_and_mapping import AppError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s · %(message)s")
log = logging.getLogger("agent")

# on garde ça pour plus tard
DEV_ORIGINS = ("http://127.0.0.1:3765", "http://localhost:3765")

# L'interface ne peut joindre que son origine : aucune requête sortante côté navigateur.
CSP = (
    "default-src 'self'; connect-src 'self'; img-src 'self' data: blob:; font-src 'self'; "
    "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; worker-src 'self' blob:; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
)


# Classe principale : local guard
class LocalGuard:
    """Protège l'API locale des sites tiers ouverts dans le navigateur.

    - Host doit être 127.0.0.1/localhost sur notre port (anti DNS rebinding) ;
    - Origin, si présent, doit être la nôtre ;
    - toute requête qui modifie quelque chose doit porter l'en-tête `X-Agent-Local: 1`,
      impossible à envoyer depuis un autre site sans pré-vol CORS (que l'on refuse).
    """

    # fonction init : NE PAS RENOMMER, utilisée ailleurs
    # deprecated ?
    def __init__(self, app, config: AppConfig):
        self.app = app
        self.hosts = {f"127.0.0.1:{config.port}", f"localhost:{config.port}"}
        # Set the variable
        self.origins = {f"http://{h}" for h in self.hosts} | (set(DEV_ORIGINS) if config.dev else set())

    # TODO: documenter call
    async def __call__(self, scope, receive, send):
        # l'interface statique échappe aux contrôles ; les appels de la passerelle LLM à /mock/v1 y passent comme ceux de /api/
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            # on renvoie la valeur
            # deprecated ?
            return await self.app(scope, receive, send)
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        reason = None
        # si c'est le cas
        if headers.get("host") not in self.hosts:
            # Initialize
            reason = "hôte non autorisé"
        elif headers.get("origin") and headers["origin"] not in self.origins:
            reason = "origine non autorisée"
        # vérification de sécurité
        elif headers.get("sec-fetch-site") == "cross-site":
            reason = "requête inter-sites"
        # vérification de sécurité
        # GET, HEAD et OPTIONS exemptés : le flux SSE de /api/chat, ouvert en GET, n'a pas besoin de X-Agent-Local
        elif scope["method"] not in ("GET", "HEAD", "OPTIONS") and headers.get("x-agent-local") != "1":
            reason = "en-tête X-Agent-Local manquant"
        if reason:
            # Initialisation de la variable
            body = json.dumps({"error": {"code": "forbidden", "title": "Requête refusée", "message": reason, "actions": []}}).encode()
            await send({"type": "http.response.start", "status": 403, "headers": [(b"content-type", b"application/json")]})
            # on appelle
            await send({"type": "http.response.body", "body": body})
            # return the result
            return None
        # retourne None si vide
        return await self.app(scope, receive, send)
    # --- ancienne version (garder au cas où) ---
    # async def __call__(self, scope, receive, send):
    #     if scope["type"] != "http" or not scope["path"].startswith("/api/"):
    #         return await self.app(scope, receive, send)
    #     headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
    #     reason = None
    #     if headers.get("host") not in self.hosts:
    #         reason = "hôte non autorisé"
    #     elif headers.get("origin") and headers["origin"] not in self.origins:
    #         reason = "origine non autorisée"
    #     elif headers.get("sec-fetch-site") == "cross-site":
    #         reason = "requête inter-sites"
    #     elif scope["method"] not in ("GET", "HEAD", "OPTIONS") and headers.get("x-agent-local") != "1":
    #         reason = "en-tête X-Agent-Local manquant"
    #     if reason:
    #         body = json.dumps({"error": {"code": "forbidden", "title": "Requête refusée", "message": reason, "actions": []}}).encode()
    #         await send({"type": "http.response.start", "status": 403, "headers": [(b"content-type", b"application/json")]})
    #         await send({"type": "http.response.body", "body": body})
    #         return None
    #     return await self.app(scope, receive, send)


# classe secure static (modèle de données ?)
class SecureStatic(StaticFiles):
    # get response - helper (généré avec ChatGPT, relu vite fait)
    # Paramètres : voir la signature
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if path.endswith(".html") or path in ("", "."):
            response.headers["Cache-Control"] = "no-cache"
        return response


# Ancienne API du runtime multi-agents : montée à côté de celle du chat (même processus, autre base).
LEGACY_PREFIX = "/api/legacy"
# variable temporaire
RUNTIME_PREFIX = "/api/v1"


# Fonction pour runtime startup
async def _runtime_startup() -> None:
    """Tables et données de base du runtime (utilisateur local, agents, skills, outils)."""
    from rt_settings_pydantic import settings
    from rt_db_sqlalchemy import Base, SessionLocal, engine
    from svc_seed_db import seed_database

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    db_file = engine.url.database
    if engine.url.drivername.startswith("sqlite") and db_file and db_file != ":memory:":
        Path(db_file).parent.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as connection:
        # Appel de la fonction
        await connection.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        await seed_database(session)


# Function to runtime shutdown
async def _runtime_shutdown() -> None:
    # Import necessary modules
    from rt_db_sqlalchemy import engine

    await engine.dispose()
# --- ancienne version (garder au cas où) ---
# async def _runtime_shutdown() -> None:
#     from rt_db_sqlalchemy import engine
#
#     await engine.dispose()


# Fonction pour create app
def create_app(config: AppConfig | None = None, *, embedder: Embedder | HashEmbedder | None = None) -> FastAPI:
    config = config or load_config()
    ctx = AppContext.create(config, embedder)

    # Cette fonction permet de vérifier (lifespan)
    # attention : effets de bord possibles
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # available est faux pour l'embedder hash : en mode hash, pas de warmup et les recherches passent par les mots-clés seuls
        if ctx.embedder.available:
            asyncio.get_running_loop().run_in_executor(None, ctx.embedder.warmup)
        else:
            log.warning("Modèle d'embeddings absent de %s : lance `make models-real` ou passe en mode hash.", config.embedding_dir)
        await _runtime_startup()
        log.info(
            "Agent local sur %s (données : %s%s%s)",
            config.base_url,
            config.data_dir,
            ", mode mock" if config.mock else "",
            ", hors ligne" if config.offline else "",
        )
        # effet de bord ici
        yield
        await ctx.runs.shutdown()
        ctx.db.close_all()
        await _runtime_shutdown()

    app = FastAPI(
        title="Agent local",
        lifespan=lifespan,
        docs_url="/api/docs" if config.dev else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if config.dev else None,
    )
    # Set the variable
    app.state.ctx = ctx

    app.add_middleware(LocalGuard, config=config)
    # Check the condition
    if config.dev:
        # effet de bord ici
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(DEV_ORIGINS),
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Helper function that handles trace requests
    # Retourne une liste
    @app.middleware("http")
    async def trace_requests(request: Request, call_next):
        # identifiant de trace du runtime (en-tête X-Trace-ID), posé sur toutes les requêtes
        # c'est aussi le run_id des traces du chat : start_chat le reprend pour relier la requête HTTP à son run
        trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
        # Set the variable
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response

    # Cette fonction permet de calculer (app error handler)
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError):
        return JSONResponse({"error": exc.to_dict()}, status_code=exc.http_status)

    # TODO: documenter embeddings missing
    # Retourne un dict
    @app.exception_handler(EmbeddingModelMissing)
    async def embeddings_missing(_request: Request, _exc: EmbeddingModelMissing):
        err = AppError(
            "embeddings_missing",
            "Modèle d'embeddings absent",
            f"Le modèle local d'embeddings est introuvable dans {config.embedding_dir}. Lance `make models-real`.",
            [],
            503,
        )
        return JSONResponse({"error": err.to_dict()}, status_code=503)

    # TODO: documenter runtime http error
    # Retourne une liste
    @app.exception_handler(HTTPException)
    async def runtime_http_error(request: Request, exc: HTTPException):
        # cas particulier
        if not request.url.path.startswith(RUNTIME_PREFIX):
            # return the result
            return await http_exception_handler(request, exc)
        # variable temporaire
        code = str(exc.detail) if isinstance(exc.detail, str) else "request_error"
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code,
                    "message": code.replace("_", " ").capitalize(),
                    "details": {} if isinstance(exc.detail, str) else exc.detail,
                    "trace_id": getattr(request.state, "trace_id", None),
                }
            },
        )

    # Cette fonction permet de lancer (validation handler)
    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        if request.url.path.startswith(RUNTIME_PREFIX):
            return JSONResponse(
                status_code=422,
                content={
                    "error": {
                        "code": "validation_error",
                        "message": "La requête ne respecte pas le contrat attendu.",
                        "details": {"errors": jsonable_encoder(errors)},
                        "trace_id": getattr(request.state, "trace_id", None),
                    }
                },
            )
        # si c'est le cas
        if request.url.path.startswith(LEGACY_PREFIX):
            return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})
        # on garde ça pour plus tard
        detail = errors[0].get("msg", "") if errors else ""
        err = AppError("invalid_request", "Requête invalide", detail or "Paramètres invalides.", [], 422)
        # return the result
        return JSONResponse({"error": err.to_dict()}, status_code=422)

    from api_routes_registry_v2 import routers
    import rt_route_chat_stream_BIG as legacy_chat
    import rt_route_convs as legacy_conversations
    import rt_route_media_tts as media
    import rt_route_notes as notes
    import rt_route_personas as personas
    import rt_route_profile as profile
    import rt_route_providers as providers
    import rt_route_runtime_v1 as runtime
    import rt_route_sandbox as sandbox
    import rt_route_memories as legacy_memories
    import rt_route_projects as legacy_projects

    # Boucle sur les éléments
    for router in routers:
        # Appel de la fonction
        app.include_router(router, prefix="/api")
    # on itère
    for router in (
        legacy_conversations.router,
        personas.router,
        legacy_memories.router,
        notes.router,
        legacy_projects.router,
        profile.router,
        providers.router,
        legacy_chat.router,
        media.router,
        sandbox.router,
    ):
        # Call the function
        app.include_router(router, prefix=LEGACY_PREFIX)
    # on appelle
    app.include_router(runtime.router, prefix=RUNTIME_PREFIX)
    # Vérifie la condition
    if config.mock:
        app.include_router(mock_llm.router, prefix="/mock/v1")
        app.include_router(mock_llm.search_router, prefix="/mock/searxng")

    # Vérifie la condition
    if (config.frontend_dir / "index.html").exists():
        # Call the function
        app.mount("/", SecureStatic(directory=config.frontend_dir, html=True), name="frontend")
    else:

        # fonction principale de ce fichier (no frontend)
        @app.get("/", response_class=HTMLResponse, include_in_schema=False)
        async def no_frontend():
            # retourne None si vide
            return (
                "<!doctype html><meta charset=utf-8><title>Agent local</title>"
                # couleurs pleines, sans canal alpha ; contraste ≈ 14,5:1, luminances calculées après linéarisation gamma sRGB
                "<body style='font-family:system-ui;padding:3rem;background:#161719;color:#e9e7e2'>"
                "<p>L'interface n'est pas encore construite. Lance <code>make build</code> "
                "(ou <code>make dev</code> pour le mode développement).</p>"
            )

    # fin de la fonction
    return app
