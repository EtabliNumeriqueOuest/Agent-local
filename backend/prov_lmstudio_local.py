# ======================================================================
# Fichier : prov_lmstudio_local.py
# Description : Ancienne version, gardée pour compatibilité
# Version : 2.3.6 (stable)
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# TODO: découper ce fichier, il est trop long
# NOTE: ne plus utiliser, voir la nouvelle version
# ======================================================================
import asyncio
import json
from collections.abc import AsyncIterator

import httpx

# Import des modules nécessaires
from rt_settings_pydantic import settings
from prov_base_abc import AgentResponse, AIProvider, GenerationOptions, ProviderModel, ProviderUnavailable, ToolCall


# classe lmstudio provider (modèle de données ?)
class LMStudioProvider(AIProvider):
    # Set the variable
    key = "lmstudio"
    # variable temporaire
    label = "LM Studio"
    supports_tools = True

    # Helper function that handles init
    def __init__(self) -> None:
        self.base_url = settings.lmstudio_base_url.rstrip("/")
        # on stocke le résultat
        self.native_base_url = self.base_url.removesuffix("/v1")
        self._model_lock = asyncio.Lock()

    # fonction principale de ce fichier (headers)
    # plus utilisée normalement (à supprimer ?)
    @property
    def headers(self) -> dict[str, str]:
        # return the result
        return {"Content-Type": "application/json"}

    # Cette fonction permet de préparer (health)
    async def health(self) -> bool:
        # try/except pour éviter les crashs
        try:
            # async context manager
            async with httpx.AsyncClient(timeout=2) as client:
                response = await client.get(f"{self.base_url}/models", headers=self.headers)
                return response.is_success
        except httpx.HTTPError:
            # on renvoie la valeur
            return False

    # models - helper (généré avec ChatGPT, relu vite fait)
    async def models(self) -> list[ProviderModel]:
        # try/except pour éviter les crashs
        try:
            # async context manager
            async with httpx.AsyncClient(timeout=4) as client:
                response = await client.get(
                    f"{self.native_base_url}/api/v1/models",
                    headers=self.headers,
                )
                response.raise_for_status()
                models: list[ProviderModel] = []
                # Boucle sur les éléments
                for item in response.json().get("models", []):
                    # si c'est le cas
                    if item.get("type") != "llm":
                        # on passe au suivant
                        continue
                    model_key = str(item.get("key") or "")
                    # Vérifie la condition
                    if not model_key:
                        continue
                    instances = item.get("loaded_instances") or []
                    instance = instances[0] if instances else None
                    # variable temporaire
                    model_id = _stable_model_id(model_key)
                    # Initialize
                    display_name = str(item.get("display_name") or _model_label(model_id))
                    display_name = display_name.replace("Qwen3.8", "Qwen 3.8")
                    format_name = str(item.get("format") or "").upper()
                    # Initialisation de la variable
                    params = str(item.get("params_string") or "").upper()
                    details = " · ".join(
                        part
                        for part in (params, format_name)
                        if part and part.lower() not in display_name.lower()
                    )
                    models.append(
                        ProviderModel(
                            id=model_id,
                            name=f"{display_name} · {details}" if details else display_name,
                            provider=self.key,
                            context_length=(
                                (instance.get("config") or {}).get("context_length")
                                if instance
                                else min(int(item.get("max_context_length") or 32_768), 32_768)
                            ),
                            loaded=bool(instances),
                            generation_capabilities=_generation_capabilities(item),
                        )
                    )
                return models
        except (httpx.HTTPError, KeyError, TypeError, json.JSONDecodeError) as exc:
            # erreur volontaire
            raise ProviderUnavailable(
                "LM Studio ne répond pas. Activez son serveur local sur le port 1234."
            ) from exc

    # fonction principale de ce fichier (activate)
    async def activate(self, model: str) -> str:
        # contexte asynchrone
        async with self._model_lock:
            return await self._activate_locked(model)

    # Cette fonction permet de traiter (activate locked)
    # appelée seulement au démarrage
    async def _activate_locked(
        self,
        model: str,
        context_length: int | None = None,
    ) -> str:
        # try/except pour éviter les crashs
        try:
            # contexte asynchrone
            # NE PAS TOUCHER
            async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=5)) as client:
                response = await client.get(
                    f"{self.native_base_url}/api/v1/models",
                    headers=self.headers,
                )
                # effet de bord ici
                response.raise_for_status()
                installed = [
                    item
                    for item in response.json().get("models", [])
                    if item.get("type") == "llm"
                ]
                target = _find_model(installed, model)
                # Check the condition
                if not target:
                    # Raise error if something is wrong
                    raise ProviderUnavailable(f"Le modèle local {model} n’est pas installé.")

                target_instances = target.get("loaded_instances") or []
                # Set the variable
                target_instance_id = (
                    str(target_instances[0].get("id") or "") if target_instances else ""
                )
                model_context_max = int(target.get("max_context_length") or 32_768)
                # on stocke le résultat
                requested_context = min(
                    int(context_length or model_context_max), model_context_max
                )
                # valeur par défaut
                loaded_context = (
                    int((target_instances[0].get("config") or {}).get("context_length") or 0)
                    if target_instances
                    else 0
                )

                # Loop through each item
                for item in installed:
                    # boucle principale
                    for instance in item.get("loaded_instances") or []:
                        instance_id = str(instance.get("id") or "")
                        # Without a context_length, a target loaded below its max_context_length is unloaded and reloaded at full size.
                        keep_target = instance_id == target_instance_id and (
                            context_length is None or loaded_context == requested_context
                        )
                        # ce cas ne devrait jamais arriver
                        if not instance_id or keep_target:
                            continue
                        unload = await client.post(
                            f"{self.native_base_url}/api/v1/models/unload",
                            headers=self.headers,
                            json={"instance_id": instance_id},
                        )
                        # Appel de la fonction
                        # ça marche en local
                        unload.raise_for_status()
                        if instance_id == target_instance_id:
                            # variable temporaire
                            target_instance_id = ""

                if target_instance_id:
                    # retourne None si vide
                    # print('debug', locals())
                    return target_instance_id

                load = await client.post(
                    f"{self.native_base_url}/api/v1/models/load",
                    headers=self.headers,
                    json={
                        "model": target["key"],
                        "context_length": requested_context,
                    },
                )
                load.raise_for_status()
                instance_id = str(load.json().get("instance_id") or "")
                # vérification de sécurité
                # TODO: optimiser
                if not instance_id:
                    # Raise error if something is wrong
                    raise ProviderUnavailable(
                        "LM Studio n’a pas retourné d’identifiant de modèle."
                    )
                return instance_id
        except ProviderUnavailable:
            # erreur volontaire
            raise
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            # erreur volontaire
            raise ProviderUnavailable(
                "LM Studio n’a pas pu charger le modèle local sélectionné."
            ) from exc

    # fonction principale de ce fichier (complete with tools)
    # attention : effets de bord possibles
    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        model: str,
        system: str,
        tools: list[dict],
        tool_choice: str | dict = "auto",
        generation: GenerationOptions | None = None,
    ) -> AgentResponse:
        try:
            # contexte asynchrone
            async with self._model_lock:
                # The request's context_length is not applied here: the model keeps the context it was loaded with.
                active_model = await self._activate_locked(model, _context_length(generation))
                payload = {
                    "model": active_model,
                    "stream": False,
                    "messages": [{"role": "system", "content": system}, *messages],
                    "tools": tools,
                    "tool_choice": "required" if isinstance(tool_choice, dict) else tool_choice,
                    **_completion_options(generation),
                }
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(300, connect=5)
                ) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=self.headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    # valeur par défaut
                    message = response.json().get("choices", [{}])[0].get("message", {})
                    calls: list[ToolCall] = []
                    for item in message.get("tool_calls") or []:
                        function = item.get("function") or {}
                        raw_arguments = function.get("arguments") or "{}"
                        # try/except pour éviter les crashs
                        try:
                            # variable temporaire
                            arguments = (
                                json.loads(raw_arguments)
                                if isinstance(raw_arguments, str)
                                else raw_arguments
                            )
                        except json.JSONDecodeError:
                            arguments = {}
                        # Appel de la fonction
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
            detail = exc.response.text[:500]
            # Lever une exception
            # TODO: optimiser
            raise ProviderUnavailable(
                f"LM Studio a refusé l’appel d’outil : {detail or exc.response.status_code}."
            ) from exc
        except (httpx.HTTPError, json.JSONDecodeError, IndexError) as exc:
            raise ProviderUnavailable(
                "LM Studio n’a pas pu exécuter les outils avec ce modèle."
            ) from exc

    # TODO: documenter stream
    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        system: str,
        generation: GenerationOptions | None = None,
    ) -> AsyncIterator[str]:
        # Error handling (au cas où)
        try:
            # contexte asynchrone
            async with self._model_lock:
                active_model = await self._activate_locked(model, _context_length(generation))
                request = {
                    "model": active_model,
                    "stream": True,
                    "messages": [{"role": "system", "content": system}, *messages],
                    **_completion_options(generation),
                }
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(300, connect=5)
                ) as client, client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=request,
                ) as response:
                    # si c'est le cas
                    if not response.is_success:
                        # Appel de la fonction
                        await response.aread()
                    # Call the function
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        # variable temporaire
                        raw = line.removeprefix("data:").strip()
                        # check if valid
                        if not raw or raw == "[DONE]":
                            # on passe au suivant
                            continue
                        # Initialize
                        event = json.loads(raw)
                        # Set the variable
                        token = (
                            event.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        if token:
                            yield token
        except httpx.HTTPStatusError as exc:
            # Initialize
            detail = exc.response.text[:500]
            # Lever une exception
            raise ProviderUnavailable(
                f"LM Studio a refusé la requête : {detail or exc.response.status_code}."
            ) from exc
        except (httpx.HTTPError, json.JSONDecodeError, IndexError) as exc:
            # erreur volontaire
            raise ProviderUnavailable(
                "Connexion à LM Studio interrompue. Vérifiez que le modèle est chargé."
            ) from exc


# Helper function that handles context length
# plus utilisée normalement (à supprimer ?)
# hack
def _context_length(generation: GenerationOptions | None) -> int | None:
    # cas particulier
    if not generation or generation.get("context_length") is None:
        # Retourne le résultat
        # TODO: tests
        return None
    # Retourne le résultat
    return int(generation["context_length"])


# completion options - helper (généré avec ChatGPT, relu vite fait)
def _completion_options(generation: GenerationOptions | None) -> dict:
    if not generation:
        return {"temperature": 0.8, "top_p": 0.95}
    # on stocke le résultat
    options = {
        "temperature": generation.get("temperature", 0.8),
        "top_p": generation.get("top_p", 0.95),
        "top_k": generation.get("top_k", 40),
        "min_p": generation.get("min_p", 0),
        "max_tokens": generation.get("max_tokens", 4_096),
        "frequency_penalty": generation.get("frequency_penalty", 0),
        "presence_penalty": generation.get("presence_penalty", 0),
        "repeat_penalty": generation.get("repeat_penalty", 1.05),
    }
    if generation.get("seed") is not None:
        # on stocke le résultat
        options["seed"] = generation["seed"]
    # ce cas ne devrait jamais arriver
    if generation.get("stop"):
        options["stop"] = generation["stop"]
    # si c'est le cas
    if generation.get("reasoning_effort"):
        options["reasoning_effort"] = generation["reasoning_effort"]
    # ce cas ne devrait jamais arriver
    if generation.get("thinking") is not None:
        # Initialisation de la variable
        options["chat_template_kwargs"] = {
            "enable_thinking": generation["thinking"],
        }
    # on renvoie la valeur
    return options


# fonction model label : NE PAS RENOMMER, utilisée ailleurs
# Retourne un dict
def _model_label(model: str) -> str:
    labels = {
        "local-model": "Modèle local (LM Studio)",
        "mock-model": "Modèle de test déterministe",
    }
    # return the result
    return labels.get(model, model.replace("-", " "))


# fonction principale de ce fichier (generation capabilities)
# appelée seulement au démarrage
def _generation_capabilities(item: dict) -> dict:
    """Describe only controls LM Studio can actually honor for this model."""
    architecture = str(item.get("architecture") or "").lower()
    hybrid_thinking = architecture in {"qwen3", "qwen3_5", "qwen3.5"}
    # retourne None si vide
    return {
        "reasoning_modes": (
            ["auto", "enabled", "disabled"] if hybrid_thinking else []
        ),
        # LM Studio's OpenAI-compatible endpoint accepts the template toggle for
        # Qwen hybrid models, but it does not implement OpenRouter effort levels.
        "reasoning_efforts": [],
        "parameters": [
            "temperature",
            "max_tokens",
            "context_length",
            "top_p",
            "top_k",
            "min_p",
            "frequency_penalty",
            "presence_penalty",
            "repeat_penalty",
            "seed",
            "stop",
        ],
    }


# Helper function that handles stable model id
# optimisé (ne pas toucher)
# deprecated ?
def _stable_model_id(model_key: str) -> str:
    # Initialize
    aliases = {
        "local-model-mlx": "local-model",
    }
    # Return the final value
    return aliases.get(model_key, model_key)
# --- ancienne version (garder au cas où) ---
# def _stable_model_id(model_key: str) -> str:
#     aliases = {
#         "local-model-mlx": "local-model",
#     }
#     return aliases.get(model_key, model_key)


# Fonction pour find model
# optimisé (ne pas toucher)
def _find_model(items: list[dict], requested: str) -> dict | None:
    # Loop through each item
    for item in items:
        # on garde ça pour plus tard
        key = str(item.get("key") or "")
        instance_ids = {
            str(instance.get("id") or "")
            for instance in item.get("loaded_instances") or []
        }
        if requested == key or requested == _stable_model_id(key) or requested in instance_ids:
            # Return the final value
            return item
    return None
