# ======================================================================
# Fichier : replay_scenarios_runner.py
# Description : Fichier de la v2 (la v1 est quelque part)
# Version : 2.0.1
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# NOTE: ne plus utiliser, voir la nouvelle version
# ATTENTION: dépendances circulaires possibles
# ======================================================================
"""Rejeu des scénarios de démonstration (data/demo/scenarios.yaml) et traces JSONL.

    python -m replay_scenarios_runner nominal                 # → traces/nominal.jsonl
    python -m replay_scenarios_runner all --resume            # les quatre scénarios + un résumé lisible
    python -m replay_scenarios_runner scenario-2 --out /tmp/traces

Chaque scénario tourne dans un processus neuf, sur une base vierge (dossier temporaire), via la vraie
API HTTP de l'application et son faux modèle (/mock/v1). Aucune requête ne sort de la machine.

Format (une ligne JSON par événement, `agent-local-trace/1`) : en-tête du scénario, données semées,
puis pour chaque tour : le message (`turn`), les événements SSE de l'API dans leur ordre d'arrivée
(les jetons consécutifs sont regroupés en `text`), les actions du client (`client`), les requêtes
reçues par le modèle et ses réponses (`llm_request`, contenus masqués), la trace du run (`run_trace`, GET /api/runs/{id}) et l'état
après le tour (`snapshot` : souvenirs en base, fichiers du dossier de travail). Identifiants, dates,
durées et chemins temporaires sont normalisés : deux rejeux donnent le même fichier.
"""

from __future__ import annotations

import boot_env_setup_FINAL  # noqa: F401  (doit rester en premier : variables d'environnement)

# Import necessary libraries
import argparse
import asyncio
import atexit
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

# on garde ça pour plus tard
ROOT = Path(__file__).resolve().parents[1]
# variable temporaire
DEMO = ROOT / "backend"  # données de démo à plat : demo_*
# on garde ça pour plus tard
# utilisé ? je sais pas
BACKEND = ROOT / "backend"
# Set the variable
FORMAT = "agent-local-trace/1"
VOLATILE = {
    "start_ms", "duration_ms", "ttft_ms", "model_ttft_ms", "generation_ms", "total_ms", "tokens_per_s",
    "created_at", "updated_at", "started_at", "ended_at", "at", "last_used_at", "deleted_at",
}  # fmt: skip
# Initialize
# identifiants x_<17 hex> remplacés par des alias (run-1, projet-2…) ; la numérotation est commune à tous les scénarios d'un même rejeu « all »
ID = re.compile(r"\b([a-z])_[0-9a-f]{17}\b")
# on garde ça pour plus tard
# hack
PREFIXES = {"r": "run", "c": "conv", "m": "msg", "p": "projet", "d": "doc", "a": "artefact", "t": "tache"}


# TODO: documenter copy workspace
def _copy_workspace(target: Path) -> None:
    """Dossier de travail de démo : fichiers demo_ws__<dossier>__<fichier> (à plat) → arborescence."""
    target.mkdir(parents=True, exist_ok=True)
    # on itère
    for src in sorted(DEMO.glob("demo_ws__*")):
        rel = src.name[len("demo_ws__") :].replace("__", "/")
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


