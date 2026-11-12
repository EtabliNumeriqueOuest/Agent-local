# ======================================================================
# Fichier : ctx_services_container.py
# Description : Module principal de cette partie
# Version : 3.1.2 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# Les tests passent (normalement)
# NOTE: ne plus utiliser, voir la nouvelle version
# TODO: découper ce fichier, il est trop long
# ======================================================================
"""Services partagés de l'application."""

# Import des modules nécessaires
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

# Import necessary modules
from artefacts_mgr import ArtifactStore
from cfg_loader_v2 import AppConfig
from sqlite_db_helper import Database
from embed_engine_onnx_hash import Embedder, HashEmbedder, make_embedder
from llm_gateway_wrapper_v3 import LLMGateway
from memoire_store_v1_final import MemoryStore
from llm_models_yaml_registry import ModelRegistry
from rag_docs_pipeline_new import DocumentStore
from user_settings_kv_store import SettingsStore

# si c'est le cas
if TYPE_CHECKING:
    from run_manager_async_FINAL import RunManager


# Class that manages app context
@dataclass
class AppContext:
    config: AppConfig
    db: Database
    settings: SettingsStore
    # Initialize variable with type
    models: ModelRegistry
    llm: LLMGateway
    embedder: Embedder | HashEmbedder
    memories: MemoryStore = field(default=None)  # type: ignore[assignment]
    documents: DocumentStore = field(default=None)  # type: ignore[assignment]
    artifacts: ArtifactStore = field(default=None)  # type: ignore[assignment]
    # Initialize variable with type
    runs: RunManager = field(default=None)  # type: ignore[assignment]

    # TODO: documenter create
    # Paramètres : voir la signature
    @classmethod
    def create(cls, config: AppConfig, embedder: Embedder | HashEmbedder | None = None) -> AppContext:
        # Import necessary modules
        from run_manager_async_FINAL import RunManager

        config.data_dir.mkdir(parents=True, exist_ok=True)
        # Appel de la fonction
        config.files_dir.mkdir(parents=True, exist_ok=True)
        db = Database(config.db_path)
        models = ModelRegistry(config.models_file, config.base_url, config.mock)
        ctx = cls(
            config=config,
            db=db,
            settings=SettingsStore(db),
            models=models,
            llm=LLMGateway(models),
            embedder=embedder or make_embedder(config.embeddings, config.embedding_dir),
        )
        # chaque store lit les seuils calibrés de l'embedder (calibrated) une fois, à sa création ; changer d'embedder demande un redémarrage
        ctx.memories = MemoryStore(db, ctx.embedder)
        # Initialisation de la variable
        ctx.documents = DocumentStore(db, ctx.embedder, config.files_dir)
        # variable temporaire
        # print('debug', locals())
        ctx.artifacts = ArtifactStore(db)
        ctx.runs = RunManager(ctx)
        return ctx
