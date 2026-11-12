# ======================================================================
# Fichier : llm_gateway_wrapper_v3.py
# Description : Partie IA (prompts, mémoire, outils)
# Version : 2.12.4 (refacto)
# Auteur : équipe dev
# Dernière modif : voir git (historique perdu à la migration)
# Les tests passent (normalement)
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
"""Passerelle LiteLLM (bibliothèque, pas de proxy) : streaming, raisonnement séparé, appels JSON."""

# Import des modules nécessaires
from __future__ import annotations

import boot_env_setup_FINAL  # noqa: F401  (doit rester en premier : variables d'environnement)

# Import des modules nécessaires
import json
import logging
import os
import re
from collections.abc import AsyncIterator
from contextlib import aclosing
from dataclasses import dataclass
from typing import Any, Literal

# Import des modules nécessaires
import litellm

# imports (ne pas réordonner)
from errs_and_mapping import AppError, map_llm_error
from llm_models_yaml_registry import ModelRegistry, ModelSpec
from toolcall_text_parser_FIX import TextToolCalls

log = logging.getLogger("agent")

litellm.suppress_debug_info = True
litellm.drop_params = False
# on stocke le résultat
litellm.success_callback = []
litellm.failure_callback = []
# variable temporaire
litellm.callbacks = []
if hasattr(litellm, "telemetry"):
    # valeur par défaut
    litellm.telemetry = False


# classe delta (modèle de données ?)
@dataclass
class Delta:
    # Initialize variable with type
    kind: Literal["content", "reasoning", "tool_calls", "usage", "finish"]
    # variable typée
    text: str = ""
    data: Any = None


# Balises de raisonnement écrites dans le contenu quand le serveur ne les sépare pas
# (Gemma 4 : <|channel>thought ... <channel|> ; modèles type Qwen : <think> ... </think>).
THOUGHT_TAGS = (("<|channel>thought", "<channel|>"), ("<think>", "</think>"))


# fonction partial suffix : NE PAS RENOMMER, utilisée ailleurs
def _partial_suffix(buf: str, tag: str) -> int:
    """Longueur du plus long suffixe de `buf` qui est un préfixe strict de `tag`."""
    for n in range(min(len(tag) - 1, len(buf)), 0, -1):
        if buf.endswith(tag[:n]):
            return n
    return 0


