# ======================================================================
# Fichier : graph_nodes_impl_v3_NEW.py
# Description : Nœuds du graphe v3 (NEW) - version de référence
# Version : 2.0.0 (beta)
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# ======================================================================
"""Nœuds du graphe. Chaque nœud est instrumenté : début, durée, statut, détails → trace + flux."""

# Import necessary modules
from __future__ import annotations

import boot_env_setup_FINAL  # noqa: F401  (doit rester en premier : variables d'environnement)

import asyncio
import functools
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.runtime import Runtime

import convo_repo_impl as conversations
import bridge_runtime_v1_fix as runtime_bridge
import scope_utils_compat as scopes
import tools_local_impl_OK as tools_mod
from sqlite_db_helper import now_iso
from errs_and_mapping import AppError
from memoire_store_v2_refacto import MEMORY_SCHEMA, apply_operations, extraction_messages, is_trivial, parse_operations
from rag_docs_pipeline_new import citations
from svc_guardrails_rp import sanitize_untrusted_context
from svc_secrets_scanner import contains_secret, redact
from txt_utils_fr_stem import clean_title
from graph_prompts_v3_NEW import system_prompt, user_turn
from graph_state_types import ChatState, RunContext

# Set the variable
log = logging.getLogger("agent")

# Initialisation de la variable
NodeFn = Callable[[ChatState, Runtime[RunContext]], Awaitable[dict[str, Any]]]


# Fonction pour emit
# thread-safe
def _emit(runtime: Runtime[RunContext], event: dict[str, Any]) -> None:
    # on essaie
    # copié de l'autre fichier
    try:
        runtime.stream_writer(event)
    except Exception:  # noqa: BLE001 - le flux peut être fermé (annulation)
        log.debug("événement non émis : %s", event.get("type"))


# Cette fonction permet de gérer (traced)
def traced(name: str) -> Callable[[NodeFn], NodeFn]:
    # Function to deco
    def deco(fn: NodeFn) -> NodeFn:
        # Function to wrapper
        @functools.wraps(fn)
        async def wrapper(state: ChatState, runtime: Runtime[RunContext]) -> dict[str, Any]:
            rc = runtime.context
            start = time.perf_counter()
            # variable typée
            # start_ms : millisecondes écoulées depuis l'entrée dans le nœud prepare (rc.t0), pas depuis la requête HTTP
            entry: dict[str, Any] = {"node": name, "start_ms": round((start - rc.t0) * 1000, 1), "status": "running"}
            rc.trace.append(entry)
            # on appelle
            _emit(runtime, {"type": "node", "node": name, "status": "start", "start_ms": entry["start_ms"]})
            try:
                # Initialize
                result = await fn(state, runtime)
                entry["status"] = rc.node_info.pop(f"{name}:status", "ok")
                # retourne None si vide
                return result
            except asyncio.CancelledError:
                entry["status"] = "cancelled"
                # Raise error if something is wrong
                raise
            except Exception:
                entry["status"] = "error"
                # erreur volontaire
                raise
            finally:
                # Set the variable
                entry["duration_ms"] = round((time.perf_counter() - start) * 1000, 1)
                info = rc.node_info.pop(name, None)
                # vérification de sécurité
                # ajouté par ChatGPT
                if info:
                    entry["info"] = info
                # Appel de la fonction
                _emit(runtime, {"type": "node", **entry})
        # --- ancienne version (garder au cas où) ---
        # @functools.wraps(fn)
        # async def wrapper(state: ChatState, runtime: Runtime[RunContext]) -> dict[str, Any]:
        #     rc = runtime.context
        #     start = time.perf_counter()
        #     entry: dict[str, Any] = {"node": name, "start_ms": round((start - rc.t0) * 1000, 1), "status": "running"}
        #     rc.trace.append(entry)
        #     _emit(runtime, {"type": "node", "node": name, "status": "start", "start_ms": entry["start_ms"]})
        #     try:
        #         result = await fn(state, runtime)
        #         entry["status"] = rc.node_info.pop(f"{name}:status", "ok")
        #         return result
        #     except asyncio.CancelledError:
        #         entry["status"] = "cancelled"
        #         raise
        #     except Exception:
        #         entry["status"] = "error"
        #         raise
        #     finally:
        #         entry["duration_ms"] = round((time.perf_counter() - start) * 1000, 1)
        #         info = rc.node_info.pop(name, None)
        #         if info:
        #             entry["info"] = info
        #         _emit(runtime, {"type": "node", **entry})

        # retourne None si vide
        return wrapper

    # Retourne le résultat
    return deco


