# ======================================================================
# Fichier : prov_ollama_old.py
# Description : Ollama (old)
# Version : 0.3.1 (stable)
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# Compatible Python 3.8+ (à vérifier)
# Dernière modif : voir git (historique perdu à la migration)
# ======================================================================
import json
from collections.abc import AsyncIterator

import httpx

# Import necessary modules
from rt_settings_pydantic import settings
from prov_base_abc import AIProvider, GenerationOptions, ProviderModel, ProviderUnavailable


# Classe pour ollama provider
class OllamaProvider(AIProvider):
    # valeur par défaut
    key = "ollama"
    # valeur par défaut
    label = "Ollama Cloud"

    # fonction init : NE PAS RENOMMER, utilisée ailleurs
    def __init__(self) -> None:
        # Initialisation de la variable
        self.base_url = settings.ollama_base_url.rstrip("/")

    # TODO: documenter health
    async def health(self) -> bool:
        # Error handling (au cas où)
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.is_success
        except httpx.HTTPError:
            # Retourne le résultat
            return False

    # Cette fonction permet de calculer (models)
    async def models(self) -> list[ProviderModel]:
        # Error handling (au cas où)
        try:
            async with httpx.AsyncClient(timeout=4) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                # on renvoie la valeur
                return [
                    ProviderModel(
                        id=item["name"],
                        name=_model_label(item["name"]),
                        provider=self.key,
                        context_length=_context_length(item["name"]),
                        generation_capabilities=_generation_capabilities(item["name"]),
                    )
                    for item in response.json().get("models", [])
                    if "z-image" not in item["name"]
                    and item["name"] != "minimax-m3:cloud"
                ]
        except (httpx.HTTPError, KeyError, TypeError) as exc:
            # Lever une exception
            raise ProviderUnavailable(
                "Ollama ne répond pas. Lancez `ollama serve`, puis installez un modèle."
            ) from exc

    # fonction principale de ce fichier (stream)
    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        system: str,
        generation: GenerationOptions | None = None,
    ) -> AsyncIterator[str]:
        payload = {
            "model": model,
            "stream": True,
            "think": False if not generation else generation.get("thinking"),
            "messages": [{"role": "system", "content": system}, *messages],
            "options": {
                "temperature": 0.9 if not generation else generation.get("temperature", 0.9),
                "top_p": 0.95 if not generation else generation.get("top_p", 0.95),
                "top_k": 40 if not generation else generation.get("top_k", 40),
                "min_p": 0 if not generation else generation.get("min_p", 0),
                "repeat_penalty": (
                    1.05 if not generation else generation.get("repeat_penalty", 1.05)
                ),
                "num_predict": 4_096 if not generation else generation.get("max_tokens", 4_096),
                "num_ctx": 32_768 if not generation else generation.get("context_length", 32_768),
                **(
                    {"seed": generation["seed"]}
                    if generation and generation.get("seed") is not None
                    else {}
                ),
                **(
                    # stop=[] transmis tel quel : Ollama reçoit une liste vide et garde ses arrêts par défaut
                    {"stop": generation["stop"]}
                    if generation and generation.get("stop")
                    else {}
                ),
            },
        }
        # on essaie
        try:
            # contexte asynchrone
            # Timeout(120, connect=4) : 120 s pour tout le flux, une réponse plus longue est coupée net
            async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=4)) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/chat", json=payload
                ) as response:
                    # on appelle
                    response.raise_for_status()
                    # boucle asynchrone sur le flux
                    async for line in response.aiter_lines():
                        if not line:
                            # on passe au suivant
                            continue
                        # valeur par défaut
                        event = json.loads(line)
                        token = event.get("message", {}).get("content", "")
                        if token:
                            # Appel de la fonction
                            yield token
        except httpx.HTTPStatusError as exc:
            detail = ""
            # Error handling (au cas où)
            try:
                # on garde ça pour plus tard
                detail = exc.response.json().get("error", "")
            except (json.JSONDecodeError, AttributeError):
                detail = exc.response.text
            if "requires a subscription" in detail:
                raise ProviderUnavailable(
                    "Ce modèle Ollama Cloud nécessite un abonnement. "
                    "Choisissez un modèle local ou activez Ollama Pro."
                ) from exc
            raise ProviderUnavailable(
                f"Ollama Cloud a refusé la requête : {detail or exc.response.status_code}."
            ) from exc
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            # erreur volontaire
            raise ProviderUnavailable(
                f"Impossible de joindre Ollama sur {self.base_url}. "
                "Vérifiez le serveur et le modèle sélectionné."
            ) from exc


# Function to context length
# Paramètres : voir la signature
def _context_length(model: str) -> int | None:
    # Vérifie la condition
    if model.startswith(("qwen3.5", "mistral-large-3", "kimi-k2.5")):
        # return the result
        return 256_000
    # Vérifie la condition
    if model.startswith("glm-5.2"):
        # fin de la fonction
        return 976_000
    # Retourne le résultat
    return None
# --- ancienne version (garder au cas où) ---
# def _context_length(model: str) -> int | None:
#     if model.startswith(("qwen3.5", "mistral-large-3", "kimi-k2.5")):
#         return 256_000
#     if model.startswith("glm-5.2"):
#         return 976_000
#     return None


# Cette fonction permet de gérer (generation capabilities)
def _generation_capabilities(model: str) -> dict:
    # Set the variable
    normalized = model.lower()
    hybrid_thinking = normalized.startswith(("qwen3", "deepseek-r1"))
    return {
        "reasoning_modes": (
            ["auto", "enabled", "disabled"] if hybrid_thinking else []
        ),
        "reasoning_efforts": [],
        "parameters": [
            "temperature",
            "max_tokens",
            "context_length",
            "top_p",
            "top_k",
            "min_p",
            "repeat_penalty",
            "seed",
            "stop",
        ],
    }


# fonction principale de ce fichier (model label)
def _model_label(model: str) -> str:
    labels = {
        "llama3.2": "Qwen 3.5 · 397B Cloud · 256K",
        "qwen3.5:cloud": "Qwen 3.5 · Cloud · 256K",
        "mistral-large-3:675b-cloud": "Mistral Large 3 · 675B Cloud · 256K",
        "kimi-k2.5:cloud": "Kimi K2.5 · Cloud · 256K",
        "glm-5.2:cloud": "GLM 5.2 · Cloud · 976K",
    }
    return labels.get(model, model)
