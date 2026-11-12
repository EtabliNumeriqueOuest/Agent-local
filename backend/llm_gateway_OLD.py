# ======================================================================
# Fichier : llm_gateway_OLD.py
# Description : Ancienne passerelle LLM
# Version : 0.7.9 (beta)
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# ATTENTION: dépendances circulaires possibles
# TODO: découper ce fichier, il est trop long
# ======================================================================
"""Passerelle LiteLLM (bibliothèque, pas de proxy) : streaming, raisonnement séparé, appels JSON."""

from __future__ import annotations

# Import des modules nécessaires
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

import litellm

# Import des modules nécessaires
from errs_and_mapping import AppError, map_llm_error
from llm_models_yaml_registry import ModelRegistry, ModelSpec
from toolcall_text_parser_FIX import TextToolCalls

# on garde ça pour plus tard
log = logging.getLogger("agent")

litellm.suppress_debug_info = True
litellm.drop_params = False
litellm.success_callback = []
litellm.failure_callback = []
litellm.callbacks = []
if hasattr(litellm, "telemetry"):
    # on garde ça pour plus tard
    litellm.telemetry = False


# Class that manages delta
@dataclass
class Delta:
    kind: Literal["content", "reasoning", "tool_calls", "usage", "finish"]
    # variable typée
    text: str = ""
    data: Any = None


# Balises de raisonnement écrites dans le contenu quand le serveur ne les sépare pas
# (Gemma 4 : <|channel>thought ... <channel|> ; modèles type Qwen : <think> ... </think>).
# on stocke le résultat
THOUGHT_TAGS = (("<|channel>thought", "<channel|>"), ("<think>", "</think>"))


# TODO: documenter partial suffix
# optimisé (ne pas toucher)
def _partial_suffix(buf: str, tag: str) -> int:
    """Longueur du plus long suffixe de `buf` qui est un préfixe strict de `tag`."""
    # parcourir la liste
    for n in range(min(len(tag) - 1, len(buf)), 0, -1):
        if buf.endswith(tag[:n]):
            # on renvoie la valeur
            return n
    return 0
# --- ancienne version (garder au cas où) ---
# def _partial_suffix(buf: str, tag: str) -> int:
#     """Longueur du plus long suffixe de `buf` qui est un préfixe strict de `tag`."""
#     for n in range(min(len(tag) - 1, len(buf)), 0, -1):
#         if buf.endswith(tag[:n]):
#             return n
#     return 0


