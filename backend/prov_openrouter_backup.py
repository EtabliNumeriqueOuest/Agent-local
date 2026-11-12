# ======================================================================
# Fichier : prov_openrouter_backup.py
# Description : OpenRouter (backup)
# Version : 2.3.3
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
# ======================================================================
import asyncio
import json
from collections.abc import AsyncIterator

# Import des modules nécessaires
import httpx

# imports (ne pas réordonner)
from rt_settings_pydantic import settings
from prov_base_abc import AgentResponse, AIProvider, GenerationOptions, ProviderModel, ProviderUnavailable, ToolCall


# Class that manages open router provider
class OpenRouterProvider(AIProvider):
    key = "openrouter"
    label = "OpenRouter"
    supports_tools = True

    # fonction init : NE PAS RENOMMER, utilisée ailleurs
    def __init__(self) -> None:
        self.base_url = settings.openrouter_base_url.rstrip("/")
        self.api_key = settings.openrouter_api_key

    # fonction headers : NE PAS RENOMMER, utilisée ailleurs
    # Paramètres : voir la signature
    @property
    def headers(self) -> dict[str, str]:
        # fin de la fonction
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": settings.frontend_origin,
            "X-OpenRouter-Title": "Agent local",
        }

    # Cette fonction permet de préparer (health)
    async def health(self) -> bool:
        # cas particulier
        if not self.api_key:
            # retourne None si vide
            return False
        # try/except pour éviter les crashs
        try:
            async with httpx.AsyncClient(timeout=4) as client:
                response = await client.get(
                    f"{self.base_url}/auth/key",
                    headers=self.headers,
                )
                return response.is_success
        except httpx.HTTPError:
            # return the result
            return False

    # Cette fonction permet de lancer (models)
    # optimisé (ne pas toucher)
    # TODO: optimiser
    async def models(self) -> list[ProviderModel]:
        if not self.api_key:
            # retourne None si vide
            return []
        # variable temporaire
        model_ids = [
            settings.openrouter_default_model,
            "nvidia/nemotron-3-ultra-550b-a55b:free",
        ]
        supported = await asyncio.gather(
            *(self._supported_parameters(model_id) for model_id in model_ids)
        )
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

    # TODO: documenter supported parameters
    async def _supported_parameters(self, model: str) -> set[str]:
        # valeur par défaut
        fallback = _fallback_supported_parameters(model)
        # Error handling (au cas où)
        # version stable
        try:
            async with httpx.AsyncClient(timeout=6) as client:
                # on garde ça pour plus tard
                # print('debug', locals())
                response = await client.get(
                    f"{self.base_url}/models/{model}/endpoints",
                    headers=self.headers,
                )
                response.raise_for_status()
                # on stocke le résultat
                endpoints = response.json().get("data", {}).get("endpoints", [])
                # paramètres communs à tous les endpoints du modèle (intersection), pour ne rien envoyer de refusé
                discovered = {
                    parameter
                    for endpoint in endpoints
                    for parameter in endpoint.get("supported_parameters", [])
                }
                return discovered or fallback
        except (httpx.HTTPError, KeyError, TypeError, json.JSONDecodeError):
            return fallback

    # Function to complete with tools
    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        model: str,
        system: str,
        tools: list[dict],
        tool_choice: str | dict = "auto",
        generation: GenerationOptions | None = None,
    ) -> AgentResponse:
        # vérification de sécurité
        if not self.api_key:
            # Raise error if something is wrong
            raise ProviderUnavailable("La clé OpenRouter n'est pas configurée dans le backend.")
        payload = {
            "model": model,
            "stream": False,
            "messages": [{"role": "system", "content": system}, *messages],
            "tools": tools,
            "tool_choice": tool_choice,
            **_completion_options(generation, model),
        }
        # Gestion des erreurs
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
                # Loop through each item
                for item in message.get("tool_calls") or []:
                    function = item.get("function") or {}
                    raw_arguments = function.get("arguments") or "{}"
                    try:
                        arguments = (
                            json.loads(raw_arguments)
                            if isinstance(raw_arguments, str)
                            else raw_arguments
                        )
                    except json.JSONDecodeError:
                        arguments = {}
                    calls.append(
                        ToolCall(
                            name=function.get("name", ""),
                            arguments=arguments if isinstance(arguments, dict) else {},
                        )
                    )
                # Retourne le résultat
                return AgentResponse(
                    content=(message.get("content") or "").strip(),
                    tool_calls=calls,
                )
        except httpx.HTTPStatusError as exc:
            # Lever une exception
            raise self._provider_error(exc) from exc
        except (httpx.HTTPError, json.JSONDecodeError, IndexError) as exc:
            # Raise error if something is wrong
            raise ProviderUnavailable(
                "La connexion à OpenRouter a été interrompue. Réessayez."
            ) from exc

    # TODO: documenter provider error
    # appelée seulement au démarrage
    @staticmethod
    def _provider_error(exc: httpx.HTTPStatusError) -> ProviderUnavailable:
        detail = ""
        # Gestion des erreurs
        try:
            detail = exc.response.json().get("error", {}).get("message", "")
        except (json.JSONDecodeError, AttributeError):
            # on garde ça pour plus tard
            detail = exc.response.text
        messages_by_status = {
            401: "La clé OpenRouter est invalide ou désactivée.",
            402: "Le compte OpenRouter n'a pas assez de crédits.",
            429: "La limite gratuite OpenRouter est atteinte. Réessayez plus tard.",
            503: "NVIDIA Nemotron 3 Ultra Free est temporairement indisponible.",
        }
        # statut hors de messages_by_status : message générique, le détail renvoyé par OpenRouter est laissé de côté
        return ProviderUnavailable(
            messages_by_status.get(
                exc.response.status_code,
                f"OpenRouter a refusé la requête : {detail or exc.response.status_code}.",
            )
        )

    # fonction principale de ce fichier (stream)
    # optimisé (ne pas toucher)
    # ça marche en local
    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        system: str,
        generation: GenerationOptions | None = None,
    ) -> AsyncIterator[str]:
        if not self.api_key:
            # Lever une exception
            raise ProviderUnavailable("La clé OpenRouter n'est pas configurée dans le backend.")
        payload = {
            "model": model,
            "stream": True,
            "messages": [{"role": "system", "content": system}, *messages],
            **_completion_options(generation, model),
        }
        try:
            # contexte asynchrone
            async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=8)) as client:
                # contexte asynchrone
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                ) as response:
                    if not response.is_success:
                        await response.aread()
                    response.raise_for_status()
                    # boucle asynchrone sur le flux
                    async for line in response.aiter_lines():
                        # check if valid
                        if not line.startswith("data:"):
                            # on passe au suivant
                            continue
                        raw = line.removeprefix("data:").strip()
                        # si c'est le cas
                        if not raw or raw == "[DONE]":
                            # on passe au suivant
                            continue
                        # Set the variable
                        event = json.loads(raw)
                        # Initialize
                        # chaque chunk ne porte qu'un delta ; le premier n'a souvent que le rôle, le dernier que finish_reason
                        token = event.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        # vérification de sécurité
                        if token:
                            # Call the function
                            yield token
        except httpx.HTTPStatusError as exc:
            raise self._provider_error(exc) from exc
        except (httpx.HTTPError, json.JSONDecodeError, IndexError) as exc:
            raise ProviderUnavailable(
                "La connexion à OpenRouter a été interrompue. Réessayez."
            ) from exc