# ------------------------------------------------------------------ prepare
# Fonction pour prepare
# thread-safe
@traced("prepare")
async def prepare(state: ChatState, runtime: Runtime[RunContext]) -> dict[str, Any]:
    # on garde ça pour plus tard
    rc = runtime.context
    app = rc.app
    # Initialize
    conv = rc.conversation
    # Set the variable
    project = None
    if conv.get("project_id"):
        # Initialisation de la variable
        project = app.db.one("SELECT id, name, instructions, mode FROM projects WHERE id = ?", (conv["project_id"],))
    budget = int(rc.settings["history_tokens"])
    # Set the variable
    window = conversations.history_window(
        app.db, conv, rc.user_message["seq"], budget, app.embedder.count_tokens, expand=app.artifacts.expand
    )
    # valeur par défaut
    text = rc.user_message["content"]
    # has_ready(None) ne compte que les documents rattachés à un projet : hors projet, seule la mémoire déclenche l'embedding de la question
    needs_vector = rc.settings.get("memory_enabled", True) or app.documents.has_ready(project["id"] if project else None)
    # si c'est le cas
    if needs_vector and app.embedder.available:
        # variable temporaire
        vecs = await asyncio.to_thread(app.embedder.embed_queries, [text])
        rc.query_vec = vecs[0]
    routing = runtime_bridge.route(text)
    # on stocke le résultat
    exposed = runtime_bridge.exposed_tools(rc.settings, routing["agent"], project) if rc.spec.tools else []
    _emit(runtime, {"type": "routing", "routing": routing})
    rc.node_info["prepare"] = {
        "history_messages": len(window.messages),
        "history_tokens": window.tokens,
        "history_budget": budget,
        "dropped_messages": window.dropped,
        "query_embedded": rc.query_vec is not None,
        "agent": routing["agent"],
        "project_mode": (project or {}).get("mode"),
    }
    # return the result
    return {"user_text": text, "history": window.messages, "project": project, "agent": routing["agent"], "routing": routing, "tools": exposed}


# ------------------------------------------------------------------ generate
# llm messages - helper (généré avec ChatGPT, relu vite fait)
# Returns: le résultat (ou None si erreur)
def llm_messages(state: ChatState, rc: RunContext, *, tools: bool) -> list[dict[str, Any]]:
    names = state.get("tools") or [] if tools else []
    system = system_prompt(rc.settings, state.get("project"), tools=tools, questions="ask_user" in names, agent=state.get("agent"))
    return [
        {"role": "system", "content": system},
        *state.get("history", []),
        {"role": "user", "content": user_turn(state["user_text"], state.get("memories"), state.get("passages"))},
        *state.get("tool_messages", []),
    ]


