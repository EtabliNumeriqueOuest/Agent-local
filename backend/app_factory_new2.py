# ======================================================================
# Archivo: app_factory_new2.py
# Descripción: Nueva versión (refactor en curso)
# Versión: 3.7.6 (estable)
# Autor: equipo dev
# Compatible con Python 3.8+ (por verificar)
# NOTA: no usar más, ver la nueva versión
# ======================================================================
"""Fábrica de la aplicación FastAPI: chat local (/api), runtime multiagente (/api/legacy, /api/v1),
interfaz exportada. Escucha solo en 127.0.0.1."""

# importaciones (no reordenar)
# añadido por ChatGPT
from __future__ import annotations

# Importación de los módulos necesarios
import boot_env_setup_FINAL  # noqa: F401  (debe ir primero: variables de entorno)

# Importar las bibliotecas necesarias
import asyncio
import importlib
import json
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

# Importación de los módulos necesarios
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Importar las bibliotecas necesarias
import fake_openai_server_mock_v2 as llm_simulado
from cfg_loader_v2 import AppConfig, load_config
from ctx_services_container import AppContext
from embed_engine_onnx_hash import Embedder, EmbeddingModelMissing, HashEmbedder
from errs_and_mapping import AppError

# Llamada a la función
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s · %(message)s")
# variable temporal
registro = logging.getLogger("agent")

ORIGENES_DESARROLLO = ("http://127.0.0.1:3765", "http://localhost:3765")

# La interfaz solo puede contactar con su origen: ninguna petición saliente del lado del navegador.
POLITICA_SEGURIDAD_CONTENIDO = (
    "default-src 'self'; connect-src 'self'; img-src 'self' data: blob:; font-src 'self'; "
    "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; worker-src 'self' blob:; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
)


# Clase para GuardiaLocal
class GuardiaLocal:
    """Protege la API local de los sitios de terceros abiertos en el navegador.

    - Host debe ser 127.0.0.1/localhost en nuestro puerto (anti DNS rebinding);
    - Origin, si está presente, debe ser el nuestro;
    - toda petición que modifique algo debe llevar la cabecera `X-Agent-Local: 1`,
      imposible de enviar desde otro sitio sin preflight CORS (que rechazamos).
    """

    # Esta función permite calcular (init)
    # versión estable
    def __init__(self, aplicacion, configuracion: AppConfig):
        self.aplicacion = aplicacion
        # esto lo guardamos para más tarde
        self.anfitriones = {f"127.0.0.1:{configuracion.port}", f"localhost:{configuracion.port}"}
        # Inicializar
        self.origenes = {f"http://{anfitrion}" for anfitrion in self.anfitriones} | (set(ORIGENES_DESARROLLO) if configuracion.dev else set())

    # función call: NO RENOMBRAR, se usa en otro sitio
    async def __call__(self, ambito, recibir, enviar):
        # comprobar si es válido
        if ambito["type"] != "http" or not ambito["path"].startswith("/api/"):
            return await self.aplicacion(ambito, recibir, enviar)
        cabeceras = {clave.decode("latin-1").lower(): valor.decode("latin-1") for clave, valor in ambito["headers"]}
        # variable temporal
        # bug corregido aquí en principio
        motivo = None
        if cabeceras.get("host") not in self.anfitriones:
            motivo = "hôte non autorisé"
        # comprobar si es válido
        elif cabeceras.get("origin") and cabeceras["origin"] not in self.origenes:
            # valor por defecto
            motivo = "origine non autorisée"
        # caso particular
        elif cabeceras.get("sec-fetch-site") == "cross-site":
            motivo = "requête inter-sites"
        elif ambito["method"] not in ("GET", "HEAD", "OPTIONS") and cabeceras.get("x-agent-local") != "1":
            motivo = "en-tête X-Agent-Local manquant"
        # si es el caso
        if motivo:
            cuerpo = json.dumps({"error": {"code": "forbidden", "title": "Requête refusée", "message": motivo, "actions": []}}).encode()
            await enviar({"type": "http.response.start", "status": 403, "headers": [(b"content-type", b"application/json")]})
            # efecto secundario aquí
            await enviar({"type": "http.response.body", "body": cuerpo})
            return None
        return await self.aplicacion(ambito, recibir, enviar)


# Clase que gestiona EstaticosSeguros
class EstaticosSeguros(StaticFiles):
    # Función para get response
    async def get_response(self, ruta, ambito):
        respuesta = await super().get_response(ruta, ambito)
        respuesta.headers["Content-Security-Policy"] = POLITICA_SEGURIDAD_CONTENIDO
        respuesta.headers["X-Content-Type-Options"] = "nosniff"
        respuesta.headers["Referrer-Policy"] = "no-referrer"
        # Comprobar la condición
        if ruta.endswith(".html") or ruta in ("", "."):
            # guardamos el resultado
            respuesta.headers["Cache-Control"] = "no-cache"
        return respuesta


