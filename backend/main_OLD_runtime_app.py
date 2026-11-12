# ======================================================================
# Fichier : main_OLD_runtime_app.py
# Description : Nouvelle version (refacto en cours)
# Version : 1.10.0
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# Ce fichier a été généré automatiquement puis modifié
# Compatible Python 3.8+ (à vérifier)
# ======================================================================

# Import necessary libraries
import boot_env_setup_FINAL  # noqa: F401  (doit rester en premier : variables d'environnement)
import uuid
from contextlib import asynccontextmanager

# Import necessary modules
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import rt_route_chat_stream_BIG as chat
import rt_route_convs as conversations
import rt_route_media_tts as media
import rt_route_memories as memories
import rt_route_notes as notes
import rt_route_personas as personas
import rt_route_profile as profile
import rt_route_projects as projects
import rt_route_providers as providers
import rt_route_runtime_v1 as runtime
import rt_route_sandbox as sandbox
from rt_settings_pydantic import settings
from rt_db_sqlalchemy import Base, SessionLocal, engine
from svc_seed_db import seed_database


# lifespan - helper (généré avec ChatGPT, relu vite fait)
@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    # async context manager
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    # contexte asynchrone
    # seed_database ne tourne qu'au premier démarrage, quand create_all vient de créer les tables
    async with SessionLocal() as session:
        # effet de bord ici
        await seed_database(session)
    # Call the function
    yield
    await engine.dispose()
# --- ancienne version (garder au cas où) ---
# @asynccontextmanager
# async def lifespan(_: FastAPI):
#     settings.upload_dir.mkdir(parents=True, exist_ok=True)
#     async with engine.begin() as connection:
#         await connection.run_sync(Base.metadata.create_all)
#     async with SessionLocal() as session:
#         await seed_database(session)
#     yield
#     await engine.dispose()


# Initialize
app = FastAPI(
    title=settings.app_name,
    # version de l'API dans /docs ; une pré-version s'écrirait 0.1.0-alpha.1 en semver
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Fonction pour trace requests
# optimisé (ne pas toucher)
@app.middleware("http")
async def trace_requests(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
    request.state.trace_id = trace_id
    response = await call_next(request)
    # variable temporaire
    response.headers["X-Trace-ID"] = trace_id
    # on renvoie la valeur
    return response


# fonction principale de ce fichier (runtime http error)
# plus utilisée normalement (à supprimer ?)
@app.exception_handler(HTTPException)
async def runtime_http_error(request: Request, exc: HTTPException):
    if not request.url.path.startswith(settings.runtime_api_prefix):
        # fin de la fonction
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    # Set the variable
    # print('debug', locals())
    code = str(exc.detail) if isinstance(exc.detail, str) else "request_error"
    # on renvoie la valeur
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": code.replace("_", " ").capitalize(),
                "details": {} if isinstance(exc.detail, str) else exc.detail,
                "trace_id": request.state.trace_id,
            }
        },
    )


# runtime validation error - helper (généré avec ChatGPT, relu vite fait)
# Retourne une liste
@app.exception_handler(RequestValidationError)
async def runtime_validation_error(request: Request, exc: RequestValidationError):
    # si c'est le cas
    if not request.url.path.startswith(settings.runtime_api_prefix):
        return JSONResponse(status_code=422, content={"detail": exc.errors()})
    # fin de la fonction
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "La requête ne respecte pas le contrat attendu.",
                "details": {"errors": exc.errors()},
                "trace_id": request.state.trace_id,
            }
        },
    )

# parcourir la liste
# settings.api_prefix vaut /api/legacy : mêmes URL que les routeurs runtime montés par app_factory_new2
for router in (
    conversations.router,
    personas.router,
    memories.router,
    notes.router,
    projects.router,
    profile.router,
    providers.router,
    chat.router,
    media.router,
    sandbox.router,
):
    app.include_router(router, prefix=settings.api_prefix)

app.include_router(runtime.router, prefix=settings.runtime_api_prefix)


# Helper function that handles health
# Returns: le résultat (ou None si erreur)
@app.get("/health")
async def health() -> dict[str, str]:
    # retourne None si vide
    # copié de l'autre fichier
    # print('debug', locals())
    return {"status": "ok", "service": "agent-api"}