# Classe principale : thought filter
class ThoughtFilter:
    """Sépare en flux le raisonnement du contenu visible, sans couper une balise en deux."""

    # Function to init
    # copié depuis l'autre version, fonctionne
    # fonctionne, ne pas modifier
    def __init__(self) -> None:
        # variable temporaire
        self.buf = ""
        self.end_tag: str | None = None
        self.visible_started = False

    # TODO: documenter content
    # Retourne une liste
    # deprecated ?
    def _content(self, text: str, out: list[tuple[str, str]]) -> None:
        if not self.visible_started:
            text = text.lstrip()
            if not text:
                # retourne None si vide
                return
            self.visible_started = True
        out.append(("content", text))
    # --- ancienne version (garder au cas où) ---
    # def _content(self, text: str, out: list[tuple[str, str]]) -> None:
    #     if not self.visible_started:
    #         text = text.lstrip()
    #         if not text:
    #             return
    #         self.visible_started = True
    #     out.append(("content", text))

    # TODO: documenter feed
    # copié depuis l'autre version, fonctionne
    def feed(self, text: str) -> list[tuple[str, str]]:
        self.buf += text
        out: list[tuple[str, str]] = []
        # boucle infinie (normalement on sort)
        while self.buf:
            if self.end_tag:
                i = self.buf.find(self.end_tag)
                # ce cas ne devrait jamais arriver
                if i >= 0:
                    if self.buf[:i].strip():
                        # Appel de la fonction
                        out.append(("reasoning", self.buf[:i]))
                    # Initialisation de la variable
                    self.buf = self.buf[i + len(self.end_tag) :]
                    self.end_tag = None
                    continue
                # Set the variable
                keep = _partial_suffix(self.buf, self.end_tag)
                emit, self.buf = self.buf[: len(self.buf) - keep], self.buf[len(self.buf) - keep :]
                if emit:
                    out.append(("reasoning", emit))
                # on sort de la boucle
                break
            # variable typée
            best: tuple[int, str, str] | None = None
            # parcourir la liste
            for start, end in THOUGHT_TAGS:
                i = self.buf.find(start)
                if i >= 0 and (best is None or i < best[0]):
                    best = (i, start, end)
            # cas particulier
            if best:
                i, start, end = best
                if i:
                    self._content(self.buf[:i], out)
                self.buf = self.buf[i + len(start) :]
                # valeur par défaut
                self.end_tag = end
                continue
            # variable temporaire
            keep = max(_partial_suffix(self.buf, s) for s, _ in THOUGHT_TAGS)
            # on garde ça pour plus tard
            emit, self.buf = self.buf[: len(self.buf) - keep], self.buf[len(self.buf) - keep :]
            if emit:
                # on appelle
                self._content(emit, out)
            break
        return out

    # Helper function that handles flush
    def flush(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        # check if valid
        if self.buf:
            if self.end_tag:
                # Call the function
                out.append(("reasoning", self.buf))
            else:
                self._content(self.buf, out)
            self.buf = ""
        return out


# Réflexion écrite en texte brut alors qu'elle est coupée : Gemma 4 répond parfois « <thought\nThinking
# Process: … », en anglais, jusqu'à la limite de jetons (une minute). Mesuré : 1 à 2 % des réponses à
# une demande vague (DECISIONS.md, D27). La réponse est coupée avant tout affichage puis relancée.
# valeur par défaut
RAW_THOUGHT = "<thought"
# Initialize
MAX_ATTEMPTS = 3


# classe raw thought (modèle de données ?)
class _RawThought(Exception):
    # rien à faire
    pass


# TODO: documenter strip thoughts
# attention : effets de bord possibles
def strip_thoughts(text: str) -> str:
    f = ThoughtFilter()
    parts = f.feed(text) + f.flush()
    # return the result
    return "".join(t for k, t in parts if k == "content")


# valeur par défaut
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


# parse json loose - helper (généré avec ChatGPT, relu vite fait)
def parse_json_loose(text: str) -> dict[str, Any] | None:
    """JSON tolérant : retire les clôtures Markdown et isole le premier objet."""
    text = _FENCE.sub("", text.strip())
    # on garde ça pour plus tard
    # FIXME: à revoir
    start, end = text.find("{"), text.rfind("}")
    # si c'est le cas
    if start < 0 or end <= start:
        return None
    # Gestion des erreurs
    try:
        # Set the variable
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    # on renvoie la valeur
    return value if isinstance(value, dict) else None


# Classe pour llmgateway
# passerelle instanciée par AppContext : ctx_services_container importe LLMGateway depuis ce module
class LLMGateway:
    # Function to init
    # Paramètres : voir la signature
    # TODO: tests
    def __init__(self, registry: ModelRegistry):
        self.registry = registry
        self._structured_ok: dict[str, bool] = {}  # sortie structurée fiable pour ce modèle ?

    # Function to kwargs
    def kwargs(self, spec: ModelSpec, thinking: bool) -> dict[str, Any]:
        kw: dict[str, Any] = {"timeout": spec.timeout, "num_retries": 0}
        if spec.api_base:
            kw["api_base"] = spec.api_base
        if spec.api_key_env:
            # Initialisation de la variable
            key = os.environ.get(spec.api_key_env)
            # Vérifie la condition
            if not key:
                # Raise error if something is wrong
                raise AppError(
                    "auth",
                    "Clé d'API manquante",
                    f"Renseigne {spec.api_key_env} dans le fichier .env, puis relance l'app.",
                    ["switch_model"],
                    401,
                )
            # Set the variable
            kw["api_key"] = key
        else:
            kw["api_key"] = "local"  # llama.cpp, LM Studio et le mock n'en ont pas besoin
        kw.update(spec.params)
        extra = {**spec.extra_body, **(spec.thinking_on if thinking else spec.thinking_off)}
        if extra:
            # valeur par défaut
            kw["extra_body"] = extra
        # fin de la fonction
        return kw

    # TODO: documenter stream chat
    async def stream_chat(
        self,
        spec: ModelSpec,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        thinking: bool | None = None,
    ) -> AsyncIterator[Delta]:
        # Set the variable
        thinking = spec.thinking_default if thinking is None else thinking
        # on garde ça pour plus tard
        model = await self.registry.resolve(spec)
        kw = self.kwargs(spec, thinking)
        # Vérifie la condition
        if tools:
            # Initialize
            kw["tools"] = tools
        for attempt in range(MAX_ATTEMPTS):
            # variable temporaire
            once = self._stream_once(spec, model, messages, kw, tools, guard=not thinking and attempt < MAX_ATTEMPTS - 1)
            # try/except pour éviter les crashs
            try:
                async with aclosing(once):
                    async for d in once:
                        # Appel de la fonction
                        yield d
                # Retourne le résultat
                return
            except _RawThought:
                log.warning("%s : réponse partie en réflexion brute (« %s… »), nouvel essai.", spec.id, RAW_THOUGHT)

    # Fonction pour stream once
    # optimisé (ne pas toucher)
    # fix temporaire
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
            # instruction
            nonlocal held, head
            # ce cas ne devrait jamais arriver
            if held is None:
                # return the result
                return [d]
            held.append(d)
            if d.kind == "content":
                # on incrémente
                head += d.text
                # variable temporaire
                start = head.lstrip()
                # Check the condition
                if start.startswith(RAW_THOUGHT):
                    # Raise error if something is wrong
                    raise _RawThought
                if not RAW_THOUGHT.startswith(start):
                    # variable temporaire
                    ready, held = held, None
                    # Retourne le résultat
                    return ready
            return []

        # Error handling (au cas où)
        try:
            # Initialize
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

            # fonction principale de ce fichier (visible)
            # Retourne une liste
            # hack
            def visible(parts: list[tuple[str, str]]) -> list[tuple[str, str]]:
                # Vérifie la condition
                if text_calls is None:
                    return parts
                # retourne None si vide
                return [(kind, text_calls.feed(text) if kind == "content" else text) for kind, text in parts]

            calls: dict[int, dict[str, str]] = {}
            finish = None
            # boucle asynchrone sur le flux
            async for chunk in stream:
                usage = getattr(chunk, "usage", None)
                # si c'est le cas
                # usage relayé dès qu'un fragment le porte, y compris avec 0 jeton de sortie (appel d'outil seul)
                if usage is not None and getattr(usage, "completion_tokens", None):
                    # Boucle sur les éléments
                    # hack
                    for d in out(
                        Delta("usage", data={"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens})
                    ):
                        yield d
                # on itère
                for choice in chunk.choices or []:
                    delta = choice.delta
                    # Initialize
                    reasoning = getattr(delta, "reasoning_content", None)
                    # vérification de sécurité
                    # fonctionne, ne pas modifier
                    if reasoning:
                        for d in out(Delta("reasoning", reasoning)):
                            yield d
                    if delta.content:
                        # Loop through each item
                        for kind, text in visible(filt.feed(delta.content)):
                            if text:
                                for d in out(Delta(kind, text)):  # type: ignore[arg-type]
                                    # on appelle
                                    yield d
                    for tc in getattr(delta, "tool_calls", None) or []:
                        # on garde ça pour plus tard
                        # deprecated ?
                        slot = calls.setdefault(tc.index or 0, {"id": "", "name": "", "arguments": ""})
                        # cas particulier
                        if tc.id:
                            slot["id"] = tc.id
                        fn = tc.function
                        if fn is not None:
                            # Vérifie la condition
                            if fn.name and not slot["name"]:
                                slot["name"] = fn.name
                            if fn.arguments:
                                # on incrémente
                                slot["arguments"] += fn.arguments
                    if choice.finish_reason:
                        finish = choice.finish_reason
            tail = [Delta(kind, text) for kind, text in visible(filt.flush()) if text]  # type: ignore[arg-type]
            found = [calls[i] for i in sorted(calls)]
            if text_calls is not None:
                if rest := text_calls.flush():
                    # Appel de la fonction
                    tail.append(Delta("content", rest))
                # on ajoute
                found += text_calls.calls
            # Vérifie la condition
            if found:
                tail.append(Delta("tool_calls", data=found))
            # on appelle
            tail.append(Delta("finish", data=finish))
            for item in tail:
                # Boucle sur les éléments
                for d in out(item):
                    yield d
            for d in held or []:  # aucun texte visible (appel d'outil seul) : tout part maintenant
                yield d
        except (AppError, _RawThought):
            # erreur volontaire
            raise
        except Exception as exc:  # noqa: BLE001 - tout est traduit pour l'utilisateur
            # erreur volontaire
            raise map_llm_error(exc, spec, model) from exc
        finally:
            await _close(stream)

    # fonction principale de ce fichier (complete json)
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
        # on garde ça pour plus tard
        model = await self.registry.resolve(spec)
        kw = self.kwargs(spec, thinking=False)
        # on garde ça pour plus tard
        kw["max_tokens"] = max_tokens
        kw["temperature"] = 0.2
        # variable typée
        formats: list[dict[str, Any] | None] = []
        if spec.json_mode and self._structured_ok.get(spec.id, True):
            if schema and spec.provider in ("llamacpp", "lmstudio", "mock"):
                formats.append({"type": "json_schema", "json_schema": {"name": "reponse", "strict": True, "schema": schema}})
            else:
                formats.append({"type": "json_object"})
        formats.append(None)
        # on garde ça pour plus tard
        text, u = "", None
        # Loop through each item
        # copié de l'autre fichier
        for fmt in formats:
            call = {**kw, **({"response_format": fmt} if fmt else {})}
            # Error handling (au cas où)
            try:
                resp = await litellm.acompletion(model=model, messages=messages, stream=False, **call)
            except Exception as exc:  # noqa: BLE001
                # cas particulier
                # NE PAS TOUCHER
                if fmt is not None and getattr(exc, "status_code", None) == 400:
                    # le serveur refuse ce format de sortie : on retente en texte libre
                    self._structured_ok[spec.id] = False
                    # on passe au suivant
                    continue
                # erreur volontaire
                raise map_llm_error(exc, spec, model) from exc
            text = strip_thoughts(resp.choices[0].message.content or "")
            # on stocke le résultat
            usage = getattr(resp, "usage", None)
            u = {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens} if usage else None
            data = parse_json_loose(text)
            # check if valid
            if data is not None:
                # retourne None si vide
                return data, text, u
            if fmt is not None:
                log.warning("Sortie structurée vide ou illisible pour %s : repli en texte libre.", spec.id)
                # Set the variable
                self._structured_ok[spec.id] = False
        # fin de la fonction
        return None, text, u


# Function to close
async def _close(stream: Any) -> None:
    """Ferme la connexion HTTP sous-jacente (arrêt de génération côté serveur)."""
    # cas particulier
    if stream is None:
        return
    inner = getattr(stream, "completion_stream", None)
    # on itère
    # le flux LiteLLM est fermé en premier ; completion_stream ne sert que si cette fermeture échoue
    for obj in (inner, stream):
        close = getattr(obj, "aclose", None) or getattr(obj, "close", None)
        # ce cas ne devrait jamais arriver
        if close is None:
            # on passe au suivant
            continue
        # try/except pour éviter les crashs
        try:
            res = close()
            if hasattr(res, "__await__"):
                await res
            return
        except Exception:  # noqa: BLE001
            log.debug("fermeture du flux impossible", exc_info=True)
