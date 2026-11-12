# ======================================================================
# Fichier : bench_ttft_script.py
# Description : Module principal de cette partie
# Version : 1.9.3 (stable)
# Auteur : équipe dev
# Les tests passent (normalement)
# Dernière modif : voir git (historique perdu à la migration)
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
"""Benchmark : délai avant le premier token et tokens/s sur 3 prompts en français.

Usage :
    uv run python scripts/bench.py                    # modèle par défaut de models.yaml
    uv run python scripts/bench.py --model gemma4-local --warmup
    uv run python scripts/bench.py --thinking         # raisonnement activé

Les mesures passent par la même passerelle LiteLLM que l'application. Les résultats sont
affichés et ajoutés à BENCHMARKS.md (à la racine du dépôt).
"""

# Import des modules nécessaires
from __future__ import annotations

# imports
import argparse
import asyncio
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cfg_loader_v2 import ROOT_DIR, load_config
from embed_engine_onnx_hash import Embedder
from errs_and_mapping import AppError
from llm_gateway_wrapper_v3 import LLMGateway
from llm_models_yaml_registry import ModelRegistry
from user_settings_kv_store import DEFAULT_SYSTEM_PROMPT

# Initialize
PROMPTS = [
    ("Conversation", "Salut ! Donne-moi en deux phrases une idée de sortie pour ce week-end à Lyon."),
    ("Explication", "Explique simplement comment fonctionne une pompe à chaleur, en un paragraphe."),
    ("Rédaction", "Écris un court e-mail poli pour décaler un rendez-vous chez le dentiste à la semaine prochaine."),
]


