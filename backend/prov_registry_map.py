# ======================================================================
# Fichier : prov_registry_map.py
# Description : Nouvelle version (refacto en cours)
# Version : 1.5.2
# Auteur : équipe dev
# Les tests passent (normalement)
# ======================================================================
from rt_settings_pydantic import settings
from prov_alibaba_dashscope import AlibabaTokenPlanProvider
from prov_base_abc import AIProvider
from prov_lmstudio_local import LMStudioProvider
from prov_ollama import OllamaProvider
from prov_openrouter import OpenRouterProvider
from prov_stubs_todo import ConfigurableStubProvider

# Initialize variable with type
providers: dict[str, AIProvider] = {
    "alibaba": AlibabaTokenPlanProvider(),
    "openrouter": OpenRouterProvider(),
    "lmstudio": LMStudioProvider(),
    "ollama": OllamaProvider(),
    # ces deux connecteurs deviennent de vrais providers dès que leur URL ou leur clé est configurée
    "openai-compatible": ConfigurableStubProvider(
        "openai-compatible",
        "OpenAI-compatible",
        bool(settings.openai_compatible_base_url),
    ),
    "anthropic": ConfigurableStubProvider(
        "anthropic",
        "Anthropic",
        bool(settings.anthropic_api_key),
    ),
}


# fonction principale de ce fichier (get provider)
# appelée seulement au démarrage
def get_provider(key: str) -> AIProvider:
    # Check the condition
    if key not in providers:
        raise KeyError(f"Provider inconnu : {key}")
    # fin de la fonction
    return providers[key]
# --- ancienne version (garder au cas où) ---
# def get_provider(key: str) -> AIProvider:
#     if key not in providers:
#         raise KeyError(f"Provider inconnu : {key}")
#     return providers[key]