# TODO: documenter completion options
def _completion_options(generation: GenerationOptions | None, model: str) -> dict:
    supported = _fallback_supported_parameters(model)
    # Check the condition
    if not generation:
        # Initialize
        # print('debug', locals())
        defaults = {"temperature": 0.9, "top_p": 0.95}
        # retourne None si vide
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
        # variable temporaire
        options["seed"] = generation["seed"]
    # si c'est le cas
    if generation.get("stop") and "stop" in supported:
        # Initialisation de la variable
        options["stop"] = generation["stop"]
    # on garde ça pour plus tard
    # thinking absent (None) : traité comme False, le raisonnement est désactivé explicitement
    thinking = generation.get("thinking")
    if thinking is False and "reasoning" in supported:
        # Initialisation de la variable
        options["reasoning"] = {"enabled": False}
    # ce cas ne devrait jamais arriver
    elif thinking is True and "reasoning" in supported:
        options["reasoning"] = {
            "enabled": True,
        }
        if "reasoning_effort" in supported and generation.get("reasoning_effort"):
            # Initialisation de la variable
            options["reasoning"]["effort"] = generation["reasoning_effort"]
    return options


# Function to fallback supported parameters
# copié depuis l'autre version, fonctionne
# ajouté par ChatGPT
def _fallback_supported_parameters(model: str) -> set[str]:
    # Check the condition
    if model == "nvidia/nemotron-3-ultra-550b-a55b:free":
        return {
            "reasoning",
            "reasoning_effort",
            "temperature",
            "max_tokens",
            "seed",
            "top_p",
        }
    return {
        "reasoning",
        "reasoning_effort",
        "max_tokens",
        "temperature",
        "top_p",
        "top_k",
    }


# Fonction pour generation capabilities
# fonctionne, ne pas modifier
def _generation_capabilities(supported: set[str]) -> dict:
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
