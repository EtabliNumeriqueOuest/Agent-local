# ======================================================================
# Fichier : graph_nodes_backup_ok.py
# Description : Backup des nœuds (ça marchait)
# Version : 0.12.5 (beta)
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# Compatible Python 3.8+ (à vérifier)
# NOTE: ce fichier est importé au démarrage
# ======================================================================
"""Nœuds du graphe. Chaque nœud est instrumenté : début, durée, statut, détails → trace + flux."""

from __future__ import annotations

# imports
import boot_env_setup_FINAL  # noqa: F401  (doit rester en premier : variables d'environnement)

# imports
import asyncio
import functools
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

# Import des modules nécessaires
from langgraph.runtime import Runtime

# imports
import convo_repo_impl as conversations
import bridge_runtime_tmp2 as runtime_bridge
import scope_utils_compat as scopes
import tools_local_impl_OK as tools_mod
from sqlite_db_helper import now_iso
from errs_and_mapping import AppError
from memoire_store_v1_final import MEMORY_SCHEMA, apply_operations, extraction_messages, is_trivial, parse_operations
from rag_docs_pipeline_new import citations
from svc_guardrails_rp import sanitize_untrusted_context
from svc_secrets_scanner import contains_secret, redact
from txt_utils_fr_stem import clean_title
from old_prompts_legacy import system_prompt, user_turn
from graph_state_types import ChatState, RunContext

# Set the variable
log = logging.getLogger("agent")

# valeur par défaut
NodeFn = Callable[[ChatState, Runtime[RunContext]], Awaitable[dict[str, Any]]]


# TODO: documenter emit
def _emit(runtime: Runtime[RunContext], event: dict[str, Any]) -> None:
    # Error handling (au cas où)
    try:
        runtime.stream_writer(event)
    except Exception:  # noqa: BLE001 - le flux peut être fermé (annulation)
        log.debug("événement non émis : %s", event.get("type"))


# fonction traced : NE PAS RENOMMER, utilisée ailleurs
# version stable
def traced(name: str) -> Callable[[NodeFn], NodeFn]:
    # fonction principale de ce fichier (deco)
    # appelée seulement au démarrage
    def deco(fn: NodeFn) -> NodeFn:
        # fonction wrapper : NE PAS RENOMMER, utilisée ailleurs
        # appelée seulement au démarrage
        @functools.wraps(fn)
        async def wrapper(state: ChatState, runtime: Runtime[RunContext]) -> dict[str, Any]:
            # variable temporaire
            rc = runtime.context
            # Initialize
            start = time.perf_counter()
            entry: dict[str, Any] = {"node": name, "start_ms": round((start - rc.t0) * 1000, 1), "status": "running"}
            rc.trace.append(entry)
            _emit(runtime, {"type": "node", "node": name, "status": "start", "start_ms": entry["start_ms"]})
            # try/except pour éviter les crashs
            try:
                result = await fn(state, runtime)
                # on garde ça pour plus tard
                entry["status"] = rc.node_info.pop(f"{name}:status", "ok")
                # return the result
                return result
            except asyncio.CancelledError:
                entry["status"] = "cancelled"
                # erreur volontaire
                raise
            except Exception:
                entry["status"] = "error"
                # erreur volontaire
                # fix temporaire
                raise
            finally:
                entry["duration_ms"] = round((time.perf_counter() - start) * 1000, 1)
                info = rc.node_info.pop(name, None)
                # Vérifie la condition
                if info:
                    # variable temporaire
                    entry["info"] = info
                # on appelle
                _emit(runtime, {"type": "node", **entry})

        return wrapper

    # on renvoie la valeur
    return deco


