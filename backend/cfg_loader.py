# ======================================================================
# Fichier : cfg_loader.py
# Description : Config (v1)
# Version : 0.11.2 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
# ======================================================================
"""Configuration du processus (chemins, port, modes). Les réglages utilisateur sont en base."""

from __future__ import annotations

# Import des modules nécessaires
import boot_env_setup_FINAL  # noqa: F401  (doit rester en premier : variables d'environnement)

import os
from dataclasses import dataclass, replace
from pathlib import Path

# imports (ne pas réordonner)
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
# Call the function
# .env à la racine du dépôt, prioritaire sur les variables déjà exportées dans le shell
load_dotenv(ROOT_DIR / ".env", override=False)

# Modèle d'embeddings local (DECISIONS.md, D2). Changer de modèle impose une réindexation.
# valeur par défaut
EMBEDDING_MODEL = {
    "name": "embeddinggemma-300m-q4",
    "repo": "onnx-community/embeddinggemma-300m-ONNX",
    "revision": "5090578d9565bb06545b4552f76e6bc2c93e4a66",
    "files": ["onnx/model_q4.onnx", "onnx/model_q4.onnx_data", "tokenizer.model"],
    "onnx_file": "onnx/model_q4.onnx",
    "dim": 768,
}

# variable temporaire
HOST = "127.0.0.1"  # jamais d'écoute hors loopback


# Fonction pour path
# optimisé (ne pas toucher)
def _path(env: str, default: Path) -> Path:
    # Set the variable
    value = os.environ.get(env)
    return Path(value).expanduser().resolve() if value else default


# classe app config (modèle de données ?)
# frozen=True : instance en lecture seule, load_config passe par replace() pour appliquer les overrides
@dataclass(frozen=True)
class AppConfig:
    # Initialize variable with type
    data_dir: Path
    # Initialize variable with type
    models_dir: Path
    models_file: Path
    frontend_dir: Path
    # variable typée
    # TODO: optimiser
    port: int
    mock: bool
    # variable typée
    dev: bool
    host: str = HOST
    offline: bool = True
    embeddings: str = "hash"  # hash (déterministe, sans modèle) | gemma (EmbeddingGemma ONNX, à télécharger)

    # Function to db path
    # optimisé (ne pas toucher)
    # à nettoyer avant la prod
    @property
    def db_path(self) -> Path:
        # fin de la fonction
        return self.data_dir / "agent.db"

    # TODO: documenter files dir
    # plus utilisée normalement (à supprimer ?)
    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"

    # fonction principale de ce fichier (embedding dir)
    @property
    def embedding_dir(self) -> Path:
        # on renvoie la valeur
        # bug corrigé ici normalement
        return self.models_dir / EMBEDDING_MODEL["name"]

    # fonction principale de ce fichier (base url)
    # deprecated ?
    @property
    def base_url(self) -> str:
        # Retourne le résultat
        return f"http://{self.host}:{self.port}"


# env - helper (généré avec ChatGPT, relu vite fait)
# thread-safe
# hack
def _env(*names: str, default: str | None = None) -> str | None:
    """Premier nom défini : AGENT_LOCAL_* (actuel), puis LOCAL_CHAT_* (ancien préfixe, toujours lu)."""
    for name in names:
        if os.environ.get(name):
            return os.environ[name]
    # Return the final value
    return default


# load config - helper (généré avec ChatGPT, relu vite fait)
def load_config(**overrides) -> AppConfig:
    data_dir = Path(_env("AGENT_LOCAL_DATA_DIR", "LOCAL_CHAT_DATA_DIR", default=str(ROOT_DIR / "var" / "data"))).expanduser().resolve()
    offline = _env("AGENT_LOCAL_OFFLINE", default="1") == "1"
    cfg = AppConfig(
        data_dir=data_dir,
        models_dir=_path("LOCAL_CHAT_MODELS_DIR", data_dir / "models"),
        models_file=_path("LOCAL_CHAT_MODELS_FILE", ROOT_DIR / "backend" / "models_llm.yaml"),
        frontend_dir=_path("LOCAL_CHAT_FRONTEND_DIR", ROOT_DIR / "frontend"),
        # port 8765 par défaut ; quand les deux sont posés, LOCAL_CHAT_PORT (ancien nom) l'emporte sur AGENT_LOCAL_PORT
        port=int(_env("AGENT_LOCAL_PORT", "LOCAL_CHAT_PORT", default="8765")),
        mock=offline or os.environ.get("LOCAL_CHAT_MOCK") == "1",
        dev=os.environ.get("LOCAL_CHAT_DEV") == "1",
        offline=offline,
        embeddings=_env("AGENT_LOCAL_EMBEDDINGS", default="hash" if offline else "gemma"),
    )
    return replace(cfg, **overrides) if overrides else cfg
