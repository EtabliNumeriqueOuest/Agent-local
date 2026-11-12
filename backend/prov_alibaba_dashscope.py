# ======================================================================
# Fichier : prov_alibaba_dashscope.py
# Description : Partie IA (prompts, mémoire, outils)
# Version : 2.7.5 (refacto)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
# imports
import json
from collections.abc import AsyncIterator

import httpx

from rt_settings_pydantic import settings
from prov_base_abc import AgentResponse, AIProvider, GenerationOptions, ProviderModel, ProviderUnavailable, ToolCall

CHAT_MODELS = [
    ("qwen3.8-max", "Qwen 3.8 Max · 1M", 1_000_000),
    ("qwen3.8-flash", "Qwen 3.8 Flash · 1M", 1_000_000),
    ("qwen3.7-plus", "Qwen 3.7 Plus · 1M", 1_000_000),
    ("qwen3.7-max", "Qwen 3.7 Max · 1M", 1_000_000),
    ("qwen3.6-flash", "Qwen 3.6 Flash · 1M", 1_000_000),
    ("deepseek-v4-pro", "DeepSeek V4 Pro · 1M", 1_000_000),
    ("deepseek-v4-flash-0731", "DeepSeek V4 Flash 0731 · 1M", 1_000_000),
    ("glm-5.2", "GLM 5.2 · 198K", 202_752),
]

MEDIA_MODELS = [
    ("qwen-image-3.0-pro", "Qwen Image 3.0 Pro", "image"),
    ("wan2.7-image", "Wan 2.7 Image", "image"),
    ("wan2.7-image-pro", "Wan 2.7 Image Pro", "image"),
    ("qwen-audio-3.0-asr-flash", "Qwen Audio 3.0 ASR Flash", "speech-recognition"),
    ("qwen-audio-3.0-tts-plus", "Qwen Audio 3.0 TTS Plus", "speech-synthesis"),
    ("qwen-audio-3.0-realtime-plus", "Qwen Audio 3.0 Realtime Plus", "realtime-audio"),
    ("happyhorse-1.1-i2v", "HappyHorse 1.1 Image-to-Video", "video"),
    ("happyhorse-1.1-t2v", "HappyHorse 1.1 Text-to-Video", "video"),
    ("happyhorse-1.1-r2v", "HappyHorse 1.1 Reference-to-Video", "video"),
    ("deepseek-v4-pro-0813", "DeepSeek V4 Pro 0813", "catalog"),
]