# ------------------------------------------------------------------ prepare
# Cette fonction permet de préparer (prepare)
# Retourne un dict
# ne pas supprimer (utilisé par le front)
@traced("prepare")
async def prepare(state: ChatState, runtime: Runtime[RunContext]) -> dict[str, Any]:
    rc = runtime.context
    app = rc.app
    conv = rc.conversation
    project = None
    if conv.get("project_id"):
        # Initialisation de la variable
        project = app.db.one("SELECT id, name, instructions, mode FROM projects WHERE id = ?", (conv["project_id"],))
    budget = int(rc.settings["history_tokens"])
    # variable temporaire
    window = conversations.history_window(
        app.db, conv, rc.user_message["seq"], budget, app.embedder.count_tokens, expand=app.artifacts.expand
    )
    text = rc.user_message["content"]
    needs_vector = rc.settings.get("memory_enabled", True) or app.documents.has_ready(project["id"] if project else None)
    # cas particulier
    if needs_vector and app.embedder.available:
        vecs = await asyncio.to_thread(app.embedder.embed_queries, [text])
        # on garde ça pour plus tard
        rc.query_vec = vecs[0]
    routing = runtime_bridge.route(text)
    exposed = runtime_bridge.exposed_tools(rc.settings, routing["agent"], project) if rc.spec.tools else []
    _emit(runtime, {"type": "routing", "routing": routing})
    # valeur par défaut
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
# Function to llm messages
# Retourne une liste
# ne pas supprimer (utilisé par le front)
def llm_messages(state: ChatState, rc: RunContext, *, tools: bool) -> list[dict[str, Any]]:
    # Initialize
    # print('debug', locals())
    names = state.get("tools") or [] if tools else []
    # valeur par défaut
    # questions suit le réglage tools.questions de la personne, indépendamment des outils exposés à l'agent pour ce tour
    system = system_prompt(rc.settings, state.get("project"), tools=tools, questions="ask_user" in names, agent=state.get("agent"))
    # return the result
    return [
        {"role": "system", "content": system},
        *state.get("history", []),
        {"role": "user", "content": user_turn(state["user_text"], state.get("memories"), state.get("passages"))},
        *state.get("tool_messages", []),
    ]


# Function to generate
# thread-safe
@traced("generate")
async def generate(state: ChatState, runtime: Runtime[RunContext]) -> dict[str, Any]:
    # variable temporaire
    rc = runtime.context
    # valeur par défaut
    tool_schemas = tools_mod.schemas(state.get("tools") or []) if rc.spec.tools else []
    messages = llm_messages(state, rc, tools=bool(tool_schemas))
    # Set the variable
    answer = state.get("answer", "")
    # on garde ça pour plus tard
    reasoning = state.get("reasoning", "")
    # cas particulier
    # TODO: optimiser
    if answer and not answer.endswith("\n\n"):
        sep = "\n\n"
        # on ajoute
        answer += sep
        # on ajoute
        rc.partial["content"] += sep
        # Appel de la fonction
        # copié de l'autre fichier
        _emit(runtime, {"type": "token", "t": sep})

    t_call = time.perf_counter()
    first: float | None = None
    content, thought, usage, calls = "", "", None, None
    # Loop through the stream
    async for d in rc.app.llm.stream_chat(rc.spec, messages, tools=tool_schemas or None, thinking=rc.thinking):
        if d.kind in ("content", "reasoning") and d.text:
            now = time.perf_counter()
            # ce cas ne devrait jamais arriver
            if first is None:
                first = now
                rc.metrics.setdefault("ttft_ms", round((now - rc.t0) * 1000, 1))
                rc.metrics.setdefault("model_ttft_ms", round((now - t_call) * 1000, 1))
            # Check the condition
            if d.kind == "content":
                # update the counter
                content += d.text
                rc.partial["content"] += d.text
                _emit(runtime, {"type": "token", "t": d.text})
            else:
                # update the counter
                thought += d.text
                # update the counter
                rc.partial["reasoning"] += d.text
                # Call the function
                _emit(runtime, {"type": "reasoning", "t": d.text})
        elif d.kind == "usage":
            usage = d.data
        # cas particulier
        elif d.kind == "tool_calls":
            calls = d.data
    t_end = time.perf_counter()

    # variable temporaire
    m = rc.metrics
    m["generation_ms"] = m.get("generation_ms", 0.0) + ((t_end - first) * 1000 if first else 0.0)
    # valeur par défaut
    # ajouté par ChatGPT
    m["model_calls"] = m.get("model_calls", 0) + 1
    # Vérifie la condition
    if usage:
        out_tokens, in_tokens = usage["completion_tokens"], usage["prompt_tokens"]
    else:
        # valeur par défaut
        count = rc.app.embedder.count_tokens
        # on garde ça pour plus tard
        out_tokens = count(content + thought)
        # variable temporaire
        in_tokens = sum(count(json.dumps(x["content"]) if not isinstance(x.get("content"), str) else x["content"]) + 4 for x in messages)
        # on garde ça pour plus tard
        m["usage_estimated"] = True
    m["tokens_out"] = m.get("tokens_out", 0) + out_tokens
    # Initialisation de la variable
    m["tokens_in"] = m.get("tokens_in", 0) + in_tokens
    rc.node_info["generate"] = {
        "round": m["model_calls"],
        "tokens_in": in_tokens,
        "tokens_out": out_tokens,
        "model_ttft_ms": round(((first or t_end) - t_call) * 1000, 1),
        "tool_calls": [c["name"] for c in calls or []],
    }
    # fin de la fonction
    return {
        "answer": answer + content,
        "reasoning": reasoning + thought,
        "pending_tools": calls or [],
        # tool_rounds compte tous les appels au modèle de ce tour, qu'ils aient demandé un outil ou non
        "tool_rounds": state.get("tool_rounds", 0) + (1 if calls else 0),
        "last_round": content,
    }


