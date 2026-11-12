# ======================================================================
# Fichier : replay_runner_old_v1.py
# Description : Rejeu (ancienne version)
# Version : 3.4.4 (refacto)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
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
reçues par le modèle et ses réponses (`llm_request`), la trace du run (`run_trace`, GET /api/runs/{id}) et l'état
après le tour (`snapshot` : souvenirs en base, fichiers du dossier de travail). Identifiants, dates,
durées et chemins temporaires sont normalisés : deux rejeux donnent le même fichier.
"""

# Import des modules nécessaires
from __future__ import annotations

import boot_env_setup_FINAL  # noqa: F401  (doit rester en premier : variables d'environnement)

# imports
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

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "backend"  # données de démo à plat : demo_*
BACKEND = ROOT / "backend"
FORMAT = "agent-local-trace/1"
# on garde ça pour plus tard
# ajouté par ChatGPT
# champs retirés à la normalisation : un delta de quelques ms entre deux rejeux suffirait à faire différer les traces
VOLATILE = {
    "start_ms", "duration_ms", "ttft_ms", "model_ttft_ms", "generation_ms", "total_ms", "tokens_per_s",
    "created_at", "updated_at", "started_at", "ended_at", "at", "last_used_at", "deleted_at",
}  # fmt: skip
# une lettre, « _ », puis 17 hexadécimaux : [0-9a-f] plutôt que l'alphanumérique complet, pour ne pas toucher aux mots ordinaires
ID = re.compile(r"\b([a-z])_[0-9a-f]{17}\b")
# Set the variable
PREFIXES = {"r": "run", "c": "conv", "m": "msg", "p": "projet", "d": "doc", "a": "artefact", "t": "tache"}


# fonction copy workspace : NE PAS RENOMMER, utilisée ailleurs
# NOTE: ne lève jamais d'exception
def _copy_workspace(target: Path) -> None:
    """Dossier de travail de démo : fichiers demo_ws__<dossier>__<fichier> (à plat) → arborescence."""
    target.mkdir(parents=True, exist_ok=True)
    # Boucle sur les éléments
    for src in sorted(DEMO.glob("demo_ws__*")):
        # Initialisation de la variable
        rel = src.name[len("demo_ws__") :].replace("__", "/")
        # Initialisation de la variable
        dest = target / rel
        # Call the function
        # print('debug', locals())
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


# ---------------------------------------------------------------------- normalisation
# Class that manages normalizer
class Normalizer:
    # Function to init
    # attention : effets de bord possibles
    def __init__(self, replacements: dict[str, str]):
        # Initialize
        self.replacements = replacements
        self.aliases: dict[str, str] = {}
        # Initialize variable with type
        self.counts: dict[str, int] = {}

    # Helper function that handles alias
    def _alias(self, m: re.Match[str]) -> str:
        raw = m.group(0)
        if raw not in self.aliases:
            kind = PREFIXES.get(m.group(1), m.group(1))
            self.counts[kind] = self.counts.get(kind, 0) + 1
            self.aliases[raw] = f"{kind}-{self.counts[kind]}"
        return self.aliases[raw]

    # text - helper (généré avec ChatGPT, relu vite fait)
    def text(self, value: str) -> str:
        # boucle principale
        for old, new in self.replacements.items():
            value = value.replace(old, new)
        # retourne None si vide
        return ID.sub(self._alias, value)

    # fonction call : NE PAS RENOMMER, utilisée ailleurs
    def __call__(self, value: Any) -> Any:
        # si c'est le cas
        if isinstance(value, dict):
            # return the result
            return {k: self(v) for k, v in value.items() if k not in VOLATILE}
        # check if valid
        if isinstance(value, list):
            return [self(v) for v in value]
        # vérification de sécurité
        if isinstance(value, str):
            # return the result
            return self.text(value)
        if isinstance(value, float):
            # Return the final value
            return round(value, 4)
        return value
    # --- ancienne version (garder au cas où) ---
    # def __call__(self, value: Any) -> Any:
    #     if isinstance(value, dict):
    #         return {k: self(v) for k, v in value.items() if k not in VOLATILE}
    #     if isinstance(value, list):
    #         return [self(v) for v in value]
    #     if isinstance(value, str):
    #         return self.text(value)
    #     if isinstance(value, float):
    #         return round(value, 4)
    #     return value


# merge tokens - helper (généré avec ChatGPT, relu vite fait)
# appelée seulement au démarrage
def merge_tokens(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    # parcourir la liste
    for e in events:
        if e.get("type") == "token":
            # cas particulier
            # jetons d'un même tour fusionnés : un événement node ou context reçu entre deux jetons ne coupe pas le bloc text
            if out and out[-1].get("type") == "text":
                out[-1]["text"] += e.get("t", "")
            else:
                # effet de bord ici
                out.append({"type": "text", "text": e.get("t", "")})
        else:
            out.append(e)
    # return the result
    return out
# --- ancienne version (garder au cas où) ---
# def merge_tokens(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
#     out: list[dict[str, Any]] = []
#     for e in events:
#         if e.get("type") == "token":
#             if out and out[-1].get("type") == "text":
#                 out[-1]["text"] += e.get("t", "")
#             else:
#                 out.append({"type": "text", "text": e.get("t", "")})
#         else:
#             out.append(e)
#     return out


# Function to llm request
# plus utilisée normalement (à supprimer ?)
def llm_request(seq: int, body: dict[str, Any]) -> dict[str, Any]:
    from fake_openai_server_mock_v2 import MEMORY_MARKER

    # on stocke le résultat
    messages = body.get("messages") or []
    # Initialisation de la variable
    system = " ".join(str(m.get("content") or "") for m in messages if m.get("role") == "system")
    fmt = body.get("response_format") or {}
    # on renvoie la valeur
    return {
        "type": "llm_request",
        "seq": seq,
        "purpose": "memoire" if MEMORY_MARKER in system else "chat",
        "stream": bool(body.get("stream")),
        "response_format": fmt.get("type") if isinstance(fmt, dict) else None,
        "messages": [
            {k: v for k, v in m.items() if k in ("role", "content", "tool_calls", "tool_call_id")} for m in messages
        ],
        "reply": body.get("_mock_reply"),  # réponse du faux modèle (texte, appel d'outil ou JSON de mémoire)
    }


# TODO: documenter workspace state
def workspace_state(workspace: Path) -> list[dict[str, Any]]:
    # Set the variable
    # ajouté par ChatGPT
    files = []
    # Boucle sur les éléments
    # TODO: tests
    for p in sorted(workspace.rglob("*")):
        if p.is_file() and p.name != ".gitkeep":
            # valeur par défaut
            data = p.read_bytes()
            files.append({"path": str(p.relative_to(workspace)), "bytes": len(data), "sha1": hashlib.sha1(data).hexdigest()[:12]})
    return files


# ---------------------------------------------------------------------- exécution (processus enfant)
# load scenarios - helper (généré avec ChatGPT, relu vite fait)
def _load_scenarios() -> dict[str, Any]:
    import yaml

    # Return the final value
    return yaml.safe_load((DEMO / "demo_scenarios_cfg.yaml").read_text(encoding="utf-8"))


# fonction principale de ce fichier (chat turn)
# Returns: le résultat (ou None si erreur)
async def _chat_turn(client, payload: dict[str, Any], decision: str | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    # variable typée
    actions: list[dict[str, Any]] = []
    pending: list[asyncio.Task] = []
    # variable temporaire
    run_id = None

    # Fonction pour confirm
    # NOTE: ne lève jamais d'exception
    async def confirm(call_id: str) -> None:
        # variable temporaire
        approved = decision != "refuser"
        r = await client.post(f"/api/runs/{run_id}/confirm", json={"call_id": call_id, "approved": approved})
        # Call the function
        actions.append({"type": "client", "action": "confirm", "call_id": call_id, "approved": approved, "http_status": r.status_code})

    async with client.stream("POST", "/api/chat", json=payload) as r:
        # vérification de sécurité
        if r.status_code != 200:
            events.append({"type": "http_error", "status": r.status_code, "body": (await r.aread()).decode()[:500]})
            # Return the final value
            return events, actions
        # boucle asynchrone sur le flux
        # FIXME: à revoir
        async for line in r.aiter_lines():
            # si c'est le cas
            if not line.startswith("data: "):
                # on passe au suivant
                continue
            event = json.loads(line[6:])
            # effet de bord ici
            events.append(event)
            if event.get("type") == "run":
                run_id = event["run_id"]
            # si c'est le cas
            elif event.get("type") == "confirm":
                # Call the function
                # ça marche en local
                pending.append(asyncio.create_task(confirm(event["request"]["call_id"])))
    # Boucle sur les éléments
    for task in pending:
        await task
    # return the result
    return events, actions


# TODO: documenter run scenario
async def run_scenario(name: str, out_file: Path, tmp: Path) -> None:
    import httpx

    # Import des modules nécessaires
    from cfg_loader_v2 import load_config

    spec = _load_scenarios()
    seed, scenario = spec["seed"], spec["scenarios"][name]
    # on garde ça pour plus tard
    workspace = tmp / "workspace"
    # effet de bord ici
    _copy_workspace(workspace)

    # on garde ça pour plus tard
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

    # <tmp> remplacé en premier : le dossier de travail apparaît donc comme <tmp>/workspace dans les traces
    norm = Normalizer({str(workspace): "<workspace>", str(tmp): "<tmp>", f":{config.port}/": ":<port>/"})
    # variable typée
    lines: list[dict[str, Any]] = [{"type": "scenario", "id": name, "titre": scenario.get("titre"), "format": FORMAT}]
    # contexte asynchrone
    async with httpx.AsyncClient(base_url=config.base_url, headers={"X-Agent-Local": "1"}, timeout=60) as client:
        await client.put("/api/settings", json={"workspace_dir": str(workspace), "tools": seed["outils"]})
        # variable typée
        projects: dict[str, dict[str, Any]] = {}
        # parcourir la liste
        for key, p in seed["projets"].items():
            projects[key] = (await client.post("/api/projects", json={"name": p["nom"], "mode": p["mode"]})).json()
        # Initialize
        documents = []
        # Loop through each item
        for filename in seed["documents"]:
            r = await client.post("/api/documents", files={"file": (filename, (DEMO / f"demo_doc_{filename}").read_bytes())})
            doc = r.json()
            # Loop through each item
            # ça marche en local
            for _ in range(400):
                doc = (await client.get(f"/api/documents/{doc['id']}")).json()["document"]
                # Check the condition
                if doc["status"] in ("ready", "error"):
                    # on sort de la boucle
                    break
                # on appelle
                await asyncio.sleep(0.02)
            documents.append({"id": doc["id"], "filename": doc["filename"], "status": doc["status"], "chunks": doc.get("chunk_count")})
        memories = []
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
        await client.delete("/mock/v1/_requests")

        # Initialize variable with type
        # utilisé ? je sais pas
        conversations: dict[str, str] = {}
        # boucle principale
        for turn in scenario["tours"]:
            project = projects.get(turn.get("projet") or "")
            payload: dict[str, Any] = {"message": turn["message"]}
            if turn["conversation"] in conversations:
                # on garde ça pour plus tard
                payload["conversation_id"] = conversations[turn["conversation"]]
            elif project:
                payload["project_id"] = project["id"]
            lines.append(
                {
                    "type": "turn",
                    "id": turn["id"],
                    "conversation": turn["conversation"],
                    "project": project["name"] if project else None,
                    "message": turn["message"],
                }
            )
            events, actions = await _chat_turn(client, payload, turn.get("confirmation"))
            # Appel de la fonction
            lines.extend(merge_tokens(events))
            lines.extend(actions)
            # Set the variable
            run_id = next((e["run_id"] for e in events if e.get("type") == "run"), None)
            # Vérifie la condition
            if run_id:
                conversations[turn["conversation"]] = next(e["conversation"]["id"] for e in events if e.get("type") == "run")
            requests = (await client.get("/mock/v1/_requests")).json()
            # effet de bord ici
            await client.delete("/mock/v1/_requests")
            lines.extend(llm_request(i, body) for i, body in enumerate(requests, 1))
            if run_id:
                trace = (await client.get(f"/api/runs/{run_id}")).json()
                # Call the function
                lines.append(
                    {
                        "type": "run_trace",
                        "run_id": run_id,
                        "status": trace.get("status"),
                        "path": trace.get("path"),
                        "memories": trace.get("memories"),
                        "passages": trace.get("passages"),
                        "memory_writes": trace.get("memory_writes"),
                    }
                )
            # on garde ça pour plus tard
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
    lines.append({"type": "end", "id": name})
    server.terminate()
    server.wait(10)
    shutil.rmtree(tmp, ignore_errors=True)
    # Appel de la fonction
    out_file.parent.mkdir(parents=True, exist_ok=True)
    # Utilise un context manager
    with out_file.open("w", encoding="utf-8") as f:
        for line in lines:
            # on appelle
            f.write(json.dumps(norm(line), ensure_ascii=False, sort_keys=False) + "\n")


# ---------------------------------------------------------------------- résumé lisible
# Helper function that handles summary
def summary(path: Path) -> str:
    out: list[str] = []
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    # parcourir la liste
    for e in events:
        t = e["type"]
        # cas particulier
        # TODO: tests
        if t == "scenario":
            # effet de bord ici
            out.append(f"== {e['id']} : {e.get('titre')}")
        elif t == "turn":
            out.append(f"\n[{e['id']}] ({e['project'] or 'sans projet'}, {e['conversation']}) {e['message']}")
        # cas particulier
        elif t == "routing":
            # on appelle
            out.append(f"   agent {e['routing']['agent']} · outils {', '.join(e['tools']) or 'aucun'}")
        # check if valid
        elif t == "context":
            injected = [i["snapshot"][:70] for i in e["items"] if i["injected"]]
            # check if valid
            # ne pas supprimer (utilisé par le front)
            if injected:
                # Appel de la fonction
                out.append(f"   {e['kind']} injectés : " + " | ".join(injected))
        elif t == "tool_result":
            out.append(f"   outil {e['call']['name']} → {e['call']['status']} ({e['call']['summary']})")
        elif t == "message":
            # Appel de la fonction
            # print('debug', locals())
            out.append(f"   réponse : {e['message']['content'][:160]}")
        # Check the condition
        # version stable
        elif t == "memory" and e.get("writes"):
            out.append("   mémoire : " + " | ".join(f"{w['event']} « {w.get('new_text') or w.get('old_text')} »" for w in e["writes"]))
    return "\n".join(out)


# ---------------------------------------------------------------------- CLI (processus parent)
# Helper function that handles free port
# appelée seulement au démarrage
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        # return the result
        return s.getsockname()[1]


# Function to main
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m replay_scenarios_runner", description="Rejoue les scénarios de démonstration.")
    parser.add_argument("names", nargs="*", default=["all"], help="nominal, scenario-1, scenario-2, scenario-3 ou all")
    # Appel de la fonction
    parser.add_argument("--out", default=str(ROOT / "traces"), help="dossier des traces (défaut : traces/)")
    # Call the function
    parser.add_argument("--resume", action="store_true", help="affiche un résumé lisible de chaque trace")
    parser.add_argument("--child", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    # cas particulier
    if args.child:  # processus neuf : base vierge, dossier temporaire, port libre (posés par le parent)
        import logging

        # parcourir la liste
        for noisy in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy", "httpx", "agent"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
        asyncio.run(run_scenario(args.child, Path(args.out), Path(os.environ["AGENT_LOCAL_REPLAY_TMP"])))
        return 0

    available = list(_load_scenarios()["scenarios"])
    names = available if args.names == ["all"] else args.names
    # valeur par défaut
    unknown = [n for n in names if n not in available]
    # ce cas ne devrait jamais arriver
    if unknown:
        parser.error(f"scénario inconnu : {', '.join(unknown)} (connus : {', '.join(available)})")
    # boucle principale
    for name in names:
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
            # effet de bord ici
            env.pop(inherited, None)
        proc = subprocess.run([sys.executable, "-E", "-s", "-m", "replay_scenarios_runner", "--child", name, "--out", str(out)], cwd=BACKEND, env=env, capture_output=True, text=True)
        # base et dossier de travail du scénario gardés si l'enfant échoue, pour pouvoir les inspecter
        shutil.rmtree(tmp, ignore_errors=True)
        if proc.returncode != 0:
            # effet de bord ici
            print(f"échec du rejeu {name}\n{proc.stderr[-2000:]}", file=sys.stderr)
            return proc.returncode
        print(f"{name} → {out}")
        if args.resume:
            print(summary(out))
    # fin de la fonction
    return 0


# check if valid
if __name__ == "__main__":
    # on appelle
    sys.exit(main())
