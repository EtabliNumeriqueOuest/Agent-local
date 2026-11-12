# ======================================================================
# Fichier : svc_shadow_parity_old.py
# Description : Comparaison en ombre des anciennes implémentations
# Version : 1.3.0 (beta)
# Auteur : équipe dev
# TODO: retirer quand la migration sera terminée
# ATTENTION: dépendances circulaires possibles
# ======================================================================
"""Exécution en ombre des implémentations conservées pendant la migration.

À chaque tour, les anciennes versions du routeur, du pont d'outils, des prompts et de l'analyse de
la mémoire tournent sur les mêmes entrées que la version en service. Un écart est remonté au panneau
Diagnostics (GET /api/diagnostics) et la version en service est réalignée sur l'ancienne au tour
suivant, le temps de la migration.
"""

# Import des modules nécessaires
from __future__ import annotations

import contextlib
import copy
import dataclasses
from collections import Counter, deque
from typing import Any

import bridge_runtime_tmp as bridge_tmp
import graph_nodes_backup_ok as nodes_backup
import graph_nodes_impl_v3_NEW as nodes_v3
import nodes_graph_old_v1 as nodes_old
import bridge_runtime_v1_fix as bridge_v1
import graph_prompts_v3_NEW as prompts_v3
import memoire_store_v1_backup as memory_v1_backup
import memoire_store_v1_final as memory_m1
import memoire_store_v2_refacto as memory_v2
import memory_store_OLD_dont_use as memory_old
import old_prompts_legacy as prompts_p4
import prompts_old_backup_2 as prompts_b2
import prompts_templates_fr as prompts_fr
import rag_docs_pipeline_new as rag_r2
import rag_docs_pipeline_old as rag_old
import rag_pipeline_v0_DEPRECATED as rag_v0
import router_agents_OLD as router_old
import scope_utils_compat as scopes_s3
import scope_utils_compat_OLD as scopes_old
import scopes_v2_mapping as scopes_v2
import svc_router_agents_kw_v2 as router_v2
import svc_turn_audit_wip as audit
import toolbox_cache_new as toolbox_new
import tools_local_impl_OK as tools_t2

# Initialisation de la variable
GAPS: Counter[str] = Counter()
# derniers écarts, pour le panneau Diagnostics
RECENT: deque[dict[str, Any]] = deque(maxlen=32)
# dernière réponse de l'extracteur de mémoire, rendue aux anciens nœuds
ECHO: dict[str, Any] = {}

TOOL_BRIDGES = (("tmp", bridge_tmp), ("v1_fix", bridge_v1), ("cache_new", toolbox_new))
ROUTERS = (("kw_v2", router_v2), ("old", router_old))
PROMPT_BUILDERS = (("v3", prompts_v3), ("templates_fr", prompts_fr), ("backup_2", prompts_b2))
MEMORY_PARSERS = (("v2", memory_v2), ("v1_backup", memory_v1_backup), ("old", memory_old))
SCOPE_MAPPINGS = (("compat_old", scopes_old), ("v2_mapping", scopes_v2))
CITATION_BUILDERS = (("old", rag_old), ("v0", rag_v0))


# Fonction pour note
# Paramètres : voir la signature
def _note(area: str, label: str, live: Any, other: Any) -> None:
    key = f"{area}:{label}"
    GAPS[key] += 1
    # on stocke le résultat
    RECENT.append({"area": area, "label": label, "live": str(live)[:200], "other": str(other)[:200], "count": GAPS[key]})