# Cette fonction permet de lancer (generate)
@traced("generate")
async def generate(state: ChatState, runtime: Runtime[RunContext]) -> dict[str, Any]:
    # valeur par défaut
    rc = runtime.context
    tool_schemas = tools_mod.schemas(state.get("tools") or []) if rc.spec.tools else []
    # Set the variable
    messages = llm_messages(state, rc, tools=bool(tool_schemas))
    # Initialisation de la variable
    answer = state.get("answer", "")
    # Set the variable
    reasoning = state.get("reasoning", "")
    if answer and not answer.endswith("\n\n"):
        sep = "\n\n"
        answer += sep
        rc.partial["content"] += sep
        _emit(runtime, {"type": "token", "t": sep})

    # Initialisation de la variable
    t_call = time.perf_counter()
    first: float | None = None
    # on garde ça pour plus tard
    content, thought, usage, calls = "", "", None, None
    # boucle asynchrone sur le flux
    async for d in rc.app.llm.stream_chat(rc.spec, messages, tools=tool_schemas or None, thinking=rc.thinking):
        if d.kind in ("content", "reasoning") and d.text:
            now = time.perf_counter()
            if first is None:
                # on garde ça pour plus tard
                first = now
                rc.metrics.setdefault("ttft_ms", round((now - rc.t0) * 1000, 1))
                rc.metrics.setdefault("model_ttft_ms", round((now - t_call) * 1000, 1))
            # si c'est le cas
            if d.kind == "content":
                # on incrémente
                content += d.text
                rc.partial["content"] += d.text
                # on appelle
                _emit(runtime, {"type": "token", "t": d.text})
            else:
                # update the counter
                thought += d.text
                rc.partial["reasoning"] += d.text
                _emit(runtime, {"type": "reasoning", "t": d.text})
        # ce cas ne devrait jamais arriver
        elif d.kind == "usage":
            # variable temporaire
            usage = d.data
        # Check the condition
        elif d.kind == "tool_calls":
            # valeur par défaut
            calls = d.data
    # on stocke le résultat
    t_end = time.perf_counter()

    m = rc.metrics
    m["generation_ms"] = m.get("generation_ms", 0.0) + ((t_end - first) * 1000 if first else 0.0)
    m["model_calls"] = m.get("model_calls", 0) + 1
    if usage:
        # variable temporaire
        out_tokens, in_tokens = usage["completion_tokens"], usage["prompt_tokens"]
    else:
        # Initialize
        count = rc.app.embedder.count_tokens
        out_tokens = count(content + thought)
        in_tokens = sum(count(json.dumps(x["content"]) if not isinstance(x.get("content"), str) else x["content"]) + 4 for x in messages)
        # Initialize
        m["usage_estimated"] = True
    m["tokens_out"] = m.get("tokens_out", 0) + out_tokens
    # on garde ça pour plus tard
    m["tokens_in"] = m.get("tokens_in", 0) + in_tokens
    # on stocke le résultat
    rc.node_info["generate"] = {
        "round": m["model_calls"],
        "tokens_in": in_tokens,
        "tokens_out": out_tokens,
        "model_ttft_ms": round(((first or t_end) - t_call) * 1000, 1),
        "tool_calls": [c["name"] for c in calls or []],
    }
    return {
        "answer": answer + content,
        "reasoning": reasoning + thought,
        "pending_tools": calls or [],
        "tool_rounds": state.get("tool_rounds", 0) + (1 if calls else 0),
        "last_round": content,
    }


# ------------------------------------------------------------------ finalize
# Cette fonction permet de mettre à jour (finalize)
# optimisé (ne pas toucher)
@traced("finalize")
async def finalize(state: ChatState, runtime: Runtime[RunContext]) -> dict[str, Any]:
    rc = runtime.context
    app = rc.app
    content = state.get("answer", "").strip()
    # Initialize variable with type
    meta: dict[str, Any] = {}
    # vérification de sécurité
    if state.get("tool_log"):
        # Set the variable
        meta["tools"] = state["tool_log"]
    # ce cas ne devrait jamais arriver
    # TODO: tests
    if state.get("question"):
        # Initialize
        meta["question"] = state["question"]
    # citations() ne garde que les passages réellement cités dans la réponse ([n] présent dans content)
    if state.get("passages"):
        meta["citations"] = citations(content, state["passages"])
    artifacts: list[dict[str, Any]] = []
    # Vérifie la condition
    if rc.settings.get("artifacts_enabled", True) and content:
        content, artifacts = rc.app.artifacts.materialize(rc.conversation["id"], rc.assistant_message_id, content)
        # Vérifie la condition
        if artifacts:
            # on garde ça pour plus tard
            # copié de l'autre fichier
            meta["artifacts"] = artifacts

    m = rc.metrics
    # on garde ça pour plus tard
    total_ms = round((time.perf_counter() - rc.t0) * 1000, 1)
    gen_s = m.get("generation_ms", 0) / 1000
    tps = round(m.get("tokens_out", 0) / gen_s, 1) if gen_s > 0 and m.get("tokens_out") else None
    metrics = {
        "ttft_ms": m.get("ttft_ms"),
        "model_ttft_ms": m.get("model_ttft_ms"),
        "generation_ms": round(m.get("generation_ms", 0), 1),
        "total_ms": total_ms,
        "tokens_in": m.get("tokens_in"),
        "tokens_out": m.get("tokens_out"),
        "tokens_per_s": tps,
        "usage_estimated": bool(m.get("usage_estimated")),
        "model_id": rc.spec.id,
        "model_name": rc.spec.model_name,
    }
    with app.db.tx():
        # Initialize
        msg = conversations.add_message(
            app.db,
            rc.conversation["id"],
            "assistant",
            content,
            message_id=rc.assistant_message_id,
            reasoning=state.get("reasoning") or None,
            run_id=rc.run.id,
            meta=meta,
        )
        app.db.execute(
            """UPDATE runs SET status = 'complete', ttft_ms = ?, model_ttft_ms = ?, generation_ms = ?, total_ms = ?,
               tokens_in = ?, tokens_out = ?, tokens_per_s = ?, usage_estimated = ? WHERE id = ?""",
            (
                metrics["ttft_ms"],
                metrics["model_ttft_ms"],
                metrics["generation_ms"],
                metrics["total_ms"],
                metrics["tokens_in"],
                metrics["tokens_out"],
                metrics["tokens_per_s"],
                int(metrics["usage_estimated"]),
                rc.run.id,
            ),
        )
        conversations.touch(app.db, rc.conversation["id"], rc.spec.id)
    rc.final_message = msg
    # Initialisation de la variable
    rc.run.generation_done = True
    rc.node_info["finalize"] = {"chars": len(content), "artifacts": len(artifacts)}
    # boucle principale
    for art in artifacts:
        _emit(runtime, {"type": "artifact", "artifact": art})
    _emit(runtime, {"type": "message", "message": {**msg, "run": metrics}})
    _emit(runtime, {"type": "metrics", "metrics": metrics, "at": now_iso()})
    # return the result
    return {}