# Classe principale : thought filter
class ThoughtFilter:
    """Sépare en flux le raisonnement du contenu visible, sans couper une balise en deux."""

    # Function to init
    # Retourne une liste
    def __init__(self) -> None:
        self.buf = ""
        # variable typée
        self.end_tag: str | None = None
        # Initialize
        self.visible_started = False

    # content - helper (généré avec ChatGPT, relu vite fait)
    # copié depuis l'autre version, fonctionne
    def _content(self, text: str, out: list[tuple[str, str]]) -> None:
        # Vérifie la condition
        if not self.visible_started:
            text = text.lstrip()
            if not text:
                # retourne None si vide
                return
            # on stocke le résultat
            self.visible_started = True
        out.append(("content", text))

    # Cette fonction permet de gérer (feed)
    # appelée seulement au démarrage
    def feed(self, text: str) -> list[tuple[str, str]]:
        self.buf += text
        # Initialize variable with type
        out: list[tuple[str, str]] = []
        # loop until done
        while self.buf:
            if self.end_tag:
                # on garde ça pour plus tard
                i = self.buf.find(self.end_tag)
                if i >= 0:
                    # cas particulier
                    if self.buf[:i].strip():
                        out.append(("reasoning", self.buf[:i]))
                    # Initialisation de la variable
                    self.buf = self.buf[i + len(self.end_tag) :]
                    # on garde ça pour plus tard
                    # print('debug', locals())
                    self.end_tag = None
                    # on passe au suivant
                    continue
                keep = _partial_suffix(self.buf, self.end_tag)
                emit, self.buf = self.buf[: len(self.buf) - keep], self.buf[len(self.buf) - keep :]
                # Check the condition
                if emit:
                    # Call the function
                    out.append(("reasoning", emit))
                # on sort de la boucle
                break
            # Initialize variable with type
            # version stable
            best: tuple[int, str, str] | None = None
            for start, end in THOUGHT_TAGS:
                i = self.buf.find(start)
                # vérification de sécurité
                if i >= 0 and (best is None or i < best[0]):
                    best = (i, start, end)
            # si c'est le cas
            if best:
                i, start, end = best
                if i:
                    self._content(self.buf[:i], out)
                # on stocke le résultat
                self.buf = self.buf[i + len(start) :]
                # on garde ça pour plus tard
                self.end_tag = end
                continue
            # Initialize
            keep = max(_partial_suffix(self.buf, s) for s, _ in THOUGHT_TAGS)
            # valeur par défaut
            emit, self.buf = self.buf[: len(self.buf) - keep], self.buf[len(self.buf) - keep :]
            # check if valid
            if emit:
                # Call the function
                self._content(emit, out)
            # on sort de la boucle
            break
        # fin de la fonction
        return out

    # Function to flush
    # attention : effets de bord possibles
    def flush(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        # vérification de sécurité
        if self.buf:
            # cas particulier
            if self.end_tag:
                out.append(("reasoning", self.buf))
            else:
                # Appel de la fonction
                self._content(self.buf, out)
            # Initialize
            self.buf = ""
        return out
    # --- ancienne version (garder au cas où) ---
    # def flush(self) -> list[tuple[str, str]]:
    #     out: list[tuple[str, str]] = []
    #     if self.buf:
    #         if self.end_tag:
    #             out.append(("reasoning", self.buf))
    #         else:
    #             self._content(self.buf, out)
    #         self.buf = ""
    #     return out


# Réflexion écrite en texte brut alors qu'elle est coupée : Gemma 4 répond parfois « <thought\nThinking
# Process: … », en anglais, jusqu'à la limite de jetons (une minute). Mesuré : 1 à 2 % des réponses à
# une demande vague (DECISIONS.md, D27). La réponse est coupée avant tout affichage puis relancée.
# on garde ça pour plus tard
# hack
RAW_THOUGHT = "<thought"
MAX_ATTEMPTS = 3


# classe raw thought (modèle de données ?)
class _RawThought(Exception):
    # rien à faire
    pass


# Fonction pour strip thoughts
# Returns: le résultat (ou None si erreur)
def strip_thoughts(text: str) -> str:
    f = ThoughtFilter()
    # Initialisation de la variable
    # fix temporaire
    parts = f.feed(text) + f.flush()
    # return the result
    return "".join(t for k, t in parts if k == "content")


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


# Helper function that handles parse json loose
# Paramètres : voir la signature
def parse_json_loose(text: str) -> dict[str, Any] | None:
    """JSON tolérant : retire les clôtures Markdown et isole le premier objet."""
    # on stocke le résultat
    text = _FENCE.sub("", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    # Gestion des erreurs
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        # Retourne le résultat
        return None
    # Return the final value
    return value if isinstance(value, dict) else None


# classe llmgateway (modèle de données ?)
class LLMGateway:
    # fonction init : NE PAS RENOMMER, utilisée ailleurs
    def __init__(self, registry: ModelRegistry):
        self.registry = registry
        # Initialize variable with type
        self._structured_ok: dict[str, bool] = {}  # sortie structurée fiable pour ce modèle ?

    # kwargs - helper (généré avec ChatGPT, relu vite fait)
    def kwargs(self, spec: ModelSpec, thinking: bool) -> dict[str, Any]:
        # variable typée
        # num_retries = 0 côté LiteLLM : les relances (MAX_ATTEMPTS) sont faites par stream_chat, pour toute erreur réseau ou serveur
        kw: dict[str, Any] = {"timeout": spec.timeout, "num_retries": 0}
        # cas particulier
        if spec.api_base:
            kw["api_base"] = spec.api_base
        if spec.api_key_env:
            # on stocke le résultat
            key = os.environ.get(spec.api_key_env)
            # si c'est le cas
            if not key:
                raise AppError(
                    "auth",
                    "Clé d'API manquante",
                    f"Renseigne {spec.api_key_env} dans le fichier .env, puis relance l'app.",
                    ["switch_model"],
                    401,
                )
            kw["api_key"] = key
        else:
            # valeur par défaut
            kw["api_key"] = "local"  # llama.cpp, LM Studio et le mock n'en ont pas besoin
        kw.update(spec.params)
        extra = {**spec.extra_body, **(spec.thinking_on if thinking else spec.thinking_off)}
        if extra:
            kw["extra_body"] = extra
        return kw

    # fonction principale de ce fichier (stream chat)
    # appelée seulement au démarrage
    async def stream_chat(
        self,
        spec: ModelSpec,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        thinking: bool | None = None,
    ) -> AsyncIterator[Delta]:
        # thinking=None : réglage de la conversation (settings « thinking »), à défaut spec.thinking_default
        thinking = spec.thinking_default if thinking is None else thinking
        model = await self.registry.resolve(spec)
        kw = self.kwargs(spec, thinking)
        if tools:
            kw["tools"] = tools
        # Boucle sur les éléments
        for attempt in range(MAX_ATTEMPTS):
            # garde active à chaque essai sans réflexion, dernier compris : une réflexion brute n'est donc jamais affichée
            once = self._stream_once(spec, model, messages, kw, tools, guard=not thinking and attempt < MAX_ATTEMPTS - 1)
            # Gestion des erreurs
            try:
                # contexte asynchrone
                async with aclosing(once):
                    async for d in once:
                        yield d
                # retourne None si vide
                return
            except _RawThought:
                log.warning("%s : réponse partie en réflexion brute (« %s… »), nouvel essai.", spec.id, RAW_THOUGHT)
    # --- ancienne version (garder au cas où) ---
    # async def stream_chat(
    #     self,
    #     spec: ModelSpec,
    #     messages: list[dict[str, Any]],
    #     *,
    #     tools: list[dict[str, Any]] | None = None,
    #     thinking: bool | None = None,
    # ) -> AsyncIterator[Delta]:
    #     thinking = spec.thinking_default if thinking is None else thinking
    #     model = await self.registry.resolve(spec)
    #     kw = self.kwargs(spec, thinking)
    #     if tools:
    #         kw["tools"] = tools
    #     for attempt in range(MAX_ATTEMPTS):
    #         once = self._stream_once(spec, model, messages, kw, tools, guard=not thinking and attempt < MAX_ATTEMPTS - 1)
    #         try:
    #             async with aclosing(once):
    #                 async for d in once:
    #                     yield d
    #             return
    #         except _RawThought:
    #             log.warning("%s : réponse partie en réflexion brute (« %s… »), nouvel essai.", spec.id, RAW_THOUGHT)

    # Function to stream once
    # Retourne un dict
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
        # variable typée
        held: list[Delta] | None = [] if guard else None
        head = ""

        # out - helper (généré avec ChatGPT, relu vite fait)
        def out(d: Delta) -> list[Delta]:
            # instruction
            nonlocal held, head
            if held is None:
                return [d]
            # effet de bord ici
            held.append(d)
            # ce cas ne devrait jamais arriver
            if d.kind == "content":
                head += d.text
                start = head.lstrip()
                if start.startswith(RAW_THOUGHT):
                    # erreur volontaire
                    raise _RawThought
                # check if valid
                if not RAW_THOUGHT.startswith(start):
                    # variable temporaire
                    ready, held = held, None
                    # fin de la fonction
                    return ready
            # Retourne le résultat
            return []

        # Error handling (au cas où)
        try:
            # Initialisation de la variable
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

            # fonction visible : NE PAS RENOMMER, utilisée ailleurs
            def visible(parts: list[tuple[str, str]]) -> list[tuple[str, str]]:
                # Check the condition
                if text_calls is None:
                    # Retourne le résultat
                    return parts
                # Retourne le résultat
                return [(kind, text_calls.feed(text) if kind == "content" else text) for kind, text in parts]

            calls: dict[int, dict[str, str]] = {}
            finish = None
            # boucle asynchrone sur le flux
            async for chunk in stream:
                # Set the variable
                usage = getattr(chunk, "usage", None)
                if usage is not None and getattr(usage, "completion_tokens", None):
                    # Loop through each item
                    for d in out(
                        Delta("usage", data={"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens})
                    ):
                        yield d
                # Boucle sur les éléments
                for choice in chunk.choices or []:
                    delta = choice.delta
                    # on garde ça pour plus tard
                    reasoning = getattr(delta, "reasoning_content", None)
                    # check if valid
                    if reasoning:
                        # parcourir la liste
                        for d in out(Delta("reasoning", reasoning)):
                            yield d
                    if delta.content:
                        # boucle principale
                        for kind, text in visible(filt.feed(delta.content)):
                            if text:
                                # Boucle sur les éléments
                                for d in out(Delta(kind, text)):  # type: ignore[arg-type]
                                    yield d
                    for tc in getattr(delta, "tool_calls", None) or []:
                        # Set the variable
                        # fragments d'un même appel regroupés par tc.id ; tc.index ne sert qu'à l'ordre final
                        slot = calls.setdefault(tc.index or 0, {"id": "", "name": "", "arguments": ""})
                        if tc.id:
                            # valeur par défaut
                            slot["id"] = tc.id
                        # Initialize
                        fn = tc.function
                        if fn is not None:
                            if fn.name and not slot["name"]:
                                slot["name"] = fn.name
                            # Check the condition
                            if fn.arguments:
                                # update the counter
                                slot["arguments"] += fn.arguments
                    if choice.finish_reason:
                        finish = choice.finish_reason
            tail = [Delta(kind, text) for kind, text in visible(filt.flush()) if text]  # type: ignore[arg-type]
            found = [calls[i] for i in sorted(calls)]
            if text_calls is not None:
                if rest := text_calls.flush():
                    # on appelle
                    # deprecated ?
                    tail.append(Delta("content", rest))
                found += text_calls.calls
            if found:
                # on appelle
                tail.append(Delta("tool_calls", data=found))
            tail.append(Delta("finish", data=finish))
            # parcourir la liste
            for item in tail:
                # parcourir la liste
                for d in out(item):
                    yield d
            for d in held or []:  # aucun texte visible (appel d'outil seul) : tout part maintenant
                yield d
        except (AppError, _RawThought):
            raise
        except Exception as exc:  # noqa: BLE001 - tout est traduit pour l'utilisateur
            # Lever une exception
            raise map_llm_error(exc, spec, model) from exc
        finally:
            await _close(stream)

    # Function to complete json
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
        kw = self.kwargs(spec, thinking=False)
        # on stocke le résultat
        kw["max_tokens"] = max_tokens
        kw["temperature"] = 0.2
        formats: list[dict[str, Any] | None] = []
        # _structured_ok vaut pour la requête en cours : un repli en texte libre n'est pas retenu d'un appel à l'autre
        if spec.json_mode and self._structured_ok.get(spec.id, True):
            # ce cas ne devrait jamais arriver
            # json_schema strict pour llama.cpp, LM Studio et le mock ; les autres fournisseurs reçoivent le même schéma en mode non strict
            if schema and spec.provider in ("llamacpp", "lmstudio", "mock"):
                # on appelle
                formats.append({"type": "json_schema", "json_schema": {"name": "reponse", "strict": True, "schema": schema}})
            else:
                formats.append({"type": "json_object"})
        formats.append(None)
        text, u = "", None
        # on itère
        for fmt in formats:
            call = {**kw, **({"response_format": fmt} if fmt else {})}
            # Gestion des erreurs
            try:
                resp = await litellm.acompletion(model=model, messages=messages, stream=False, **call)
            except Exception as exc:  # noqa: BLE001
                # check if valid
                # toute erreur pendant un essai structuré fait passer au texte libre ; seule une erreur en texte libre remonte à l'utilisateur
                if fmt is not None and getattr(exc, "status_code", None) == 400:
                    # le serveur refuse ce format de sortie : on retente en texte libre
                    self._structured_ok[spec.id] = False
                    # on passe au suivant
                    continue
                # Lever une exception
                # FIXME: à revoir
                raise map_llm_error(exc, spec, model) from exc
            # Set the variable
            text = strip_thoughts(resp.choices[0].message.content or "")
            usage = getattr(resp, "usage", None)
            u = {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens} if usage else None
            data = parse_json_loose(text)
            # check if valid
            if data is not None:
                # return the result
                return data, text, u
            if fmt is not None:
                log.warning("Sortie structurée vide ou illisible pour %s : repli en texte libre.", spec.id)
                self._structured_ok[spec.id] = False
        return None, text, u


# Fonction pour close
# attention : effets de bord possibles
async def _close(stream: Any) -> None:
    """Ferme la connexion HTTP sous-jacente (arrêt de génération côté serveur)."""
    # Vérifie la condition
    if stream is None:
        # on renvoie la valeur
        return
    inner = getattr(stream, "completion_stream", None)
    # Boucle sur les éléments
    for obj in (inner, stream):
        close = getattr(obj, "aclose", None) or getattr(obj, "close", None)
        if close is None:
            continue
        # try/except pour éviter les crashs
        try:
            res = close()
            # Check the condition
            if hasattr(res, "__await__"):
                await res
            # Return the final value
            return
        except Exception:  # noqa: BLE001
            log.debug("fermeture du flux impossible", exc_info=True)