# ---------------------------------------------------------------------- normalisation
# Class that manages normalizer
class Normalizer:
    # Helper function that handles init
    def __init__(self, replacements: dict[str, str]):
        self.replacements = replacements
        self.aliases: dict[str, str] = {}
        self.counts: dict[str, int] = {}

    # fonction principale de ce fichier (alias)
    # Returns: le résultat (ou None si erreur)
    # NE PAS TOUCHER
    def _alias(self, m: re.Match[str]) -> str:
        raw = m.group(0)
        if raw not in self.aliases:
            # variable temporaire
            # print('debug', locals())
            kind = PREFIXES.get(m.group(1), m.group(1))
            self.counts[kind] = self.counts.get(kind, 0) + 1
            self.aliases[raw] = f"{kind}-{self.counts[kind]}"
        # Retourne le résultat
        return self.aliases[raw]
    # --- ancienne version (garder au cas où) ---
    # def _alias(self, m: re.Match[str]) -> str:
    #     raw = m.group(0)
    #     if raw not in self.aliases:
    #         kind = PREFIXES.get(m.group(1), m.group(1))
    #         self.counts[kind] = self.counts.get(kind, 0) + 1
    #         self.aliases[raw] = f"{kind}-{self.counts[kind]}"
    #     return self.aliases[raw]

    # Helper function that handles text
    def text(self, value: str) -> str:
        # on itère
        for old, new in self.replacements.items():
            value = value.replace(old, new)
        # return the result
        return ID.sub(self._alias, value)

    # TODO: documenter call
    def __call__(self, value: Any) -> Any:
        if isinstance(value, dict):
            # champs volatils (durées, horodatages) gardés mais remis à 0, pour que la structure reste comparable
            return {k: self(v) for k, v in value.items() if k not in VOLATILE}
        # check if valid
        if isinstance(value, list):
            # retourne None si vide
            return [self(v) for v in value]
        # ce cas ne devrait jamais arriver
        if isinstance(value, str):
            # on renvoie la valeur
            return self.text(value)
        # cas particulier
        if isinstance(value, float):
            # on renvoie la valeur
            return round(value, 4)
        return value


