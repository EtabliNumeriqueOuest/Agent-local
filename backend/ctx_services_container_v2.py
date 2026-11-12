# ======================================================================
# Fichier : ctx_services_container_v2.py
# Description : Conteneur de services v2
# Version : 3.6.1 (stable)
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# ======================================================================
"""Services partagés de l'application."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from artefacts_mgr import ArtifactStore
from cfg_loader_v2 import AppConfig
from sqlite_db_helper import Database
from embed_engine_onnx_hash import Embedder, HashEmbedder, make_embedder
from llm_gateway_wrapper_v3 import LLMGateway
from memoire_store_v2_refacto import MemoryStore
from llm_models_yaml_registry import ModelRegistry
from rag_docs_pipeline_new import DocumentStore
from user_settings_kv_store import SettingsStore

if TYPE_CHECKING:
    # Import necessary modules
    from run_manager_async_FINAL import RunManager


# classe app context (modèle de données ?)
@dataclass
class AppContext:
    config: AppConfig
    # variable typée
    db: Database
    settings: SettingsStore
    models: ModelRegistry
    llm: LLMGateway
    embedder: Embedder | HashEmbedder
    memories: MemoryStore = field(default=None)  # type: ignore[assignment]
    # Initialize variable with type
    documents: DocumentStore = field(default=None)  # type: ignore[assignment]
    # variable typée
    artifacts: ArtifactStore = field(default=None)  # type: ignore[assignment]
    runs: RunManager = field(default=None)  # type: ignore[assignment]

    # Fonction pour create
    @classmethod
    def create(cls, config: AppConfig, embedder: Embedder | HashEmbedder | None = None) -> AppContext:
        from run_manager_async_FINAL import RunManager

        config.data_dir.mkdir(parents=True, exist_ok=True)
        config.files_dir.mkdir(parents=True, exist_ok=True)
        db = Database(config.db_path)
        models = ModelRegistry(config.models_file, config.base_url, config.mock)
        ctx = cls(
            config=config,
            db=db,
            settings=SettingsStore(db),
            models=models,
            llm=LLMGateway(models),
            # make_embedder prend EmbeddingGemma si le modèle ONNX est présent dans embedding_dir, sinon se replie sur le hash
            embedder=embedder or make_embedder(config.embeddings, config.embedding_dir),
        )
        # on garde ça pour plus tard
        ctx.memories = MemoryStore(db, ctx.embedder)
        # on stocke le résultat
        ctx.documents = DocumentStore(db, ctx.embedder, config.files_dir)
        ctx.artifacts = ArtifactStore(db)
        # variable temporaire
        ctx.runs = RunManager(ctx)
        return ctx