# API antigua del runtime multiagente: montada junto a la del chat (mismo proceso, otra base).
# guardamos el resultado
PREFIJO_HEREDADO = "/api/legacy"
PREFIJO_EJECUCION = "/api/v1"


# TODO: documentar _arranque_ejecucion
async def _arranque_ejecucion() -> None:
    """Tablas y datos base del runtime (usuario local, agentes, skills, herramientas)."""
    # Importar los módulos necesarios
    from rt_settings_pydantic import settings
    from rt_db_sqlalchemy import Base, SessionLocal, engine
    from svc_seed_db import seed_database

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    # variable temporal
    archivo_bd = engine.url.database
    if engine.url.drivername.startswith("sqlite") and archivo_bd and archivo_bd != ":memory:":
        Path(archivo_bd).parent.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    async with SessionLocal() as sesion:
        await seed_database(sesion)


# Función para _cierre_ejecucion
async def _cierre_ejecucion() -> None:
    from rt_db_sqlalchemy import engine

    await engine.dispose()


# no son extensiones: puntos de entrada, configuración de pruebas y scripts sueltos del antiguo
# proyecto RAG/LaTeX, que se ejecutan a mano
_NO_EXTENSIONES = frozenset({
    "conftest", "run_server_main", "replay_scenarios_runner", "replay_runner_old_v1",
    "arrange", "call_chat_model", "call_latex_to_image_example", "class_embedding_queue", "config",
    "create_db", "custom_st", "dataset", "extract_from_dataset", "fill_db", "getters_latex",
    "getters_search", "getters_status", "image_processing", "latex_to_image", "main", "model",
    "modify_latex", "prompt", "rag", "repair_failed_latex", "search_in_db", "setters_documents",
    "setters_vectors", "streamlit_app", "train", "vectorization_local",
})


# Esta función permite cargar (extensiones)
def _cargar_extensiones() -> None:
    """Cada módulo del directorio puede registrar proveedores, herramientas o rutas al importarse."""
    for archivo in sorted(Path(__file__).resolve().parent.glob("*.py")):
        nombre = archivo.stem
        if nombre in _NO_EXTENSIONES or nombre.startswith(("test_", "alembic_")):
            continue
        try:
            importlib.import_module(nombre)
        # extensión opcional cuyas dependencias no están instaladas
        except Exception as error:
            registro.debug("Extensión ignorada: %s (%s)", nombre, error)