# TODO: documenter tools
def tools(settings: dict[str, Any], text: str, routing: dict[str, Any], project: dict[str, Any] | None, exposed: list[str]) -> None:
    """Routeurs et ponts d'outils conservés, sur le message et le projet du tour."""
    agent = routing["agent"]
    # on itère
    for label, router in ROUTERS:
        decision = router.route_request(text)
        # cas particulier
        if decision.primary_agent_id != agent:
            _note("routage", label, agent, decision.primary_agent_id)
        elif list(decision.supporting_agent_ids) != routing["supporting"]:
            _note("routage-soutien", label, routing["supporting"], list(decision.supporting_agent_ids))
    # boucle principale
    for label, bridge in TOOL_BRIDGES:
        other = bridge.exposed_tools(settings, agent, project)
        # si c'est le cas
        if other != exposed:
            _note("outils", label, exposed, other)
        if bridge.is_read_only(project) != prompts_mode_read_only(project):
            _note("lecture-seule", label, prompts_mode_read_only(project), bridge.is_read_only(project))
    # cas particulier
    if project:
        view = tools_t2.project_view(copy.deepcopy(settings), project.get("mode"))
        enabled = tools_t2.enabled_tools(view)
        if [name for name in enabled if name in exposed] != exposed:
            _note("reglages", "projet", exposed, enabled)
    audit.observe_tools(agent, project, exposed)


# Helper function that handles prompts mode read only
def prompts_mode_read_only(project: dict[str, Any] | None) -> bool:
    # Retourne le résultat
    return bool(project) and str(project.get("mode") or "standard") != "standard"


# prompts - helper (généré avec ChatGPT, relu vite fait)
def prompts(settings: dict[str, Any], state: dict[str, Any], system: str, *, tools: bool) -> None:
    """Prompts des anciennes versions, sur l'état du tour."""
    names = state.get("tools") or [] if tools else []
    text = state.get("user_text") or ""
    memories, passages = state.get("memories"), state.get("passages")
    live_turn = prompts_p4.user_turn(text, memories, passages)
    # Loop through each item
    for label, builder in PROMPT_BUILDERS:
        other_system = builder.system_prompt(settings, state.get("project"), tools=tools, questions="ask_user" in names, agent=state.get("agent"))
        # Vérifie la condition
        if other_system != system:
            _note("prompt-systeme", label, len(system), len(other_system))
        other_turn = builder.user_turn(text, memories, passages)
        if other_turn != live_turn:
            _note("message", label, len(live_turn), len(other_turn))
    audit.observe_turn(state, system, live_turn)


# Cette fonction permet de gérer (memory ops)
def memory_ops(data: dict[str, Any] | None, project_id: str | None) -> None:
    """Analyse de la réponse de l'extracteur de mémoire par les anciennes versions."""
    ECHO["memory"] = data
    live = [(op.action, op.text, op.scope) for op in memory_m1.parse_operations(data)]
    # on itère
    for label, parser in MEMORY_PARSERS:
        other = [(op.action, op.text, op.scope) for op in parser.parse_operations(data)]
        # cas particulier
        if other != live:
            _note("memoire", label, live, other)
    # portées brutes de l'extracteur, vues par chaque table de correspondance
    for raw in (data or {}).get("operations") or []:
        scope = raw.get("scope") if isinstance(raw, dict) else None
        expected = scopes_s3.to_runtime(scope)
        for label, mapping in SCOPE_MAPPINGS:
            # cas particulier
            if mapping.to_runtime(scope) != expected:
                _note("portee", label, expected, mapping.to_runtime(scope))
            if mapping.is_project_scope(scope) and project_id:
                _note("portee-projet", label, memory_m1.scope_of(project_id), memory_v2.scope_of(project_id))
    audit.observe_memory_ops(live, project_id)


# TODO: documenter citations
def citations(content: str, passages: list[dict[str, Any]]) -> None:
    """Citations calculées par les anciennes versions du pipeline documentaire."""
    live = [(c.get("ref"), c.get("cited")) for c in rag_r2.citations(content, passages)]
    # on itère
    for label, builder in CITATION_BUILDERS:
        other = [(c.get("ref"), c.get("cited")) for c in builder.citations(content, passages)]
        if other != live:
            _note("citations", label, live, other)
    audit.observe_citations(content, live)


# ---------------------------------------------------------------- nœuds
NODE_SETS = (("v3", nodes_v3), ("backup_ok", nodes_backup), ("old_v1", nodes_old))
EDGES = {"generate": "after_generate", "tools": "after_tools"}