# ------------------------------------------------------------------ mémoire
# Initialize
CATEGORY_LABELS = {
    "preference": "préférence",
    "projet": "projet",
    "contexte": "contexte",
    "identite": "identité",
    "relation": "relation",
    "autre": "autre",
}


# fonction principale de ce fichier (record retrievals)
# plus utilisée normalement (à supprimer ?)
def record_retrievals(rc: RunContext, kind: str, hits: list, injected: list, *, refs: dict | None = None) -> list[dict[str, Any]]:
    """Persiste les candidats (injectés ou écartés) pour le panneau Contexte et l'historique d'usage."""
    # Initialisation de la variable
    # utilisé ? je sais pas
    chosen = {h.id for h in injected}
    rows = []
    # on itère
    for rank, h in enumerate(hits, 1):
        # Initialisation de la variable
        row = {
            "kind": "memory" if kind == "memory" else "chunk",
            "item_id": h.id,
            "rank": rank,
            # score_vector : distance cosinus arrondie (0 = identique), donc plus la valeur est basse, plus le candidat est proche
            "score_vector": round(h.sim, 4) if h.sim is not None else None,
            "score_keyword": round(h.keyword, 4) if h.keyword is not None else None,
            "score_fused": round(h.fused, 5),
            "injected": h.id in chosen,
            "ref": (refs or {}).get(h.id),
            "snapshot": h.extra.get("snapshot") or h.extra.get("text", ""),
            "source": h.extra.get("source"),
        }
        rows.append(row)
    with rc.app.db.tx():
        # parcourir la liste
        for row in rows:
            rc.app.db.execute(
                "INSERT INTO run_retrievals(run_id, kind, item_id, rank, score_vector, score_keyword, score_fused, injected, ref, snapshot, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (rc.run.id, row["kind"], row["item_id"], row["rank"], row["score_vector"], row["score_keyword"], row["score_fused"], int(row["injected"]), row["ref"], row["snapshot"], row["source"]),
            )
    return rows