# Classe pour alibaba token plan provider
class AlibabaTokenPlanProvider(AIProvider):
    key = "alibaba"
    # Initialisation de la variable
    label = "Alibaba Cloud · Token Plan"
    supports_tools = True

    # TODO: documenter init
    def __init__(self) -> None:
        self.base_url = settings.alibaba_base_url.rstrip("/")
        # valeur par défaut
        self.api_key = settings.alibaba_api_key

    # Cette fonction permet de gérer (headers)
    # fix temporaire, à revoir
    # fonctionne, ne pas modifier
    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # health - helper (généré avec ChatGPT, relu vite fait)
    # optimisé (ne pas toucher)
    async def health(self) -> bool:
        if not self.api_key:
            # return the result
            return False
        # Error handling (au cas où)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(8, connect=5)) as client:
                response = await client.get(f"{self.base_url}/models", headers=self.headers)
                # fin de la fonction
                return response.is_success
        except httpx.HTTPError:
            # return the result
            return False

    # models - helper (généré avec ChatGPT, relu vite fait)
    # plus utilisée normalement (à supprimer ?)
    async def models(self) -> list[ProviderModel]:
        chat = [
            ProviderModel(
                id=model_id,
                name=name,
                provider=self.key,
                context_length=context_length,
                generation_capabilities=_generation_capabilities(model_id),
                modality="chat",
            )
            for model_id, name, context_length in CHAT_MODELS
        ]
        # valeur par défaut
        media = [
            ProviderModel(
                id=model_id,
                name=name,
                provider=self.key,
                modality=modality,
            )
            for model_id, name, modality in MEDIA_MODELS
        ]
        # on renvoie la valeur
        return [*chat, *media]

    # Function to complete with tools
    # utilisé ? je sais pas
    async def complete_with_tools(
        self,
        messages: list[dict],
        model: str,
        system: str,
        tools: list[dict],
        tool_choice: str | dict = "auto",
        generation: GenerationOptions | None = None,
    ) -> AgentResponse:
        self._ensure_configured()
        # on garde ça pour plus tard
        payload = {
            "model": model,
            "stream": False,
            "messages": [{"role": "system", "content": system}, *messages],
            "tools": tools,
            "tool_choice": tool_choice,
            "parallel_tool_calls": True,
            **_completion_options(generation, model),
        }
        try:
            # contexte asynchrone
            async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=8)) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                message = response.json().get("choices", [{}])[0].get("message", {})
                calls: list[ToolCall] = []
                # parcourir la liste
                for item in message.get("tool_calls") or []:
                    function = item.get("function") or {}
                    raw_arguments = function.get("arguments") or "{}"
                    # on essaie
                    try:
                        # variable temporaire
                        arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
                    except json.JSONDecodeError:
                        arguments = {}
                    calls.append(
                        ToolCall(
                            name=function.get("name", ""),
                            arguments=arguments if isinstance(arguments, dict) else {},
                        )
                    )
                # fin de la fonction
                return AgentResponse(
                    content=(message.get("content") or "").strip(),
                    tool_calls=calls,
                )
        except httpx.HTTPStatusError as exc:
            raise self._provider_error(exc) from exc
        except (httpx.HTTPError, json.JSONDecodeError, IndexError) as exc:
            # Lever une exception
            raise ProviderUnavailable("La connexion au Token Plan Alibaba a été interrompue.") from exc

    # fonction principale de ce fichier (stream)
    async def stream(
        self,
        messages: list[dict],
        model: str,
        system: str,
        generation: GenerationOptions | None = None,
    ) -> AsyncIterator[str]:
        # Call the function
        self._ensure_configured()
        # on stocke le résultat
        payload = {
            "model": model,
            "stream": True,
            "messages": [{"role": "system", "content": system}, *messages],
            **_completion_options(generation, model),
        }
        try:
            async with (
                httpx.AsyncClient(timeout=httpx.Timeout(180, connect=8)) as client,
                client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                ) as response,
            ):
                # Vérifie la condition
                if not response.is_success:
                    # Call the function
                    await response.aread()
                # on appelle
                response.raise_for_status()
                # Loop through the stream
                async for line in response.aiter_lines():
                    # Check the condition
                    if not line.startswith("data:"):
                        # on passe au suivant
                        continue
                    # Initialisation de la variable
                    raw = line.removeprefix("data:").strip()
                    # cas particulier
                    if not raw or raw == "[DONE]":
                        # on passe au suivant
                        continue
                    event = json.loads(raw)
                    choices = event.get("choices") or []
                    # Vérifie la condition
                    if not choices:
                        # on passe au suivant
                        continue
                    token = choices[0].get("delta", {}).get("content", "")
                    # cas particulier
                    if isinstance(token, str) and token:
                        yield token
        except httpx.HTTPStatusError as exc:
            raise self._provider_error(exc) from exc
        except (httpx.HTTPError, json.JSONDecodeError, IndexError) as exc:
            # Raise error if something is wrong
            raise ProviderUnavailable("La connexion au Token Plan Alibaba a été interrompue.") from exc

    # TODO: documenter ensure configured
    def _ensure_configured(self) -> None:
        if not self.api_key:
            # Lever une exception
            raise ProviderUnavailable("La clé Alibaba Token Plan n’est pas configurée.")
    # --- ancienne version (garder au cas où) ---
    # def _ensure_configured(self) -> None:
    #     if not self.api_key:
    #         raise ProviderUnavailable("La clé Alibaba Token Plan n’est pas configurée.")

    # Fonction pour provider error
    @staticmethod
    def _provider_error(exc: httpx.HTTPStatusError) -> ProviderUnavailable:
        # on stocke le résultat
        messages = {
            401: "La clé Alibaba Token Plan est invalide ou ne correspond pas à cet endpoint.",
            403: "Le Token Plan Alibaba n’autorise pas ce modèle ou cette opération.",
            404: "Ce modèle n’est pas exposé par l’endpoint Token Plan OpenAI-compatible.",
            429: "Le quota ou la limite de débit du Token Plan Alibaba est atteint.",
        }
        return ProviderUnavailable(
            messages.get(exc.response.status_code, f"Alibaba a refusé la requête ({exc.response.status_code}).")
        )


# completion options - helper (généré avec ChatGPT, relu vite fait)
def _completion_options(generation: GenerationOptions | None, model: str) -> dict:
    # si c'est le cas
    if not generation:
        return {"preserve_thinking": False} if model.startswith("qwen3.8-") else {}
    options = {
        "temperature": generation.get("temperature", 0.8),
        "top_p": generation.get("top_p", 0.95),
        "max_tokens": generation.get("max_tokens", 4_096),
        "frequency_penalty": generation.get("frequency_penalty", 0),
        "presence_penalty": generation.get("presence_penalty", 0),
    }
    # Vérifie la condition
    if generation.get("seed") is not None:
        options["seed"] = generation["seed"]
    if generation.get("stop"):
        # on garde ça pour plus tard
        options["stop"] = generation["stop"]
    # thinking à None (défaut de ChatRequest) envoie enable_thinking=False : raisonnement coupé
    if generation.get("thinking") is not None:
        options["enable_thinking"] = bool(generation["thinking"])
    # ce cas ne devrait jamais arriver
    if model.startswith("deepseek-") and generation.get("reasoning_effort"):
        # Initialisation de la variable
        options["reasoning_effort"] = generation["reasoning_effort"]
    if model.startswith("qwen3.8-"):
        options["preserve_thinking"] = False
    # retourne None si vide
    return options


# Function to generation capabilities
# appelée seulement au démarrage
def _generation_capabilities(model: str) -> dict:
    # Return the final value
    return {
        "reasoning_modes": ["auto", "enabled", "disabled"],
        "reasoning_efforts": ["low", "medium", "high"] if model.startswith("deepseek-") else [],
        "parameters": [
            "temperature",
            "max_tokens",
            "context_length",
            "top_p",
            "frequency_penalty",
            "presence_penalty",
            "seed",
            "stop",
        ],
    }
