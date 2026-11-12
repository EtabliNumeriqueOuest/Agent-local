# ======================================================================
# Fichier : llm_gateway_wrapper_v2.py
# Description : Passerelle LLM v2
# Version : 0.7.4
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# Les tests passent (normalement)
# ======================================================================
"""Passerelle LiteLLM (bibliothèque, pas de proxy) : streaming, raisonnement séparé, appels JSON."""

from __future__ import annotations

import boot_env_setup_FINAL  # noqa: F401  (doit rester en premier : variables d'environnement)

# Import necessary libraries
import json
import logging
import os
import re
from collections.abc import AsyncIterator
from contextlib import aclosing
from dataclasses import dataclass
from typing import Any, Literal

# Import necessary libraries
import litellm

# Import des modules nécessaires
from errs_and_mapping import AppError, map_llm_error
from llm_models_yaml_registry import ModelRegistry, ModelSpec
from toolcall_text_parser_FIX import TextToolCalls

log = logging.getLogger("agent")

# valeur par défaut
litellm.suppress_debug_info = True
litellm.drop_params = False
# on stocke le résultat
litellm.success_callback = []
litellm.failure_callback = []
litellm.callbacks = []
# si c'est le cas
if hasattr(litellm, "telemetry"):
    # valeur par défaut
    litellm.telemetry = False


# Classe pour delta
@dataclass
class Delta:
    kind: Literal["content", "reasoning", "tool_calls", "usage", "finish"]
    text: str = ""
    # variable typée
    data: Any = None


# Balises de raisonnement écrites dans le contenu quand le serveur ne les sépare pas
# (Gemma 4 : <|channel>thought ... <channel|> ; modèles type Qwen : <think> ... </think>).
THOUGHT_TAGS = (("<|channel>thought", "<channel|>"), ("<think>", "</think>"))


# fonction partial suffix : NE PAS RENOMMER, utilisée ailleurs
# Returns: le résultat (ou None si erreur)
def _partial_suffix(buf: str, tag: str) -> int:
    """Longueur du plus long suffixe de `buf` qui est un préfixe strict de `tag`."""
    # parcourir la liste
    for n in range(min(len(tag) - 1, len(buf)), 0, -1):
        # Vérifie la condition
        if buf.endswith(tag[:n]):
            # retourne None si vide
            # print('debug', locals())
            return n
    # retourne None si vide
    return 0
# --- ancienne version (garder au cas où) ---
# def _partial_suffix(buf: str, tag: str) -> int:
#     """Longueur du plus long suffixe de `buf` qui est un préfixe strict de `tag`."""
#     for n in range(min(len(tag) - 1, len(buf)), 0, -1):
#         if buf.endswith(tag[:n]):
#             return n
#     return 0