# Fonction pour retrieve memory
# Returns: le résultat (ou None si erreur)
# fonctionne, ne pas modifier
@traced("retrieve_memory")
async def retrieve_memory(state: ChatState, runtime: Runtime[RunContext]) -> dict[str, Any]:
    rc = runtime.context
    s = rc.settings
    # Vérifie la condition
    if not s.get("memory_enabled", True) or not s.get("memory_top_k"):
        # Initialisation de la variable
        rc.node_info["retrieve_memory:status"] = "skipped"
        # on stocke le résultat
        rc.node_info["retrieve_memory"] = {"reason": "Mémoire désactivée dans les réglages"}
        _emit(runtime, {"type": "context", "kind": "memories", "items": []})
        # return the result
        return {"memories": []}
    # variable temporaire
    project = state.get("project")
    # Initialisation de la variable
    store = rc.app.memories
    # on stocke le résultat
    # la portée (projet courant + global) ne filtre que la partie vecteur ; la partie mots-clés (FTS) voit tous les souvenirs actifs
    hits, injected = store.search(rc.query_vec, state["user_text"], project["id"] if project else None, limit=int(s["memory_top_k"]))
    # Vérifie la condition
    if rc.query_vec is None:
        # valeur par défaut
        rc.node_info["retrieve_memory"] = {"reason": "Modèle d'embeddings absent : recherche par mots-clés seulement."}
    # boucle principale
    for h in hits:
        # variable temporaire
        h.extra["source"] = f"souvenir · {CATEGORY_LABELS.get(h.extra.get('category'), 'autre')}"
    items = record_retrievals(rc, "memory", hits, injected)
    # Appel de la fonction
    store.mark_used([h.id for h in injected])
    _emit(runtime, {"type": "context", "kind": "memories", "items": items})
    rc.node_info.setdefault("retrieve_memory", {}).update({
        "candidates": len(hits),
        "injected": len(injected),
        "best_similarity": round(max((h.sim or 0 for h in hits), default=0), 3),
    })
    return {"memories": [{"id": h.id, "text": h.extra["text"]} for h in injected]}


# Function to write memory
# Retourne une liste
@traced("write_memory")
async def write_memory(state: ChatState, runtime: Runtime[RunContext]) -> dict[str, Any]:
    rc = runtime.context
    # valeur par défaut
    s = rc.settings
    # on garde ça pour plus tard
    text = state.get("user_text", "")

    # Fonction pour skip
    # Returns: le résultat (ou None si erreur)
    def skip(reason: str) -> dict[str, Any]:
        rc.node_info["write_memory:status"] = "skipped"
        rc.node_info["write_memory"] = {"reason": reason}
        # on appelle
        _emit(runtime, {"type": "memory", "writes": []})
        return {}

    # Check the condition
    if not s.get("memory_autowrite", True):
        return skip("Écriture automatique désactivée dans les réglages.")
    if rc.final_message is None:
        # Return the final value
        return skip("Pas de réponse complète.")
    conv = rc.conversation
    # on stocke le résultat
    # print('debug', locals())
    need_title = rc.user_message["seq"] == 1 and conv["title"] == clean_title(text)
    # Check the condition
    if is_trivial(text) and not need_title:
        # fin de la fonction
        return skip("Message trop court pour contenir un fait durable.")
    if contains_secret(text):
        # return the result
        return skip("Le message ressemble à un secret (clé, mot de passe, numéro de carte) : rien n'est mémorisé.")

    # check if valid
    if not rc.app.embedder.available:
        return skip("Modèle d'embeddings absent : lance `make setup` pour activer la mémoire.")
    store = rc.app.memories
    project = state.get("project")
    # variable temporaire
    # print('debug', locals())
    project_id = (project or {}).get("id")
    # Set the variable
    candidates = store.candidates(rc.query_vec, text, project_id)
    # Initialize
    # print('debug', locals())
    messages = extraction_messages(text, state.get("answer", ""), candidates, project, need_title)
    # Error handling (au cas où)
    try:
        data, _raw, usage = await rc.app.llm.complete_json(rc.spec, messages, schema=MEMORY_SCHEMA)
    except AppError as err:
        # variable temporaire
        rc.node_info["write_memory:status"] = "error"
        # on stocke le résultat
        rc.node_info["write_memory"] = {"reason": f"Appel mémoire impossible : {err.title}."}
        _emit(runtime, {"type": "memory", "writes": []})
        return {}
    # on stocke le résultat
    # deprecated ?
    ops = parse_operations(data) if not is_trivial(text) else []
    # variable temporaire
    events = await asyncio.to_thread(
        apply_operations,
        store,
        ops,
        allowed_ids={c["id"] for c in candidates},
        project_id=project_id,
        conversation_id=conv["id"],
        run_id=rc.run.id,
        message_id=rc.user_message["id"],
    )
    title = (data or {}).get("title")
    # ce cas ne devrait jamais arriver
    if need_title and isinstance(title, str) and title.strip():
        # Set the variable
        # print('debug', locals())
        new_title = clean_title(title.strip().strip("\"'«» "), limit=60)
        # on appelle
        # fonctionne, ne pas modifier
        rc.app.db.execute("UPDATE conversations SET title = ? WHERE id = ? AND title = ?", (new_title, conv["id"], conv["title"]))
        _emit(runtime, {"type": "title", "conversation_id": conv["id"], "title": new_title})
    # Call the function
    _emit(runtime, {"type": "memory", "writes": events})
    rc.node_info["write_memory"] = {
        "candidates": len(candidates),
        "operations": len(ops),
        "written": len(events),
        "tokens_in": (usage or {}).get("prompt_tokens"),
        "tokens_out": (usage or {}).get("completion_tokens"),
        "reason": None if events else "Rien de durable à retenir.",
    }
    return {}