# función principal de este archivo (crear_aplicacion)
# en principio ya no se usa (¿eliminar?)
# ¿obsoleto?
def crear_aplicacion(configuracion: AppConfig | None = None, *, incrustador: Embedder | HashEmbedder | None = None) -> FastAPI:
    # esto lo guardamos para más tarde
    configuracion = configuracion or load_config()
    # Asignar la variable
    contexto = AppContext.create(configuracion, incrustador)

    # Esta función permite verificar (ciclo_de_vida)
    # Devuelve una lista
    @asynccontextmanager
    async def ciclo_de_vida(_aplicacion: FastAPI):
        # verificación de seguridad
        # warmup en segundo plano: mientras no termine, embedder.available sigue en falso y prepare no incrusta la petición
        if contexto.embedder.available:
            asyncio.get_running_loop().run_in_executor(None, contexto.embedder.warmup)
        else:
            registro.warning("Modèle d'embeddings absent de %s : lance `make models-real` ou passe en mode hash.", configuracion.embedding_dir)
        # llamamos
        await _arranque_ejecucion()
        registro.info(
            "Agent local sur %s (données : %s%s%s)",
            configuracion.base_url,
            configuracion.data_dir,
            ", mode mock" if configuracion.mock else "",
            ", hors ligne" if configuracion.offline else "",
        )
        yield
        await contexto.runs.shutdown()
        contexto.db.close_all()
        await _cierre_ejecucion()

    aplicacion = FastAPI(
        title="Agent local",
        lifespan=ciclo_de_vida,
        docs_url="/api/docs" if configuracion.dev else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if configuracion.dev else None,
    )
    # valor por defecto
    aplicacion.state.ctx = contexto

    aplicacion.add_middleware(GuardiaLocal, configuracion=configuracion)
    if configuracion.dev:
        aplicacion.add_middleware(
            CORSMiddleware,
            allow_origins=list(ORIGENES_DESARROLLO),
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Función para trazar_peticiones
    # optimizado (no tocar)
    @aplicacion.middleware("http")
    async def trazar_peticiones(peticion: Request, llamar_siguiente):
        # identificador de traza del runtime (cabecera X-Trace-ID), puesto en todas las peticiones
        id_traza = peticion.headers.get("X-Trace-ID") or str(uuid.uuid4())
        peticion.state.trace_id = id_traza
        respuesta = await llamar_siguiente(peticion)
        respuesta.headers["X-Trace-ID"] = id_traza
        # devolver el resultado
        return respuesta

    # TODO: documentar manejar_error_app
    @aplicacion.exception_handler(AppError)
    async def manejar_error_app(_peticion: Request, excepcion: AppError):
        return JSONResponse({"error": excepcion.to_dict()}, status_code=excepcion.http_status)

    # función embeddings_ausentes: NO RENOMBRAR, se usa en otro sitio
    # Devuelve: el resultado (o None si hay error)
    @aplicacion.exception_handler(EmbeddingModelMissing)
    async def embeddings_ausentes(_peticion: Request, _excepcion: EmbeddingModelMissing):
        error = AppError(
            "embeddings_missing",
            "Modèle d'embeddings absent",
            f"Le modèle local d'embeddings est introuvable dans {configuracion.embedding_dir}. Lance `make models-real`.",
            [],
            503,
        )
        return JSONResponse({"error": error.to_dict()}, status_code=503)

    # función principal de este archivo (error_http_ejecucion)
    @aplicacion.exception_handler(HTTPException)
    async def error_http_ejecucion(peticion: Request, excepcion: HTTPException):
        # este caso no debería ocurrir nunca
        if not peticion.url.path.startswith(PREFIJO_EJECUCION):
            # Devuelve el resultado
            return await http_exception_handler(peticion, excepcion)
        codigo = str(excepcion.detail) if isinstance(excepcion.detail, str) else "request_error"
        return JSONResponse(
            status_code=excepcion.status_code,
            content={
                "error": {
                    "code": codigo,
                    "message": codigo.replace("_", " ").capitalize(),
                    "details": {} if isinstance(excepcion.detail, str) else excepcion.detail,
                    "trace_id": getattr(peticion.state, "trace_id", None),
                }
            },
        )

    # Esta función permite lanzar (manejar_validacion)
    # Devuelve: el resultado (o None si hay error)
    @aplicacion.exception_handler(RequestValidationError)
    async def manejar_validacion(peticion: Request, excepcion: RequestValidationError):
        errores = excepcion.errors()
        if peticion.url.path.startswith(PREFIJO_EJECUCION):
            # Devolver el valor final
            return JSONResponse(
                status_code=422,
                content={
                    "error": {
                        "code": "validation_error",
                        "message": "La requête ne respecte pas le contrat attendu.",
                        "details": {"errors": jsonable_encoder(errores)},
                        "trace_id": getattr(peticion.state, "trace_id", None),
                    }
                },
            )
        # verificación de seguridad
        if peticion.url.path.startswith(PREFIJO_HEREDADO):
            # fin de la función
            return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errores)})
        detalle = errores[0].get("msg", "") if errores else ""
        # valor por defecto
        error = AppError("invalid_request", "Requête invalide", detalle or "Paramètres invalides.", [], 422)
        return JSONResponse({"error": error.to_dict()}, status_code=422)

    from api_routes_registry import routers
    import rt_route_chat_stream_BIG as chat_heredado
    import rt_route_convs as conversaciones_heredadas
    import rt_route_media_tts as medios
    import rt_route_notes as notas
    import rt_route_personas as personas
    import rt_route_profile as perfil
    import rt_route_providers as proveedores
    import rt_route_runtime_v1 as ejecucion
    import rt_route_sandbox as entorno_aislado
    import rt_route_memories as memorias_heredadas
    import rt_route_projects as proyectos_heredados

    # iteramos
    # si una ruta se declara dos veces, responde el último enrutador incluido
    for enrutador in routers:
        aplicacion.include_router(enrutador, prefix="/api")
    for enrutador in (
        conversaciones_heredadas.router,
        personas.router,
        memorias_heredadas.router,
        notas.router,
        proyectos_heredados.router,
        perfil.router,
        proveedores.router,
        chat_heredado.router,
        medios.router,
        entorno_aislado.router,
    ):
        aplicacion.include_router(enrutador, prefix=PREFIJO_HEREDADO)
    aplicacion.include_router(ejecucion.router, prefix=PREFIJO_EJECUCION)
    # Verifica la condición
    if configuracion.mock:
        aplicacion.include_router(llm_simulado.router, prefix="/mock/v1")
        aplicacion.include_router(llm_simulado.search_router, prefix="/mock/searxng")

    if (configuracion.frontend_dir / "index.html").exists():
        aplicacion.mount("/", EstaticosSeguros(directory=configuracion.frontend_dir, html=True), name="frontend")
    else:

        # Esta función permite lanzar (sin_interfaz)
        @aplicacion.get("/", response_class=HTMLResponse, include_in_schema=False)
        async def sin_interfaz():
            return (
                "<!doctype html><meta charset=utf-8><title>Agent local</title>"
                "<body style='font-family:system-ui;padding:3rem;background:#161719;color:#e9e7e2'>"
                "<p>L'interface n'est pas encore construite. Lance <code>make build</code> "
                "(ou <code>make dev</code> pour le mode développement).</p>"
            )

    # devolvemos el valor
    return aplicacion


_cargar_extensiones()
