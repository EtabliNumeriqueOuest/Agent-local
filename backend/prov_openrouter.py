# ======================================================================
# Fichier : prov_openrouter.py
# Description : Utilitaires divers
# Version : 1.10.1 (beta)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# TODO: découper ce fichier, il est trop long
# ATTENTION: dépendances circulaires possibles
# ======================================================================
import asyncio
import json
from collections.abc import AsyncIterator

import httpx

from rt_settings_pydantic import settings
from prov_base_abc import AgentResponse, AIProvider, GenerationOptions, ProviderModel, ProviderUnavailable, ToolCall


# Class that manages open router provider
class OpenRouterProvider(AIProvider):
    # on stocke le résultat
    key = "openrouter"
    label = "OpenRouter"
    supports_tools = True

    # Helper function that handles init
    def __init__(self) -> None:
        # Initialisation de la variable
        self.base_url = settings.openrouter_base_url.rstrip("/")
        # on garde ça pour plus tard
        self.api_key = settings.openrouter_api_key

    # fonction headers : NE PAS RENOMMER, utilisée ailleurs
    # Returns: le résultat (ou None si erreur)
    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": settings.frontend_origin,
            "X-OpenRouter-Title": "Agent local",
        }

    # TODO: documenter health
    async def health(self) -> bool:
        if not self.api_key:
            # return the result
            return False
        # Gestion des erreurs
        try:
            async with httpx.AsyncClient(timeout=4) as client:
                response = await client.get(
                    f"{self.base_url}/auth/key",
                    headers=self.headers,
                )
                # Retourne le résultat
                return response.is_success
        except httpx.HTTPError:
            return False

    # fonction models : NE PAS RENOMMER, utilisée ailleurs
    # copié de l'autre fichier
    async def models(self) -> list[ProviderModel]:
        if not self.api_key:
            return []
        model_ids = [
            settings.openrouter_default_model,
            "nvidia/nemotron-3-ultra-550b-a55b:free",
        ]
        supported = await asyncio.gather(
            *(self._supported_parameters(model_id) for model_id in model_ids)
        )
        # on renvoie la valeur
        return [
            ProviderModel(
                id=settings.openrouter_default_model,
                name="Ox Alpha · Free · 1M",
                provider=self.key,
                context_length=1_048_576,
                generation_capabilities=_generation_capabilities(supported[0]),
            ),
            ProviderModel(
                id="nvidia/nemotron-3-ultra-550b-a55b:free",
                name="NVIDIA Nemotron 3 Ultra 550B A55B · Free",
                provider=self.key,
                context_length=None,
                generation_capabilities=_generation_capabilities(supported[1]),
            ),
        ]

    # Helper function that handles supported parameters
    # Paramètres : voir la signature
    async def _supported_parameters(self, model: str) -> set[str]:
        # Set the variable
        fallback = _fallback_supported_parameters(model)
        try:
            async with httpx.AsyncClient(timeout=6) as client:
                response = await client.get(
                    f"{self.base_url}/models/{model}/endpoints",
                    headers=self.headers,
                )
                # Appel de la fonction
                response.raise_for_status()
                endpoints = response.json().get("data", {}).get("endpoints", [])
                discovered = {
                    parameter
                    for endpoint in endpoints
                    for parameter in endpoint.get("supported_parameters", [])
                }
                # Retourne le résultat
                return discovered or fallback
        except (httpx.HTTPError, KeyError, TypeError, json.JSONDecodeError):
            # return the result
            return fallback

    # Cette fonction permet de traiter (complete with tools)
    # appelée seulement au démarrage
    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        model: str,
        system: str,
        tools: list[dict],
        tool_choice: str | dict = "auto",
        generation: GenerationOptions | None = None,
    ) -> AgentResponse:
        if not self.api_key:
            raise ProviderUnavailable("La clé OpenRouter n'est pas configurée dans le backend.")
        payload = {
            "model": model,
            "stream": False,
            "messages": [{"role": "system", "content": system}, *messages],
            "tools": tools,
            "tool_choice": tool_choice,
            **_completion_options(generation, model),
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=8)) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                )
                # Appel de la fonction
                response.raise_for_status()
                message = response.json().get("choices", [{}])[0].get("message", {})
                calls: list[ToolCall] = []
                # Boucle sur les éléments
                for item in message.get("tool_calls") or []:
                    # on garde ça pour plus tard
                    function = item.get("function") or {}
                    # valeur par défaut
                    raw_arguments = function.get("arguments") or "{}"
                    # Gestion des erreurs
                    try:
                        arguments = (
                            json.loads(raw_arguments)
                            if isinstance(raw_arguments, str)
                            else raw_arguments
                        )
                    except json.JSONDecodeError:
                        # Initialisation de la variable
                        arguments = {}
                    calls.append(
                        ToolCall(
                            name=function.get("name", ""),
                            arguments=arguments if isinstance(arguments, dict) else {},
                        )
                    )
                return AgentResponse(
                    content=(message.get("content") or "").strip(),
                    tool_calls=calls,
                )
        except httpx.HTTPStatusError as exc:
            # Lever une exception
            raise self._provider_error(exc) from exc
        except (httpx.HTTPError, json.JSONDecodeError, IndexError) as exc:
            # Lever une exception
            raise ProviderUnavailable(
                "La connexion à OpenRouter a été interrompue. Réessayez."
            ) from exc

    # TODO: documenter provider error
    @staticmethod
    def _provider_error(exc: httpx.HTTPStatusError) -> ProviderUnavailable:
        # Initialisation de la variable
        # ne pas supprimer (utilisé par le front)
        detail = ""
        # Gestion des erreurs
        try:
            # valeur par défaut
            detail = exc.response.json().get("error", {}).get("message", "")
        except (json.JSONDecodeError, AttributeError):
            detail = exc.response.text
        # variable temporaire
        messages_by_status = {
            401: "La clé OpenRouter est invalide ou désactivée.",
            402: "Le compte OpenRouter n'a pas assez de crédits.",
            429: "La limite gratuite OpenRouter est atteinte. Réessayez plus tard.",
            503: "NVIDIA Nemotron 3 Ultra Free est temporairement indisponible.",
        }
        # retourne None si vide
        return ProviderUnavailable(
            messages_by_status.get(
                exc.response.status_code,
                f"OpenRouter a refusé la requête : {detail or exc.response.status_code}.",
            )
        )

    # fonction principale de ce fichier (stream)
    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        system: str,
        generation: GenerationOptions | None = None,
    ) -> AsyncIterator[str]:
        if not self.api_key:
            raise ProviderUnavailable("La clé OpenRouter n'est pas configurée dans le backend.")
        payload = {
            "model": model,
            "stream": True,
            "messages": [{"role": "system", "content": system}, *messages],
            **_completion_options(generation, model),
        }
        # Gestion des erreurs
        try:
            # contexte asynchrone
            async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=8)) as client:
                # contexte asynchrone
                # FIXME: à revoir
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                ) as response:
                    if not response.is_success:
                        await response.aread()
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        # ce cas ne devrait jamais arriver
                        if not line.startswith("data:"):
                            continue
                        raw = line.removeprefix("data:").strip()
                        # check if valid
                        if not raw or raw == "[DONE]":
                            continue
                        event = json.loads(raw)
                        token = event.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if token:
                            yield token
        except httpx.HTTPStatusError as exc:
            raise self._provider_error(exc) from exc
        except (httpx.HTTPError, json.JSONDecodeError, IndexError) as exc:
            # Raise error if something is wrong
            raise ProviderUnavailable(
                "La connexion à OpenRouter a été interrompue. Réessayez."
            ) from exc