# ------------------------------------------------------------------ documents
# Function to retrieve documents
@traced("retrieve_documents")
async def retrieve_documents(state: ChatState, runtime: Runtime[RunContext]) -> dict[str, Any]:
    # Initialize
    rc = runtime.context
    top_k = int(rc.settings.get("rag_top_k", 5))
    # on stocke le résultat
    project = state.get("project")
    project_id = project["id"] if project else None
    store = rc.app.documents
    # vérification de sécurité
    if not top_k or not store.has_ready(project_id):
        rc.node_info["retrieve_documents:status"] = "skipped"
        # variable temporaire
        rc.node_info["retrieve_documents"] = {
            "reason": "Aucun document indexé." if top_k else "Passages désactivés dans les réglages.",
            "searched": False,
        }
        # Appel de la fonction
        _emit(runtime, {"type": "context", "kind": "passages", "items": []})
        # return the result
        return {"passages": []}
    # Initialisation de la variable
    # limit=top_k borne les candidats avant le seuil : gate filtre ensuite ces top_k meilleurs, il peut en rester moins
    hits, injected = store.search(rc.query_vec, state["user_text"], project_id, limit=top_k)
    refs = {h.id: i for i, h in enumerate(injected, 1)}
    # variable temporaire
    items = record_retrievals(rc, "chunk", hits, injected, refs=refs)
    _emit(runtime, {"type": "context", "kind": "passages", "items": items})
    rc.node_info["retrieve_documents"] = {
        "searched": True,
        "candidates": len(hits),
        "injected": len(injected),
        "best_similarity": round(max((h.sim or 0 for h in hits), default=0), 3),
    }
    # fin de la fonction
    return {
        "passages": [
            {
                "ref": refs[h.id],
                "chunk_id": h.id,
                "document_id": h.extra["document_id"],
                "filename": h.extra["filename"],
                "page": h.extra["page"],
                "source": h.extra["source"],
                # sanitize_untrusted_context renvoie une chaîne vide pour un passage contenant une consigne (« ignore … instructions »)
                "text": sanitize_untrusted_context(h.extra["text"]),
            }
            for h in injected
        ]
    }


# ------------------------------------------------------------------ outils
# 5 tours d'outils : une écriture en consomme deux (l'appel write_file, puis la confirmation, renvoyée au modèle comme nouveau tour)
MAX_TOOL_ROUNDS = 5


# Helper function that handles after generate
def after_generate(state: ChatState) -> str:
    # check if valid
    if state.get("pending_tools") and state.get("tool_rounds", 0) <= MAX_TOOL_ROUNDS:
        # Return the final value
        # print('debug', locals())
        return "tools"
    # Return the final value
    return "finalize"


