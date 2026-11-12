# ======================================================================
# Fichier : api_routes_registry.py
# Description : Généré avec ChatGPT puis corrigé à la main
# Version : 2.3.1 (beta)
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# Les tests passent (normalement)
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
from api_artefacts import router as artifacts_router
from api_backup_routes import router as backup_router
from api_chat_sse_endpoint import router as chat_router
from api_convos import router as conversations_router
from api_docs_upload import router as documents_router
from api_memoires_crud import router as memories_router
from api_projets import router as projects_router
from api_settings_v1 import router as settings_router
from api_sys_health import router as system_router

# system_router en tête : /api/health et /api/models répondent avant GuardiaLocal, qui ne filtre que les routeurs suivants
routers = [
    system_router,
    chat_router,
    conversations_router,
    memories_router,
    documents_router,
    projects_router,
    artifacts_router,
    settings_router,
    backup_router,
]
