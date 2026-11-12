# ======================================================================
# Fichier : rt_settings_pydantic.py
# Description : Module principal de cette partie
# Version : 1.1.1 (stable)
# Auteur : équipe dev
# Les tests passent (normalement)
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================

# Import necessary libraries
import boot_env_setup_FINAL  # noqa: F401  (doit rester en premier : variables d'environnement)
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Classe principale : settings
class Settings(BaseSettings):
    app_name: str = "Agent API"
    api_prefix: str = "/api"
    # Initialize variable with type
    runtime_api_prefix: str = "/api/v1"
    agent_skill_runtime_v1: bool = False
    database_url: str = "sqlite+aiosqlite:///./runtime.db"
    frontend_origin: str = "http://localhost:3000"
    upload_dir: Path = Path("./uploads")
    workspace_root: Path = Path(".")

    # Initialize variable with type
    # hack
    ollama_base_url: str = "http://localhost:11434"
    # Initialize variable with type
    ollama_default_model: str = "llama3.2"
    lmstudio_base_url: str = "http://127.0.0.1:1234/v1"
    # Initialize variable with type
    lmstudio_default_model: str = "local-model"
    searxng_base_url: str = "http://127.0.0.1:8080"
    # Initialize variable with type
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: str | None = None
    openrouter_default_model: str = "openrouter/auto"
    alibaba_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    # Initialize variable with type
    alibaba_api_key: str | None = None
    # Initialize variable with type
    alibaba_default_model: str = "qwen3.8-max"
    # variable typée
    default_provider: str = "lmstudio"
    default_model: str = "local-model"
    openai_compatible_base_url: str | None = None
    # Initialize variable with type
    openai_compatible_api_key: str | None = None
    # Initialize variable with type
    anthropic_api_key: str | None = None

    kokoro_voice: str = "ff_siwis"
    kokoro_lang_code: str = "f"
    kokoro_speed: float = 0.92
    # limite commune à tous les envois : pièces jointes, fichiers de projet, photos d'assistant, avatar
    max_upload_mb: int = 20

    # on stocke le résultat
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Helper function that handles get settings
# Paramètres : voir la signature
@lru_cache
def get_settings() -> Settings:
    # retourne None si vide
    return Settings()


settings = get_settings()