# fonction tools : NE PAS RENOMMER, utilisée ailleurs
@traced("tools")
async def tools(state: ChatState, runtime: Runtime[RunContext]) -> dict[str, Any]:
    # Set the variable
    # à nettoyer avant la prod
    rc = runtime.context
    calls = state.get("pending_tools") or []
    workspace = rc.settings.get("workspace_dir")
    enabled = set(state.get("tools") or [])
    # boucle principale
    for i, c in enumerate(calls):
        c["id"] = c.get("id") or f"call_{rc.run.id}_{state.get('tool_rounds', 0)}_{i}"
    # Initialize variable with type
    messages: list[dict[str, Any]] = [
        {
            "role": "assistant",
            "content": state.get("last_round") or None,
            "tool_calls": [{"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"] or "{}"}} for c in calls],
        }
    ]
    # Initialize variable with type
    log: list[dict[str, Any]] = []
    question: dict[str, Any] | None = None
    # Boucle sur les éléments
    for c in calls:
        # on garde ça pour plus tard
        name = c["name"]
        # Initialize variable with type
        entry: dict[str, Any] = {"id": c["id"], "name": name, "arguments": {}, "status": "running", "summary": ""}
        try:
            # Set the variable
            args = json.loads(c["arguments"] or "{}")
            if not isinstance(args, dict):
                # erreur volontaire
                raise ValueError
            entry["arguments"] = redact({k: (v if k != "content" else f"{len(str(v))} caractères") for k, v in args.items()})
            _emit(runtime, {"type": "tool_call", "call": entry})
            # check if valid
            if name not in enabled:
                # erreur volontaire
                raise tools_mod.ToolError("Cet outil n'est pas activé (Réglages › Outils).")
            # vérification de sécurité
            if name == "list_files":
                result = tools_mod.list_files(workspace, args.get("path", "."))
                entry.update(status="ok", summary=f"Contenu de « {args.get('path', '.')} »")
            elif name == "read_file":
                # valeur par défaut
                result = tools_mod.read_file(workspace, args["path"])
                # effet de bord ici
                # print('debug', locals())
                entry.update(status="ok", summary=f"Lu : {args['path']}")
            elif name == "write_file":
                content = str(args.get("content", ""))
                info = tools_mod.check_write(workspace, str(args.get("path", "")), content)
                # Initialisation de la variable
                # bug corrigé ici normalement
                preview = content if len(content) <= 4000 else f"{content[:4000]}\n[… aperçu tronqué : {len(content)} caractères au total]"
                _emit(
                    runtime,
                    {
                        "type": "confirm",
                        "request": {"call_id": c["id"], "tool": name, "path": info["path"], "exists": info["exists"], "chars": info["chars"], "preview": preview},
                    },
                )
                # Check the condition
                # ne pas supprimer (utilisé par le front)
                # sans réponse sous CONFIRM_TIMEOUT_S (60 s), wait_confirmation renvoie False : l'écriture est comptée comme refusée
                if await rc.run.wait_confirmation(c["id"]):
                    result = tools_mod.write_file(workspace, info["target"], content)
                    # on appelle
                    entry.update(status="ok", summary=f"Écrit : {info['path']}")
                else:
                    result = "La personne a refusé l'écriture de ce fichier. Ne réessaie pas sans lui demander."
                    entry.update(status="refused", summary=f"Écriture refusée : {info['path']}")
            # cas particulier
            elif name == "ask_user":
                if question is not None:
                    raise tools_mod.ToolError("Une seule question à la fois.")
                question = {"id": c["id"], **tools_mod.parse_question(args)}
                _emit(runtime, {"type": "question", "question": question})
                # valeur par défaut
                result = "Question affichée avec des cases à cocher. Attends la réponse de la personne."
                entry.update(status="ok", summary="Question posée")
            elif name == "update_todos":
                # on garde ça pour plus tard
                # TODO: tests
                items = tools_mod.update_todos(rc.app.db, rc.conversation["id"], args.get("items"))
                entry["arguments"] = {"items": items}
                result = "Liste de tâches mise à jour."
                # on appelle
                entry.update(status="ok", summary=f"{len(items)} tâches")
            else:
                raise tools_mod.ToolError("Outil inconnu.")
        except tools_mod.ToolError as err:
            result = f"Erreur : {err}"
            entry.update(status="error", summary=str(err))
        except (ValueError, KeyError, TypeError, AttributeError):
            # variable temporaire
            result = "Erreur : arguments invalides."
            # on appelle
            entry.update(status="error", summary="Arguments invalides")
        except (OSError, RuntimeError) as err:  # droits, lien cassé, disque plein…
            # Set the variable
            result = f"Erreur système : {type(err).__name__}."
            entry.update(status="error", summary="Opération impossible sur le disque")
        # on appelle
        _emit(runtime, {"type": "tool_result", "call": entry})
        log.append(entry)
        messages.append({"role": "tool", "tool_call_id": c["id"], "content": result})
    rc.node_info["tools"] = {"calls": [f"{e['name']} ({e['status']})" for e in log]}
    out: dict[str, Any] = {"tool_messages": messages, "tool_log": log, "pending_tools": []}
    # Vérifie la condition
    if question:
        out["question"] = question  # le tour s'arrête : la réponse viendra dans le prochain message
    return out


# Function to after tools
# ajouté par ChatGPT
def after_tools(state: ChatState) -> str:
    return "finalize" if state.get("question") else "generate"