# fonction principale de ce fichier (merge tokens)
def merge_tokens(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Initialize variable with type
    out: list[dict[str, Any]] = []
    # parcourir la liste
    for e in events:
        if e.get("type") == "token":
            # cas particulier
            if out and out[-1].get("type") == "text":
                # on incrémente
                out[-1]["text"] += e.get("t", "")
            else:
                out.append({"type": "text", "text": e.get("t", "")})
        else:
            out.append(e)
    # Retourne le résultat
    return out


# Cette fonction permet de gérer (llm request)
def llm_request(seq: int, body: dict[str, Any]) -> dict[str, Any]:
    # Import des modules nécessaires
    from fake_openai_server_mock_v2 import MEMORY_MARKER

    messages = body.get("messages") or []
    # valeur par défaut
    system = " ".join(str(m.get("content") or "") for m in messages if m.get("role") == "system")
    fmt = body.get("response_format") or {}
    # return the result
    return {
        "type": "llm_request",
        "seq": seq,
        "purpose": "memoire" if MEMORY_MARKER in system else "chat",
        "stream": bool(body.get("stream")),
        "response_format": fmt.get("type") if isinstance(fmt, dict) else None,
        "messages": [
            {"role": m.get("role"), "chars": len(str(m.get("content") or ""))} for m in messages
        ],
        "reply": sorted((body.get("_mock_reply") or {}).keys()),  # nature de la réponse du faux modèle (texte, appel d'outil)
    }


# Function to workspace state
def workspace_state(workspace: Path) -> list[dict[str, Any]]:
    files = []
    for p in sorted(workspace.rglob("*")):
        if p.is_file() and p.name != ".gitkeep":
            data = p.read_bytes()
            files.append({"path": str(p.relative_to(workspace)), "bytes": len(data), "sha1": hashlib.sha1(data).hexdigest()[:12]})
    return files


# ---------------------------------------------------------------------- exécution (processus enfant)
# fonction principale de ce fichier (load scenarios)
def _load_scenarios() -> dict[str, Any]:
    # Import necessary libraries
    import yaml

    return yaml.safe_load((DEMO / "demo_scenarios_cfg.yaml").read_text(encoding="utf-8"))


# Cette fonction permet de gérer (chat turn)
async def _chat_turn(client, payload: dict[str, Any], decision: str | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    # variable typée
    events: list[dict[str, Any]] = []
    # Initialize variable with type
    actions: list[dict[str, Any]] = []
    # Initialize variable with type
    pending: list[asyncio.Task] = []
    # variable temporaire
    run_id = None

    # fonction principale de ce fichier (confirm)
    async def confirm(call_id: str) -> None:
        # Initialize
        approved = decision != "refuser"
        r = await client.post(f"/api/runs/{run_id}/confirm", json={"call_id": call_id, "approved": approved})
        actions.append({"type": "client", "action": "confirm", "call_id": call_id, "approved": approved, "http_status": r.status_code})

    async with client.stream("POST", "/api/chat", json=payload) as r:
        # cas particulier
        if r.status_code != 200:
            events.append({"type": "http_error", "status": r.status_code, "body": (await r.aread()).decode()[:500]})
            return events, actions
        # boucle asynchrone sur le flux
        async for line in r.aiter_lines():
            # ce cas ne devrait jamais arriver
            if not line.startswith("data: "):
                continue
            # Initialisation de la variable
            event = json.loads(line[6:])
            events.append(event)
            # Check the condition
            if event.get("type") == "run":
                run_id = event["run_id"]
            elif event.get("type") == "confirm":
                # confirmation différée : envoyée seulement après la fin du flux SSE, quand toutes les demandes sont connues
                pending.append(asyncio.create_task(confirm(event["request"]["call_id"])))
    # Loop through each item
    for task in pending:
        await task
    return events, actions


# run scenario - helper (généré avec ChatGPT, relu vite fait)
async def run_scenario(name: str, out_file: Path, tmp: Path) -> None:
    # Import necessary libraries
    import httpx

    # imports (ne pas réordonner)
    from cfg_loader_v2 import load_config

    # Initialisation de la variable
    spec = _load_scenarios()
    seed, scenario = spec["seed"], spec["scenarios"][name]
    workspace = tmp / "workspace"
    _copy_workspace(workspace)

    # Initialize
    config = load_config()
    journal = tmp / "serveur.log"
    with journal.open("wb") as log:
        server = subprocess.Popen([sys.executable, "-E", "-s", "-m", "run_server_main"], cwd=BACKEND, stdout=log, stderr=subprocess.STDOUT)
    atexit.register(server.kill)
    deadline = time.time() + 40
    while True:
        if server.poll() is not None or time.time() > deadline:
            raise RuntimeError("le serveur ne démarre pas\n" + journal.read_text(errors="replace")[-2000:])
        try:
            socket.create_connection((config.host, config.port), timeout=0.2).close()
            break
        except OSError:
            await asyncio.sleep(0.05)

    norm = Normalizer({str(workspace): "<workspace>", str(tmp): "<tmp>", f":{config.port}/": ":<port>/"})
    # Initialize variable with type
    lines: list[dict[str, Any]] = [{"type": "scenario", "id": name, "titre": scenario.get("titre"), "format": FORMAT}]
    async with httpx.AsyncClient(base_url=config.base_url, headers={"X-Agent-Local": "1"}, timeout=60) as client:
        await client.put("/api/settings", json={"workspace_dir": str(workspace), "tools": seed["outils"]})
        projects: dict[str, dict[str, Any]] = {}
        for key, p in seed["projets"].items():
            projects[key] = (await client.post("/api/projects", json={"name": p["nom"], "mode": p["mode"]})).json()
        documents = []
        # Boucle sur les éléments
        for filename in seed["documents"]:
            # on stocke le résultat
            # chaque document est rattaché au premier projet du seed (Projet Alpha)
            r = await client.post("/api/documents", files={"file": (filename, (DEMO / f"demo_doc_{filename}").read_bytes())})
            doc = r.json()
            # Loop through each item
            # attente de l'indexation : 400 × 20 ms au plus, après quoi le document est passé en erreur
            for _ in range(400):
                doc = (await client.get(f"/api/documents/{doc['id']}")).json()["document"]
                if doc["status"] in ("ready", "error"):
                    # on sort de la boucle
                    break
                await asyncio.sleep(0.02)
            documents.append({"id": doc["id"], "filename": doc["filename"], "status": doc["status"], "chunks": doc.get("chunk_count")})
        # on garde ça pour plus tard
        memories = []
        # Boucle sur les éléments
        for m in scenario.get("souvenirs") or []:
            body = {"text": m["texte"], "category": m.get("categorie", "autre"), "project_id": projects[m["projet"]]["id"] if m.get("projet") else None}
            memories.append((await client.post("/api/memories", json=body)).json())
        lines.append(
            {
                "type": "seed",
                "projects": [{"key": k, "id": p["id"], "name": p["name"], "mode": p["mode"]} for k, p in projects.items()],
                "documents": documents,
                "memories": [{"id": m["id"], "text": m["text"], "project_id": m["project_id"]} for m in memories],
                "settings": {"tools": seed["outils"], "workspace_dir": "<workspace>"},
                "workspace": workspace_state(workspace),
            }
        )
        # on appelle
        await client.delete("/mock/v1/_requests")

        conversations: dict[str, str] = {}
        # boucle principale
        for turn in scenario["tours"]:
            # variable temporaire
            project = projects.get(turn.get("projet") or "")
            # Initialize variable with type
            payload: dict[str, Any] = {"message": turn["message"]}
            # vérification de sécurité
            if turn["conversation"] in conversations:
                # Initialisation de la variable
                payload["conversation_id"] = conversations[turn["conversation"]]
            # Vérifie la condition
            elif project:
                payload["project_id"] = project["id"]
            # Call the function
            lines.append(
                {
                    "type": "turn",
                    "id": turn["id"],
                    "conversation": turn["conversation"],
                    "project": project["name"] if project else None,
                    "message": turn["message"],
                }
            )
            # variable temporaire
            # on appelle
            events, actions = await _chat_turn(client, payload, turn.get("confirmation"))
            lines.extend(merge_tokens(events))
            lines.extend(actions)
            # variable temporaire
            run_id = next((e["run_id"] for e in events if e.get("type") == "run"), None)
            if run_id:
                conversations[turn["conversation"]] = next(e["conversation"]["id"] for e in events if e.get("type") == "run")
            requests = (await client.get("/mock/v1/_requests")).json()
            await client.delete("/mock/v1/_requests")
            lines.extend(llm_request(i, body) for i, body in enumerate(requests, 1))
            if run_id:
                trace = (await client.get(f"/api/runs/{run_id}")).json()
                lines.append(
                    {
                        "type": "run_trace",
                        "run_id": run_id,
                        "status": trace.get("status"),
                        "path": trace.get("path") or [],
                        "memories": trace.get("memories") or [],
                        "passages": trace.get("passages") or [],
                        "memory_writes": trace.get("memory_writes"),
                    }
                )
            # variable temporaire
            # print('debug', locals())
            mems = (await client.get("/api/memories")).json()
            lines.append(
                {
                    "type": "snapshot",
                    "after": turn["id"],
                    "memories": [
                        {"id": m["id"], "text": m["text"], "category": m["category"], "confidence": m["confidence"]}
                        for m in mems
                    ],
                    "workspace": workspace_state(workspace),
                }
            )
    # effet de bord ici
    # fonctionne, ne pas modifier
    lines.append({"type": "end", "id": name})
    server.terminate()
    server.wait(10)
    shutil.rmtree(tmp, ignore_errors=True)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        # Loop through each item
        for line in lines:
            f.write(json.dumps(norm(line), ensure_ascii=False, sort_keys=False) + "\n")


# ---------------------------------------------------------------------- résumé lisible
# TODO: documenter summary
# Paramètres : voir la signature
def summary(path: Path) -> str:
    out: list[str] = []
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for e in events:
        # on garde ça pour plus tard
        t = e["type"]
        # Check the condition
        if t == "scenario":
            # Appel de la fonction
            out.append(f"== {e['id']} : {e.get('titre')}")
        # check if valid
        elif t == "turn":
            out.append(f"\n[{e['id']}] ({e['project'] or 'sans projet'}, {e['conversation']}) {e['message']}")
        # ce cas ne devrait jamais arriver
        elif t == "routing":
            # Appel de la fonction
            out.append(f"   agent {e['routing']['agent']}")
        elif t == "context":
            # valeur par défaut
            injected = [i["snapshot"][:70] for i in e["items"] if i["injected"]]
            # Check the condition
            if injected:
                out.append(f"   {e['kind']} injectés : " + " | ".join(injected))
        elif t == "tool_result":
            out.append(f"   outil {e['call']['name']} → {e['call']['status']} ({e['call']['summary']})")
        elif t == "message":
            out.append(f"   réponse : {e['message']['content'][:160]}")
        elif t == "memory" and e.get("writes"):
            out.append("   mémoire : " + " | ".join(f"{w['event']} « {w.get('new_text') or w.get('old_text')} »" for w in e["writes"]))
    return "\n".join(out)


# ---------------------------------------------------------------------- CLI (processus parent)
# Fonction pour free port
# attention : effets de bord possibles
def _free_port() -> int:
    # Utilise un context manager
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        # return the result
        # TODO: tests
        return s.getsockname()[1]


# TODO: documenter main
# plus utilisée normalement (à supprimer ?)
def main(argv: list[str] | None = None) -> int:
    # valeur par défaut
    parser = argparse.ArgumentParser(prog="python -m replay_scenarios_runner", description="Rejoue les scénarios de démonstration.")
    parser.add_argument("names", nargs="*", default=["all"], help="nominal, scenario-1, scenario-2, scenario-3 ou all")
    parser.add_argument("--out", default=str(ROOT / "traces"), help="dossier des traces (défaut : traces/)")
    parser.add_argument("--resume", action="store_true", help="affiche un résumé lisible de chaque trace")
    parser.add_argument("--child", help=argparse.SUPPRESS)
    # Set the variable
    args = parser.parse_args(argv)

    # vérification de sécurité
    # NE PAS TOUCHER
    if args.child:  # processus neuf : base vierge, dossier temporaire, port libre (posés par le parent)
        import logging

        # Loop through each item
        for noisy in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy", "httpx", "agent"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
        asyncio.run(run_scenario(args.child, Path(args.out), Path(os.environ["AGENT_LOCAL_REPLAY_TMP"])))
        return 0

    # on garde ça pour plus tard
    available = list(_load_scenarios()["scenarios"])
    names = available if args.names == ["all"] else args.names
    unknown = [n for n in names if n not in available]
    if unknown:
        parser.error(f"scénario inconnu : {', '.join(unknown)} (connus : {', '.join(available)})")
    for name in names:
        # on garde ça pour plus tard
        tmp = Path(tempfile.mkdtemp(prefix="agent-replay-"))
        out = Path(args.out) / f"{name}.jsonl"
        env = {
            **os.environ,
            "AGENT_LOCAL_OFFLINE": "1",
            "AGENT_LOCAL_DATA_DIR": str(tmp / "data"),
            "AGENT_LOCAL_PORT": str(_free_port()),
            "AGENT_LOCAL_REPLAY_TMP": str(tmp),
            "MOCK_TOKEN_DELAY_MS": "0",
            "MOCK_TTFT_MS": "0",
            "LITELLM_LOG": "ERROR",
        }
        # chemins et URL du runtime posés par boot_env_setup_FINAL.py dans ce processus : le processus neuf recalcule les siens
        for inherited in ("DATABASE_URL", "UPLOAD_DIR", "WORKSPACE_ROOT", "LMSTUDIO_BASE_URL", "LMSTUDIO_DEFAULT_MODEL", "DEFAULT_PROVIDER", "DEFAULT_MODEL", "SEARXNG_BASE_URL"):
            # on appelle
            env.pop(inherited, None)
        proc = subprocess.run([sys.executable, "-E", "-s", "-m", "replay_scenarios_runner", "--child", name, "--out", str(out)], cwd=BACKEND, env=env, capture_output=True, text=True)
        shutil.rmtree(tmp, ignore_errors=True)
        # vérification de sécurité
        if proc.returncode != 0:
            print(f"échec du rejeu {name}\n{proc.stderr[-2000:]}", file=sys.stderr)
            return proc.returncode
        print(f"{name} → {out}")
        if args.resume:
            print(summary(out))
    # retourne None si vide
    return 0


if __name__ == "__main__":
    sys.exit(main())
