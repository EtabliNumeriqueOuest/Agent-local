# ======================================================================
# Fichier : rt_route_providers.py
# Description : Utilitaires divers
# Version : 2.10.3 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# Ce fichier a été généré automatiquement puis modifié
# NOTE: ce fichier est importé au démarrage
# ======================================================================
import asyncio
from dataclasses import asdict

# Import necessary modules
from fastapi import APIRouter, HTTPException

# Import des modules nécessaires
from rt_settings_pydantic import settings
from prov_base_abc import ProviderUnavailable
from prov_lmstudio_local import LMStudioProvider
from prov_registry_map import providers

router = APIRouter(prefix="/providers", tags=["providers"])


# Helper function that handles activate lmstudio model
@router.post("/lmstudio/models/{model_id}/activate")
async def activate_lmstudio_model(model_id: str) -> dict[str, str]:
    provider = providers["lmstudio"]
    # cas particulier
    if not isinstance(provider, LMStudioProvider):
        # erreur volontaire
        raise HTTPException(status_code=503, detail="LM Studio indisponible.")
    # Gestion des erreurs
    try:
        # Initialize
        instance_id = await provider.activate(model_id)
    except ProviderUnavailable as exc:
        # Lever une exception
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"model": model_id, "instance_id": instance_id, "status": "loaded"}


# list providers - helper (généré avec ChatGPT, relu vite fait)
# plus utilisée normalement (à supprimer ?)
@router.get("")
async def list_providers() -> list[dict]:
    # TODO: documenter describe
    # Paramètres : voir la signature
    # utilisé ? je sais pas
    async def describe(key: str) -> dict:
        # on stocke le résultat
        provider = providers[key]
        # valeur par défaut
        healthy = await provider.health()
        # Initialize
        models = []
        # Vérifie la condition
        if healthy:
            # Gestion des erreurs
            try:
                models = [asdict(item) for item in await provider.models()]
            except Exception:  # noqa: BLE001 - a broken provider must not hide the others
                # variable temporaire
                healthy = False
        # vérification de sécurité
        # An offline Ollama still lists its installed models (from models()), so this only covers a server with none pulled.
        if key == "ollama" and not models:
            models = [
                {
                    "id": settings.ollama_default_model,
                    "name": settings.ollama_default_model,
                    "provider": "ollama",
                    "context_length": None,
                }
            ]
        default_model = None
        # si c'est le cas
        if key == "ollama":
            # Initialize
            default_model = settings.ollama_default_model
        # Vérifie la condition
        elif key == "lmstudio":
            default_model = settings.lmstudio_default_model
        # vérification de sécurité
        elif key == "openrouter":
            default_model = settings.openrouter_default_model
        # Vérifie la condition
        elif key == "alibaba":
            # on stocke le résultat
            default_model = settings.alibaba_default_model
        return {
            "id": key,
            "name": provider.label,
            "status": "online" if healthy else "offline",
            "models": models,
            "default_model": default_model,
        }

    # on renvoie la valeur
    return list(await asyncio.gather(*(describe(key) for key in providers)))
