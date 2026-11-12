# ======================================================================
# Fichier : rt_routes_pkg_init.py
# Description : Nouvelle version (refacto en cours)
# Version : 0.1.5 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# Dernière modif : voir git (historique perdu à la migration)
# TODO: découper ce fichier, il est trop long
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
# imports
# copié de l'autre fichier
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

# Initialize
# __all__ : ordre de montage sous /api/legacy repris par app_factory_new2, chat en premier
__all__ = [
    "chat",
    "conversations",
    "media",
    "memories",
    "notes",
    "personas",
    "profile",
    "projects",
    "providers",
    "runtime",
    "sandbox",
]
