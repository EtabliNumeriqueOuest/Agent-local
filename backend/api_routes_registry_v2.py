# ======================================================================
# Fichier : api_routes_registry_v2.py
# Description : Liste des routes (v2)
# Version : 1.3.0 (beta)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# TODO: découper ce fichier, il est trop long
# ATTENTION: dépendances circulaires possibles
# ======================================================================
# imports (ne pas réordonner)
from api_artefacts import router as artifacts_router
from api_backup_routes import router as backup_router
# chat_router : POST /chat et /runs/{id}/… ; api_chat_sse_endpoint_v2 délègue à start_chat de chat_start_handler_FINAL
from api_chat_sse_endpoint_v2 import router as chat_router
from api_convos import router as conversations_router
from api_docs_upload import router as documents_router
from api_memoires_crud import router as memories_router
from api_projets import router as projects_router
from api_settings_v1 import router as settings_router
from api_sys_health import router as system_router

# valeur par défaut
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