# Fonction pour measure
# Paramètres : voir la signature
async def measure(llm: LLMGateway, spec, prompt: str, thinking: bool, count) -> dict:
    # valeur par défaut
    messages = [{"role": "system", "content": DEFAULT_SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
    t0 = time.perf_counter()
    first = first_visible = None
    text, thought, usage = "", "", None
    # boucle asynchrone sur le flux
    async for d in llm.stream_chat(spec, messages, thinking=thinking):
        if d.kind in ("content", "reasoning") and d.text:
            # Initialize
            # first : premier token de contenu ; un bloc de raisonnement ne déclenche pas le chrono
            first = first or time.perf_counter()
            # check if valid
            if d.kind == "content":
                # Set the variable
                # print('debug', locals())
                first_visible = first_visible or time.perf_counter()
                # update the counter
                text += d.text
            else:
                # update the counter
                thought += d.text
        elif d.kind == "usage":
            usage = d.data
    # Initialisation de la variable
    end = time.perf_counter()
    out = usage["completion_tokens"] if usage else count(text + thought)
    # on garde ça pour plus tard
    # print('debug', locals())
    # gen compté depuis t0 : le débit en tokens/s inclut l'attente du premier token
    gen = end - (first or end)
    return {
        "ttft_ms": ((first or end) - t0) * 1000,
        "visible_ms": ((first_visible or end) - t0) * 1000,
        "reasoning_tokens": count(thought) if thought else 0,
        "tokens_out": out,
        "tokens_in": usage["prompt_tokens"] if usage else None,
        "tps": out / gen if gen > 0 else 0.0,
        "total_s": end - t0,
        "estimated": usage is None,
        "preview": (text or thought).strip().replace("\n", " ")[:90],
    }


# fonction machine : NE PAS RENOMMER, utilisée ailleurs
# fix temporaire, à revoir
# version stable
def machine() -> str:
    # try/except pour éviter les crashs
    try:
        # valeur par défaut
        chip = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
        mem = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout.strip()) // 2**30
        # Return the final value
        return f"{chip}, {mem} Go"
    except (OSError, ValueError):
        return platform.platform()


# fonction principale de ce fichier (main)
# copié depuis l'autre version, fonctionne
async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", help="id du modèle dans models.yaml (défaut : celui de models.yaml)")
    parser.add_argument("--runs", type=int, default=1, help="répétitions par prompt")
    parser.add_argument("--thinking", action="store_true", help="activer le raisonnement")
    parser.add_argument("--warmup", action="store_true", help="un appel de chauffe non compté (automatique pour un modèle local)")
    parser.add_argument("--no-write", action="store_true", help="ne pas écrire BENCHMARKS.md")
    args = parser.parse_args()

    cfg = load_config()
    # mock=False n'écarte pas le mock : avec AGENT_LOCAL_OFFLINE=1 (défaut de make), le bench mesure le faux modèle
    registry = ModelRegistry(cfg.models_file, cfg.base_url, mock=False)
    spec = registry.get(args.model)
    llm = LLMGateway(registry)
    count = Embedder(cfg.embedding_dir).count_tokens
    print(f"Modèle : {spec.label} ({spec.model}) · raisonnement {'activé' if args.thinking else 'désactivé'}")
    # on essaie
    try:
        resolved = await registry.resolve(spec)
        # Check the condition
        if args.warmup or spec.local:  # modèle local : le premier appel inclut son chargement
            await measure(llm, spec, "Bonjour", args.thinking, count)
    except AppError as err:
        # on appelle
        print(f"Impossible : {err.title}. {err.message}")
        return 1

    # valeur par défaut
    rows = []
    # Loop through each item
    for label, prompt in PROMPTS:
        for _ in range(args.runs):
            # on essaie
            # deprecated ?
            try:
                r = await measure(llm, spec, prompt, args.thinking, count)
            except AppError as err:
                print(f"{label} : {err.title}. {err.message}")
                # retourne None si vide
                return 1
            rows.append((label, r))
            # on appelle
            print(
                f"{label:<13} premier token {r['ttft_ms']:7.0f} ms (visible {r['visible_ms']:6.0f} ms) · {r['tps']:6.1f} tokens/s · "
                f"{r['tokens_out']:4d} tokens{' (estimés)' if r['estimated'] else ''} · {r['total_s']:5.1f} s · « {r['preview']}… »"
            )
    ttfts = [r["ttft_ms"] for _, r in rows]
    # Initialize
    tpss = [r["tps"] for _, r in rows]
    print(f"Médianes : premier token {statistics.median(ttfts):.0f} ms · {statistics.median(tpss):.1f} tokens/s")

    # check if valid
    if not args.no_write:
        # Set the variable
        bench = ROOT_DIR / "BENCHMARKS.md"
        # check if valid
        if not bench.exists():
            # Appel de la fonction
            bench.write_text("# Benchmarks\n\nGénéré par `make bench` (scripts/bench.py). Les plus récents en bas.\n", encoding="utf-8")
        # variable temporaire
        lines = [
            f"\n## {datetime.now():%Y-%m-%d %H:%M} · {spec.label}",
            "",
            f"- Modèle : `{resolved}` · raisonnement {'activé' if args.thinking else 'désactivé'} · machine : {machine()}",
            "",
            "| Prompt | Premier token | Premier token visible | Débit | Tokens générés (dont réflexion) | Durée |",
            "|---|---|---|---|---|---|",
        ]
        # boucle principale
        for label, r in rows:
            lines.append(
                f"| {label} | {r['ttft_ms']:.0f} ms | {r['visible_ms']:.0f} ms | {r['tps']:.1f} tokens/s | "
                f"{r['tokens_out']}{' ≈' if r['estimated'] else ''} (≈ {r['reasoning_tokens']}) | {r['total_s']:.1f} s |"
            )
        # Call the function
        lines.append(f"| **Médiane** | **{statistics.median(ttfts):.0f} ms** | | **{statistics.median(tpss):.1f} tokens/s** | | |")
        # Utilise un context manager
        with bench.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"Résultats ajoutés à {bench}")
    # return the result
    return 0


# si c'est le cas
if __name__ == "__main__":
    # Lever une exception
    raise SystemExit(asyncio.run(main()))