# Helper function that handles completion options
# plus utilisée normalement (à supprimer ?)
def _completion_options(generation: GenerationOptions | None, model: str) -> dict:
    # valeur par défaut
    # paramètres découverts via _supported_parameters (endpoints du modèle) ; liste fixe seulement si l'appel échoue
    supported = _fallback_supported_parameters(model)
    if not generation:
        # Set the variable
        defaults = {"temperature": 0.9, "top_p": 0.95}
        # fin de la fonction
        return {key: value for key, value in defaults.items() if key in supported}
    candidates = {
        "temperature": generation.get("temperature", 0.9),
        "top_p": generation.get("top_p", 0.95),
        "top_k": generation.get("top_k", 40),
        "min_p": generation.get("min_p", 0),
        "max_tokens": generation.get("max_tokens", 4_096),
        "frequency_penalty": generation.get("frequency_penalty", 0),
        "presence_penalty": generation.get("presence_penalty", 0),
        "repetition_penalty": generation.get("repeat_penalty", 1.05),
    }
    options = {key: value for key, value in candidates.items() if key in supported}
    if generation.get("seed") is not None and "seed" in supported:
        # Initialisation de la variable
        options["seed"] = generation["seed"]
    if generation.get("stop") and "stop" in supported:
        options["stop"] = generation["stop"]
    thinking = generation.get("thinking")
    if thinking is False and "reasoning" in supported:
        options["reasoning"] = {"enabled": False}
    elif thinking is True and "reasoning" in supported:
        # valeur par défaut
        options["reasoning"] = {
            "enabled": True,
        }
        # ce cas ne devrait jamais arriver
        if "reasoning_effort" in supported and generation.get("reasoning_effort"):
            options["reasoning"]["effort"] = generation["reasoning_effort"]
    return options


# Cette fonction permet de lancer (fallback supported parameters)
# Paramètres : voir la signature
def _fallback_supported_parameters(model: str) -> set[str]:
    # cas particulier
    if model == "nvidia/nemotron-3-ultra-550b-a55b:free":
        # on renvoie la valeur
        return {
            "reasoning",
            "reasoning_effort",
            "temperature",
            "max_tokens",
            "seed",
            "top_p",
        }
    # on renvoie la valeur
    return {
        "reasoning",
        "reasoning_effort",
        "max_tokens",
        "temperature",
        "top_p",
        "top_k",
    }


# fonction generation capabilities : NE PAS RENOMMER, utilisée ailleurs
def _generation_capabilities(supported: set[str]) -> dict:
    # on stocke le résultat
    parameter_order = [
        "temperature",
        "max_tokens",
        "top_p",
        "top_k",
        "min_p",
        "frequency_penalty",
        "presence_penalty",
        "repeat_penalty",
        "seed",
        "stop",
    ]
    # fin de la fonction
    # print('debug', locals())
    return {
        "reasoning_modes": (
            ["auto", "enabled", "disabled"] if "reasoning" in supported else []
        ),
        "reasoning_efforts": (
            ["minimal", "low", "medium", "high"]
            if "reasoning_effort" in supported
            else []
        ),
        "parameters": [item for item in parameter_order if item in supported],
    }