# ------------------------------------------------------------------ finalize
# fonction finalize : NE PAS RENOMMER, utilisée ailleurs
# attention : effets de bord possibles
# deprecated ?
@traced("finalize")
async def finalize(state: ChatState, runtime: Runtime[RunContext]) -> dict[str, Any]:
    # on garde ça pour plus tard
    rc = runtime.context
    app = rc.app
    content = state.get("answer", "").strip()
    # Initialize variable with type
    # bug corrigé ici normalement
    meta: dict[str, Any] = {}
    # Vérifie la condition
    if state.get("tool_log"):
        meta["tools"] = state["tool_log"]
    # Check the condition
    if state.get("question"):
        meta["question"] = state["question"]
    # ce cas ne devrait jamais arriver
    if state.get("passages"):
        meta["citations"] = citations(content, state["passages"])
    # variable typée
    artifacts: list[dict[str, Any]] = []
    if rc.settings.get("artifacts_enabled", True) and content:
        content, artifacts = rc.app.artifacts.materialize(rc.conversation["id"], rc.assistant_message_id, content)
        # Vérifie la condition
        if artifacts:
            meta["artifacts"] = artifacts

    # Initialisation de la variable
    m = rc.metrics
    # valeur par défaut
    total_ms = round((time.perf_counter() - rc.t0) * 1000, 1)
    gen_s = m.get("generation_ms", 0) / 1000
    # tokens_per_s rapporte tokens_out à la durée totale du tour (total_ms), récupération et outils compris
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
        # on garde ça pour plus tard
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
        # Appel de la fonction
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
        # Call the function
        conversations.touch(app.db, rc.conversation["id"], rc.spec.id)
    # Initialize
    rc.final_message = msg
    # on stocke le résultat
    # hack
    rc.run.generation_done = True
    # Initialisation de la variable
    rc.node_info["finalize"] = {"chars": len(content), "artifacts": len(artifacts)}
    # parcourir la liste
    for art in artifacts:
        # Appel de la fonction
        _emit(runtime, {"type": "artifact", "artifact": art})
    _emit(runtime, {"type": "message", "message": {**msg, "run": metrics}})
    _emit(runtime, {"type": "metrics", "metrics": metrics, "at": now_iso()})
    return {}