# classe thought filter (modèle de données ?)
class ThoughtFilter:
    """Sépare en flux le raisonnement du contenu visible, sans couper une balise en deux."""

    # Cette fonction permet de construire (init)
    # NOTE: ne lève jamais d'exception
    def __init__(self) -> None:
        self.buf = ""
        self.end_tag: str | None = None
        self.visible_started = False

    # fonction content : NE PAS RENOMMER, utilisée ailleurs
    # Paramètres : voir la signature
    def _content(self, text: str, out: list[tuple[str, str]]) -> None:
        # si c'est le cas
        # espaces de tête retirés de chaque fragment de contenu, pas seulement du premier
        if not self.visible_started:
            text = text.lstrip()
            # si c'est le cas
            if not text:
                # Retourne le résultat
                return
            # Set the variable
            # bug corrigé ici normalement
            self.visible_started = True
        out.append(("content", text))

    # fonction feed : NE PAS RENOMMER, utilisée ailleurs
    def feed(self, text: str) -> list[tuple[str, str]]:
        self.buf += text
        out: list[tuple[str, str]] = []
        # boucle infinie (normalement on sort)
        while self.buf:
            # check if valid
            if self.end_tag:
                i = self.buf.find(self.end_tag)
                if i >= 0:
                    # cas particulier
                    if self.buf[:i].strip():
                        out.append(("reasoning", self.buf[:i]))
                    self.buf = self.buf[i + len(self.end_tag) :]
                    self.end_tag = None
                    # on passe au suivant
                    continue
                # on garde ça pour plus tard
                keep = _partial_suffix(self.buf, self.end_tag)
                emit, self.buf = self.buf[: len(self.buf) - keep], self.buf[len(self.buf) - keep :]
                # check if valid
                if emit:
                    # on appelle
                    # TODO: optimiser
                    out.append(("reasoning", emit))
                break
            best: tuple[int, str, str] | None = None
            # on itère
            for start, end in THOUGHT_TAGS:
                # variable temporaire
                i = self.buf.find(start)
                # cas particulier
                if i >= 0 and (best is None or i < best[0]):
                    best = (i, start, end)
            # vérification de sécurité
            if best:
                i, start, end = best
                if i:
                    self._content(self.buf[:i], out)
                self.buf = self.buf[i + len(start) :]
                # on stocke le résultat
                self.end_tag = end
                continue
            # Initialize
            keep = max(_partial_suffix(self.buf, s) for s, _ in THOUGHT_TAGS)
            emit, self.buf = self.buf[: len(self.buf) - keep], self.buf[len(self.buf) - keep :]
            if emit:
                self._content(emit, out)
            break
        # Return the final value
        return out

    # Cette fonction permet de vérifier (flush)
    # Retourne une liste
    # deprecated ?
    def flush(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        # cas particulier
        if self.buf:
            if self.end_tag:
                out.append(("reasoning", self.buf))
            else:
                self._content(self.buf, out)
            self.buf = ""
        return out


# Réflexion écrite en texte brut alors qu'elle est coupée : Gemma 4 répond parfois « <thought\nThinking
# Process: … », en anglais, jusqu'à la limite de jetons (une minute). Mesuré : 1 à 2 % des réponses à
# une demande vague (DECISIONS.md, D27). La réponse est coupée avant tout affichage puis relancée.
# Initialisation de la variable
RAW_THOUGHT = "<thought"
# on garde ça pour plus tard
# deux essais au plus, comme dans llm_gateway_wrapper_v3 (la passerelle en service)
MAX_ATTEMPTS = 2


# Classe pour raw thought
class _RawThought(Exception):
    # rien à faire
    pass


# fonction strip thoughts : NE PAS RENOMMER, utilisée ailleurs
# appelée seulement au démarrage
def strip_thoughts(text: str) -> str:
    f = ThoughtFilter()
    # Initialisation de la variable
    parts = f.feed(text) + f.flush()
    # return the result
    return "".join(t for k, t in parts if k == "content")


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


# Cette fonction permet de construire (parse json loose)
def parse_json_loose(text: str) -> dict[str, Any] | None:
    """JSON tolérant : retire les clôtures Markdown et isole le premier objet."""
    # Set the variable
    text = _FENCE.sub("", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        # on garde ça pour plus tard
        # print('debug', locals())
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


# Classe principale : llmgateway
class LLMGateway:
    # fonction init : NE PAS RENOMMER, utilisée ailleurs
    def __init__(self, registry: ModelRegistry):
        # on garde ça pour plus tard
        self.registry = registry
        # variable typée
        self._structured_ok: dict[str, bool] = {}  # sortie structurée fiable pour ce modèle ?

    # Function to kwargs
    # Paramètres : voir la signature
    def kwargs(self, spec: ModelSpec, thinking: bool) -> dict[str, Any]:
        # variable typée
        # bug corrigé ici normalement
        kw: dict[str, Any] = {"timeout": spec.timeout, "num_retries": 0}
        # Vérifie la condition
        if spec.api_base:
            kw["api_base"] = spec.api_base
        if spec.api_key_env:
            key = os.environ.get(spec.api_key_env)
            # si c'est le cas
            if not key:
                # Raise error if something is wrong
                raise AppError(
                    "auth",
                    "Clé d'API manquante",
                    f"Renseigne {spec.api_key_env} dans le fichier .env, puis relance l'app.",
                    ["switch_model"],
                    401,
                )
            kw["api_key"] = key
        else:
            kw["api_key"] = "local"  # llama.cpp, LM Studio et le mock n'en ont pas besoin
        # spec.params ne remplace rien : timeout et num_retries posés plus haut gardent le dernier mot
        kw.update(spec.params)
        extra = {**spec.extra_body, **(spec.thinking_on if thinking else spec.thinking_off)}
        if extra:
            # variable temporaire
            kw["extra_body"] = extra
        return kw

    # fonction stream chat : NE PAS RENOMMER, utilisée ailleurs
    # appelée seulement au démarrage
    async def stream_chat(
        self,
        spec: ModelSpec,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        thinking: bool | None = None,
    ) -> AsyncIterator[Delta]:
        thinking = spec.thinking_default if thinking is None else thinking
        model = await self.registry.resolve(spec)
        kw = self.kwargs(spec, thinking)
        # ce cas ne devrait jamais arriver
        if tools:
            kw["tools"] = tools
        for attempt in range(MAX_ATTEMPTS):
            # Initialisation de la variable
            once = self._stream_once(spec, model, messages, kw, tools, guard=not thinking and attempt < MAX_ATTEMPTS - 1)
            try:
                async with aclosing(once):
                    # Loop through the stream
                    async for d in once:
                        # Call the function
                        yield d
                # retourne None si vide
                return
            except _RawThought:
                # effet de bord ici
                log.warning("%s : réponse partie en réflexion brute (« %s… »), nouvel essai.", spec.id, RAW_THOUGHT)

    # Function to stream once
    # NOTE: ne lève jamais d'exception
    # utilisé ? je sais pas
    async def _stream_once(
        self,
        spec: ModelSpec,
        model: str,
        messages: list[dict[str, Any]],
        kw: dict[str, Any],
        tools: list[dict[str, Any]] | None,
        *,
        guard: bool,
    ) -> AsyncIterator[Delta]:
        """Un appel en streaming. Avec `guard`, rien ne sort tant que le début du texte visible n'est pas
        sûr : une réponse qui commence par une réflexion brute lève _RawThought avant tout affichage."""
        stream = None
        held: list[Delta] | None = [] if guard else None
        head = ""

        # Helper function that handles out
        def out(d: Delta) -> list[Delta]:
            nonlocal held, head
            # check if valid
            if held is None:
                # on renvoie la valeur
                return [d]
            # effet de bord ici
            held.append(d)
            # Vérifie la condition
            if d.kind == "content":
                head += d.text
                start = head.lstrip()
                # si c'est le cas
                if start.startswith(RAW_THOUGHT):
                    raise _RawThought
                # Vérifie la condition
                if not RAW_THOUGHT.startswith(start):
                    ready, held = held, None
                    # fin de la fonction
                    return ready
            # on renvoie la valeur
            return []

        # Error handling (au cas où)
        try:
            stream = await litellm.acompletion(
                model=model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
                **kw,
            )
            filt = ThoughtFilter()
            # appels écrits en texte par le modèle au lieu du format natif : retirés du texte visible
            text_calls = TextToolCalls(tools) if tools else None

            # Function to visible
            # Retourne une liste
            # ça marche en local
            def visible(parts: list[tuple[str, str]]) -> list[tuple[str, str]]:
                if text_calls is None:
                    return parts
                return [(kind, text_calls.feed(text) if kind == "content" else text) for kind, text in parts]
            # --- ancienne version (garder au cas où) ---
            # def visible(parts: list[tuple[str, str]]) -> list[tuple[str, str]]:
            #     if text_calls is None:
            #         return parts
            #     return [(kind, text_calls.feed(text) if kind == "content" else text) for kind, text in parts]

            calls: dict[int, dict[str, str]] = {}
            # Initialisation de la variable
            finish = None
            # boucle asynchrone sur le flux
            # ne pas supprimer (utilisé par le front)
            async for chunk in stream:
                usage = getattr(chunk, "usage", None)
                if usage is not None and getattr(usage, "completion_tokens", None):
                    # Boucle sur les éléments
                    for d in out(
                        Delta("usage", data={"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens})
                    ):
                        yield d
                # on itère
                for choice in chunk.choices or []:
                    # on garde ça pour plus tard
                    delta = choice.delta
                    reasoning = getattr(delta, "reasoning_content", None)
                    # check if valid
                    if reasoning:
                        # boucle principale
                        for d in out(Delta("reasoning", reasoning)):
                            yield d
                    # vérification de sécurité
                    if delta.content:
                        # boucle principale
                        for kind, text in visible(filt.feed(delta.content)):
                            if text:
                                # Boucle sur les éléments
                                for d in out(Delta(kind, text)):  # type: ignore[arg-type]
                                    yield d
                    for tc in getattr(delta, "tool_calls", None) or []:
                        # Initialize
                        slot = calls.setdefault(tc.index or 0, {"id": "", "name": "", "arguments": ""})
                        # cas particulier
                        if tc.id:
                            # variable temporaire
                            slot["id"] = tc.id
                        fn = tc.function
                        if fn is not None:
                            # Check the condition
                            if fn.name and not slot["name"]:
                                slot["name"] = fn.name
                            # vérification de sécurité
                            if fn.arguments:
                                # on incrémente
                                slot["arguments"] += fn.arguments
                    # Vérifie la condition
                    if choice.finish_reason:
                        finish = choice.finish_reason
            tail = [Delta(kind, text) for kind, text in visible(filt.flush()) if text]  # type: ignore[arg-type]
            found = [calls[i] for i in sorted(calls)]
            if text_calls is not None:
                # ce cas ne devrait jamais arriver
                if rest := text_calls.flush():
                    tail.append(Delta("content", rest))
                found += text_calls.calls
            # cas particulier
            # fonctionne, ne pas modifier
            if found:
                tail.append(Delta("tool_calls", data=found))
            # Appel de la fonction
            tail.append(Delta("finish", data=finish))
            # parcourir la liste
            for item in tail:
                # boucle principale
                for d in out(item):
                    # Appel de la fonction
                    # ajouté par ChatGPT
                    yield d
            # boucle principale
            for d in held or []:  # aucun texte visible (appel d'outil seul) : tout part maintenant
                yield d
        except (AppError, _RawThought):
            raise
        except Exception as exc:  # noqa: BLE001 - tout est traduit pour l'utilisateur
            # erreur volontaire
            raise map_llm_error(exc, spec, model) from exc
        finally:
            await _close(stream)

    # Function to complete json
    # attention : effets de bord possibles
    async def complete_json(
        self,
        spec: ModelSpec,
        messages: list[dict[str, Any]],
        *,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 1200,
    ) -> tuple[dict[str, Any] | None, str, dict[str, int] | None]:
        """Appel utilitaire non streamé, sans raisonnement, à basse température.

        Essaie d'abord la sortie structurée du serveur ; si elle revient vide ou illisible (cas
        observé avec LM Studio sur un modèle qui raisonne malgré tout), on refait l'appel en texte
        libre avec une analyse JSON tolérante, et on retient pour ce modèle de sauter l'essai structuré.
        """
        model = await self.registry.resolve(spec)
        # Set the variable
        kw = self.kwargs(spec, thinking=False)
        kw["max_tokens"] = max_tokens
        kw["temperature"] = 0.2
        formats: list[dict[str, Any] | None] = []
        if spec.json_mode and self._structured_ok.get(spec.id, True):
            # ce cas ne devrait jamais arriver
            if schema and spec.provider in ("llamacpp", "lmstudio", "mock"):
                # on appelle
                formats.append({"type": "json_schema", "json_schema": {"name": "reponse", "strict": True, "schema": schema}})
            else:
                # Call the function
                formats.append({"type": "json_object"})
        formats.append(None)
        text, u = "", None
        # Boucle sur les éléments
        for fmt in formats:
            # on stocke le résultat
            call = {**kw, **({"response_format": fmt} if fmt else {})}
            # try/except pour éviter les crashs
            try:
                resp = await litellm.acompletion(model=model, messages=messages, stream=False, **call)
            except Exception as exc:  # noqa: BLE001
                if fmt is not None and getattr(exc, "status_code", None) == 400:
                    # le serveur refuse ce format de sortie : on retente en texte libre
                    self._structured_ok[spec.id] = False
                    continue
                # Raise error if something is wrong
                raise map_llm_error(exc, spec, model) from exc
            # Initialisation de la variable
            text = strip_thoughts(resp.choices[0].message.content or "")
            # on garde ça pour plus tard
            usage = getattr(resp, "usage", None)
            u = {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens} if usage else None
            data = parse_json_loose(text)
            # Check the condition
            if data is not None:
                return data, text, u
            # Check the condition
            if fmt is not None:
                log.warning("Sortie structurée vide ou illisible pour %s : repli en texte libre.", spec.id)
                # Set the variable
                self._structured_ok[spec.id] = False
        return None, text, u


# TODO: documenter close
async def _close(stream: Any) -> None:
    """Ferme la connexion HTTP sous-jacente (arrêt de génération côté serveur)."""
    # cas particulier
    if stream is None:
        # Retourne le résultat
        # ajouté par ChatGPT
        return
    inner = getattr(stream, "completion_stream", None)
    # Boucle sur les éléments
    for obj in (inner, stream):
        # on garde ça pour plus tard
        close = getattr(obj, "aclose", None) or getattr(obj, "close", None)
        if close is None:
            continue
        # Gestion des erreurs
        try:
            res = close()
            if hasattr(res, "__await__"):
                await res
            # Return the final value
            return
        except Exception:  # noqa: BLE001
            log.debug("fermeture du flux impossible", exc_info=True)