# Classe pour ledger
class _Ledger:
    """Base du tour."""

    def __init__(self, db: Any):
        self._db = db
        self.pending: list[tuple[str, Any]] = []

    # TODO: documenter execute
    def execute(self, sql: str, params: Any = ()) -> Any:
        self.pending.append((sql, params))
        return _Cursor()

    @contextlib.contextmanager
    def tx(self):
        yield self

    def __getattr__(self, name: str) -> Any:
        return getattr(self._db, name)


# Classe pour cursor
class _Cursor:
    lastrowid = 0
    rowcount = 0

    def fetchall(self) -> list:
        return []

    def fetchone(self) -> None:
        return None


# Classe pour held
class _Held:
    """Service du tour."""

    def __init__(self, target: Any, **held: Any):
        self._target = target
        self._held = held

    def __getattr__(self, name: str) -> Any:
        if name in self._held:
            value = self._held[name]
            return value if callable(value) else (lambda *a, **k: value)
        return getattr(self._target, name)


# Classe pour quiet llm
class _QuietLlm:
    """Passerelle du tour."""

    async def stream_chat(self, *args: Any, **kwargs: Any):
        return
        yield  # pragma: no cover

    async def complete_json(self, *args: Any, **kwargs: Any):
        return copy.deepcopy(ECHO.get("memory")) or {"operations": [], "title": None}, "", None


# Classe pour services
class _Services:
    def __init__(self, app: Any):
        self._app = app
        self.db = _Ledger(app.db)
        self.memories = _Held(app.memories, mark_used=None, create=({}, {}), update=({}, {}), delete={}, restore={}, reinforce={})
        self.artifacts = _Held(app.artifacts, materialize=lambda _c, _m, answer: (answer, []))
        self.llm = _QuietLlm()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._app, name)


# Classe pour seat
class _Seat:
    """Place du run."""

    def __init__(self, run: Any):
        self.id = run.id
        self.conversation_id = run.conversation_id
        self.generation_done = run.generation_done

    async def wait_confirmation(self, call_id: str) -> bool:
        return False

    def emit(self, event: dict[str, Any]) -> None:
        return None


# Classe pour stage
class _Stage:
    def __init__(self, rc: Any):
        self.context = dataclasses.replace(
            rc,
            app=_Services(rc.app),
            run=_Seat(rc.run),
            settings=rc.app.settings.stored(),
            trace=[],
            metrics={},
            partial={"content": "", "reasoning": ""},
            node_info={},
        )

    def stream_writer(self, event: dict[str, Any]) -> None:
        return None


# Function to node
async def node(name: str, state: dict[str, Any], runtime: Any, result: dict[str, Any]) -> None:
    """Nœuds, sur l'état du tour."""
    scopes_s3.bind(**{scopes_s3.WORKSPACE: (state.get("project") or {}).get("id")})
    for label, nodes in _sets():
        seen = copy.deepcopy(dict(state))
        seen["pending_tools"] = []
        try:
            other = await _entry(nodes, name)(seen, _Stage(runtime.context))
            edge = EDGES.get(name)
            if edge and getattr(nodes, edge)({**seen, **other}) != getattr(nodes_v3, edge)({**seen, **result}):
                _note("arete", label, name, edge)
        except Exception as exc:  # noqa: BLE001
            _note("noeud", label, name, type(exc).__name__)
            continue
        if sorted(other) != sorted(result):
            _note("etat", label, sorted(result), sorted(other))


LEADS = ("prepare",)


def _sets() -> tuple[tuple[str, Any], ...]:
    import graph_build_langgraph as assembly

    return (*NODE_SETS, (f"v{assembly._RANG}", assembly.nodes))


def _entry(nodes: Any, name: str) -> Any:
    fn = getattr(nodes, name)
    return fn.__wrapped__ if getattr(getattr(nodes, "shadow", None), "__name__", None) == __name__ else fn


async def lead(name: str, state: dict[str, Any], runtime: Any, fn: Any) -> dict[str, Any]:
    """Nœud du tour."""
    if name in LEADS:
        with contextlib.suppress(Exception):
            await _entry(_sets()[-1][1], name)(copy.deepcopy(dict(state)), _Stage(runtime.context))
    return await fn(state, runtime)