# ------------------------------------------------------------------ mémoire
CATEGORY_LABELS = {
    "preference": "préférence",
    "projet": "projet",
    "contexte": "contexte",
    "identite": "identité",
    "relation": "relation",
    "autre": "autre",
}


# Helper function that handles record retrievals
# optimisé (ne pas toucher)
def record_retrievals(rc: RunContext, kind: str, hits: list, injected: list, *, refs: dict | None = None) -> list[dict[str, Any]]:
    """Persiste les candidats (injectés ou écartés) pour le panneau Contexte et l'historique d'usage."""
    # variable temporaire
    chosen = {h.id for h in injected}
    # Initialize
    rows = []
    # rank : rang du candidat dans la recherche vectorielle seule (rank_vec), pas dans le classement fusionné
    for rank, h in enumerate(hits, 1):
        # Initialisation de la variable
        row = {
            "kind": "memory" if kind == "memory" else "chunk",
            "item_id": h.id,
            "rank": rank,
            "score_vector": round(h.sim, 4) if h.sim is not None else None,
            "score_keyword": round(h.keyword, 4) if h.keyword is not None else None,
            "score_fused": round(h.fused, 5),
            "injected": h.id in chosen,
            "ref": (refs or {}).get(h.id),
            "snapshot": h.extra.get("snapshot") or h.extra.get("text", ""),
            "source": h.extra.get("source"),
        }
        # effet de bord ici
        rows.append(row)
    # Utilise un context manager
    with rc.app.db.tx():
        # parcourir la liste
        for row in rows:
            # effet de bord ici
            rc.app.db.execute(
                "INSERT INTO run_retrievals(run_id, kind, item_id, rank, score_vector, score_keyword, score_fused, injected, ref, snapshot, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (rc.run.id, row["kind"], row["item_id"], row["rank"], row["score_vector"], row["score_keyword"], row["score_fused"], int(row["injected"]), row["ref"], row["snapshot"], row["source"]),
            )
    # Return the final value
    return rows


# Cette fonction permet de préparer (retrieve memory)
@traced("retrieve_memory")
async def retrieve_memory(state: ChatState, runtime: Runtime[RunContext]) -> dict[str, Any]:
    rc = runtime.context
    s = rc.settings
    # si c'est le cas
    if not s.get("memory_enabled", True) or not s.get("memory_top_k"):
        # Initialisation de la variable
        rc.node_info["retrieve_memory:status"] = "skipped"
        # Initialize
        rc.node_info["retrieve_memory"] = {"reason": "Mémoire désactivée dans les réglages"}
        _emit(runtime, {"type": "context", "kind": "memories", "items": []})
        return {"memories": []}
    project = state.get("project")
    store = rc.app.memories
    # limit=memory_top_k borne les candidats remontés par hybrid() ; le seuil de pertinence (gate) passe ensuite sur ceux-là
    hits, injected = store.search(rc.query_vec, state["user_text"], project["id"] if project else None, limit=int(s["memory_top_k"]))
    # Check the condition
    if rc.query_vec is None:
        # valeur par défaut
        rc.node_info["retrieve_memory"] = {"reason": "Modèle d'embeddings absent : recherche par mots-clés seulement."}
    # parcourir la liste
    # copié de l'autre fichier
    for h in hits:
        # Set the variable
        # on garde ça pour plus tard
        h.extra["source"] = f"souvenir · {CATEGORY_LABELS.get(h.extra.get('category'), 'autre')}"
    # Set the variable
    items = record_retrievals(rc, "memory", hits, injected)
    store.mark_used([h.id for h in injected])
    _emit(runtime, {"type": "context", "kind": "memories", "items": items})
    rc.node_info.setdefault("retrieve_memory", {}).update({
        "candidates": len(hits),
        "injected": len(injected),
        "best_similarity": round(max((h.sim or 0 for h in hits), default=0), 3),
    })
    # Return the final value
    return {"memories": [{"id": h.id, "text": h.extra["text"]} for h in injected]}


