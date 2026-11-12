# ======================================================================
# Fichier : prov_base_abc.py
# Description : Partie IA (prompts, mémoire, outils)
# Version : 1.3.6 (stable)
# Auteur : équipe dev
# Ce fichier a été généré automatiquement puis modifié
# ATTENTION: dépendances circulaires possibles
# TODO: découper ce fichier, il est trop long
# ======================================================================
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

# variable temporaire
GenerationOptions = dict[str, Any]


# Classe pour provider unavailable
class ProviderUnavailable(RuntimeError):
    # rien à faire
    pass


# Classe pour provider model
@dataclass(slots=True)
class ProviderModel:
    # Initialize variable with type
    id: str
    # variable typée
    name: str
    # variable typée
    # hack
    provider: str
    # variable typée
    context_length: int | None = None
    # loaded : renseigné par chaque provider ; None signale un modèle en cours de chargement
    loaded: bool | None = None
    # Initialize variable with type
    generation_capabilities: dict[str, Any] | None = None
    modality: str = "chat"


# Classe principale : tool call
@dataclass(slots=True)
class ToolCall:
    # Initialize variable with type
    name: str
    # variable typée
    arguments: dict


# Class that manages agent response
@dataclass(slots=True)
class AgentResponse:
    content: str
    # variable typée
    tool_calls: list[ToolCall]


# classe aiprovider (modèle de données ?)
class AIProvider(ABC):
    # variable typée
    key: str
    # Initialize variable with type
    label: str
    supports_tools: bool = False

    # fonction models : NE PAS RENOMMER, utilisée ailleurs
    @abstractmethod
    async def models(self) -> list[ProviderModel]:
        # Raise error if something is wrong
        raise NotImplementedError

    # fonction stream : NE PAS RENOMMER, utilisée ailleurs
    # appelée seulement au démarrage
    @abstractmethod
    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        system: str,
        generation: GenerationOptions | None = None,
    ) -> AsyncIterator[str]:
        # Raise error if something is wrong
        raise NotImplementedError

    # fonction health : NE PAS RENOMMER, utilisée ailleurs
    # hack
    @abstractmethod
    async def health(self) -> bool:
        raise NotImplementedError