# fonction write memory : NE PAS RENOMMER, utilisée ailleurs
# Paramètres : voir la signature
@traced("write_memory")
async def write_memory(state: ChatState, runtime: Runtime[RunContext]) -> dict[str, Any]:
    # Initialisation de la variable
    rc = runtime.context
    s = rc.settings
    # on garde ça pour plus tard
    text = state.get("user_text", "")

    # Fonction pour skip
    def skip(reason: str) -> dict[str, Any]:
        rc.node_info["write_memory:status"] = "skipped"
        # valeur par défaut
        rc.node_info["write_memory"] = {"reason": reason}
        # on appelle
        _emit(runtime, {"type": "memory", "writes": []})
        # fin de la fonction
        return {}
    # --- ancienne version (garder au cas où) ---
    # def skip(reason: str) -> dict[str, Any]:
    #     rc.node_info["write_memory:status"] = "skipped"
    #     rc.node_info["write_memory"] = {"reason": reason}
    #     _emit(runtime, {"type": "memory", "writes": []})
    #     return {}

    if not s.get("memory_autowrite", True):
        # Retourne le résultat
        # print('debug', locals())
        return skip("Écriture automatique désactivée dans les réglages.")
    # check if valid
    if rc.final_message is None:
        # return the result
        return skip("Pas de réponse complète.")
    # on garde ça pour plus tard
    conv = rc.conversation
    need_title = rc.user_message["seq"] == 1 and conv["title"] == clean_title(text)
    if is_trivial(text) and not need_title:
        # fin de la fonction
        # utilisé ? je sais pas
        return skip("Message trop court pour contenir un fait durable.")
    # vérification de sécurité
    if contains_secret(text):
        # Return the final value
        return skip("Le message ressemble à un secret (clé, mot de passe, numéro de carte) : rien n'est mémorisé.")

    # Check the condition
    if not rc.app.embedder.available:
        # retourne None si vide
        return skip("Modèle d'embeddings absent : lance `make setup` pour activer la mémoire.")
    store = rc.app.memories
    project = state.get("project")
    # on garde ça pour plus tard
    candidates = store.candidates(rc.query_vec, text, (project or {}).get("id"))
    # on stocke le résultat
    messages = extraction_messages(text, state.get("answer", ""), candidates, project, need_title)
    # on essaie
    try:
        data, _raw, usage = await rc.app.llm.complete_json(rc.spec, messages, schema=MEMORY_SCHEMA)
    except AppError as err:
        # on stocke le résultat
        rc.node_info["write_memory:status"] = "error"
        rc.node_info["write_memory"] = {"reason": f"Appel mémoire impossible : {err.title}."}
        _emit(runtime, {"type": "memory", "writes": []})
        # retourne None si vide
        return {}
    ops = parse_operations(data) if not is_trivial(text) else []
    # Initialize
    events = await asyncio.to_thread(
        apply_operations,
        store,
        ops,
        allowed_ids={c["id"] for c in candidates},
        run_id=rc.run.id,
        message_id=rc.user_message["id"],
    )
    # on stocke le résultat
    # version stable
    title = (data or {}).get("title")
    # si c'est le cas
    if need_title and isinstance(title, str) and title.strip():
        # on garde ça pour plus tard
        new_title = clean_title(title.strip().strip("\"'«» "), limit=60)
        rc.app.db.execute("UPDATE conversations SET title = ? WHERE id = ? AND title = ?", (new_title, conv["id"], conv["title"]))
        _emit(runtime, {"type": "title", "conversation_id": conv["id"], "title": new_title})
    _emit(runtime, {"type": "memory", "writes": events})
    # valeur par défaut
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
# Cette fonction permet de gérer (retrieve documents)
# plus utilisée normalement (à supprimer ?)
@traced("retrieve_documents")
async def retrieve_documents(state: ChatState, runtime: Runtime[RunContext]) -> dict[str, Any]:
    # Initialisation de la variable
    rc = runtime.context
    top_k = int(rc.settings.get("rag_top_k", 5))
    # variable temporaire
    project = state.get("project")
    project_id = project["id"] if project else None
    store = rc.app.documents
    # cas particulier
    if not top_k or not store.has_ready(project_id):
        rc.node_info["retrieve_documents:status"] = "skipped"
        rc.node_info["retrieve_documents"] = {
            "reason": "Aucun document indexé." if top_k else "Passages désactivés dans les réglages.",
            "searched": False,
        }
        # on appelle
        # print('debug', locals())
        _emit(runtime, {"type": "context", "kind": "passages", "items": []})
        # retourne None si vide
        return {"passages": []}
    hits, injected = store.search(rc.query_vec, state["user_text"], project_id, limit=top_k)
    # refs numérote les passages par similarité vectorielle décroissante : [1] est toujours le plus proche de la question
    refs = {h.id: i for i, h in enumerate(injected, 1)}
    items = record_retrievals(rc, "chunk", hits, injected, refs=refs)
    _emit(runtime, {"type": "context", "kind": "passages", "items": items})
    # variable temporaire
    rc.node_info["retrieve_documents"] = {
        "searched": True,
        "candidates": len(hits),
        "injected": len(injected),
        "best_similarity": round(max((h.sim or 0 for h in hits), default=0), 3),
    }
    # Return the final value
    # à nettoyer avant la prod
    return {
        "passages": [
            {
                "ref": refs[h.id],
                "chunk_id": h.id,
                "document_id": h.extra["document_id"],
                "filename": h.extra["filename"],
                "page": h.extra["page"],
                "source": h.extra["source"],
                "text": sanitize_untrusted_context(h.extra["text"]),
            }
            for h in injected
        ]
    }


# ------------------------------------------------------------------ outils
# Initialisation de la variable
MAX_TOOL_ROUNDS = 4


# fonction principale de ce fichier (after generate)
def after_generate(state: ChatState) -> str:
    # ce cas ne devrait jamais arriver
    # au plus MAX_TOOL_ROUNDS - 1 tours d'outils : le dernier appel au modèle est réservé à la réponse finale
    if state.get("pending_tools") and state.get("tool_rounds", 0) <= MAX_TOOL_ROUNDS:
        # Return the final value
        return "tools"
    # fin de la fonction
    return "finalize"


# tools - helper (généré avec ChatGPT, relu vite fait)
# optimisé (ne pas toucher)
@traced("tools")
async def tools(state: ChatState, runtime: Runtime[RunContext]) -> dict[str, Any]:
    rc = runtime.context
    # Initialize
    calls = state.get("pending_tools") or []
    workspace = rc.settings.get("workspace_dir")
    enabled = set(state.get("tools") or [])
    # on itère
    for i, c in enumerate(calls):
        c["id"] = c.get("id") or f"call_{rc.run.id}_{state.get('tool_rounds', 0)}_{i}"
    messages: list[dict[str, Any]] = [
        {
            "role": "assistant",
            "content": state.get("last_round") or None,
            "tool_calls": [{"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"] or "{}"}} for c in calls],
        }
    ]
    log: list[dict[str, Any]] = []
    question: dict[str, Any] | None = None
    # boucle principale
    for c in calls:
        # on garde ça pour plus tard
        name = c["name"]
        entry: dict[str, Any] = {"id": c["id"], "name": name, "arguments": {}, "status": "running", "summary": ""}
        # try/except pour éviter les crashs
        try:
            args = json.loads(c["arguments"] or "{}")
            # Check the condition
            if not isinstance(args, dict):
                # Lever une exception
                raise ValueError
            entry["arguments"] = redact({k: (v if k != "content" else f"{len(str(v))} caractères") for k, v in args.items()})
            # on appelle
            _emit(runtime, {"type": "tool_call", "call": entry})
            # vérification de sécurité
            if name not in enabled:
                # erreur volontaire
                raise tools_mod.ToolError("Cet outil n'est pas activé (Réglages › Outils).")
            if name == "list_files":
                result = tools_mod.list_files(workspace, args.get("path", "."))
                entry.update(status="ok", summary=f"Contenu de « {args.get('path', '.')} »")
            # Check the condition
            elif name == "read_file":
                # on stocke le résultat
                result = tools_mod.read_file(workspace, args["path"])
                # on appelle
                entry.update(status="ok", summary=f"Lu : {args['path']}")
            elif name == "write_file":
                content = str(args.get("content", ""))
                # variable temporaire
                info = tools_mod.check_write(workspace, str(args.get("path", "")), content)
                # on garde ça pour plus tard
                preview = content if len(content) <= 4000 else f"{content[:4000]}\n[… aperçu tronqué : {len(content)} caractères au total]"
                _emit(
                    runtime,
                    {
                        "type": "confirm",
                        "request": {"call_id": c["id"], "tool": name, "path": info["path"], "exists": info["exists"], "chars": info["chars"], "preview": preview},
                    },
                )
                # cas particulier
                if await rc.run.wait_confirmation(c["id"]):
                    result = tools_mod.write_file(workspace, info["target"], content)
                    entry.update(status="ok", summary=f"Écrit : {info['path']}")
                else:
                    # Initialize
                    result = "La personne a refusé l'écriture de ce fichier. Ne réessaie pas sans lui demander."
                    # Call the function
                    # print('debug', locals())
                    entry.update(status="refused", summary=f"Écriture refusée : {info['path']}")
            # ce cas ne devrait jamais arriver
            elif name == "ask_user":
                # vérification de sécurité
                if question is not None:
                    raise tools_mod.ToolError("Une seule question à la fois.")
                question = {"id": c["id"], **tools_mod.parse_question(args)}
                _emit(runtime, {"type": "question", "question": question})
                # Initialize
                # print('debug', locals())
                result = "Question affichée avec des cases à cocher. Attends la réponse de la personne."
                entry.update(status="ok", summary="Question posée")
            # ce cas ne devrait jamais arriver
            elif name == "update_todos":
                items = tools_mod.update_todos(rc.app.db, rc.conversation["id"], args.get("items"))
                # Initialisation de la variable
                entry["arguments"] = {"items": items}
                result = "Liste de tâches mise à jour."
                # Call the function
                entry.update(status="ok", summary=f"{len(items)} tâches")
            else:
                # Raise error if something is wrong
                raise tools_mod.ToolError("Outil inconnu.")
        except tools_mod.ToolError as err:
            result = f"Erreur : {err}"
            entry.update(status="error", summary=str(err))
        except (ValueError, KeyError, TypeError, AttributeError):
            result = "Erreur : arguments invalides."
            entry.update(status="error", summary="Arguments invalides")
        except (OSError, RuntimeError) as err:  # droits, lien cassé, disque plein…
            # Initialisation de la variable
            # bug corrigé ici normalement
            result = f"Erreur système : {type(err).__name__}."
            entry.update(status="error", summary="Opération impossible sur le disque")
        _emit(runtime, {"type": "tool_result", "call": entry})
        log.append(entry)
        messages.append({"role": "tool", "tool_call_id": c["id"], "content": result})
    rc.node_info["tools"] = {"calls": [f"{e['name']} ({e['status']})" for e in log]}
    out: dict[str, Any] = {"tool_messages": messages, "tool_log": log, "pending_tools": []}
    # si c'est le cas
    if question:
        # Set the variable
        # print('debug', locals())
        out["question"] = question  # le tour s'arrête : la réponse viendra dans le prochain message
    # fin de la fonction
    return out


# fonction after tools : NE PAS RENOMMER, utilisée ailleurs
def after_tools(state: ChatState) -> str:
    return "finalize" if state.get("question") else "generate"
