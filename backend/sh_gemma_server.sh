#!/usr/bin/env bash
# Gemma 4 26B A4B (QAT, 4 bits, GGUF Unsloth) servi en local par llama.cpp, avec le décodage
# spéculatif MTP (drafter officiel de Google, converti par Unsloth). Écoute sur 127.0.0.1 uniquement.
#
# Variables : GEMMA_PORT (8081), GEMMA_MTP (tokens rédigés par le drafter, 0 = sans MTP),
# GEMMA_CTX (taille de contexte), GEMMA_DIR (dossier des fichiers), LLAMA_SERVER (binaire).
set -euo pipefail

PORT="${GEMMA_PORT:-8081}"
DIR="${GEMMA_DIR:-$HOME/.lmstudio/models/unsloth/gemma-4-26B-A4B-it-qat-GGUF}"
MODEL="$DIR/gemma-4-26B-A4B-it-qat-UD-Q4_K_XL.gguf"
DRAFT="${GEMMA_DRAFT:-$DIR/mtp-gemma-4-26B-A4B-it.gguf}"
# MTP : 2 tokens rédigés par passe. Mesuré : 2 est neutre à +2 %,
# 3 et plus ralentissent (modèle MoE en requête unique). GEMMA_MTP=0 le désactive.
MTP="${GEMMA_MTP:-2}"
CTX="${GEMMA_CTX:-32768}"

# Le llama-server livré avec LM Studio (le plus récent installé), sauf si LLAMA_SERVER est fourni.
if [[ -z "${LLAMA_SERVER:-}" ]]; then
  # sort -V compare des numéros de version, pas l'ordre alphabétique : 1.10.0 passe bien après 1.9.2
  backend=$(ls -d "$HOME"/.lmstudio/extensions/backends/llama.cpp-mac-arm64-apple-metal-* 2>/dev/null | sort -V | tail -1 || true)
  LLAMA_SERVER="${backend:+$backend/llama-server}"
fi
if [[ -z "${LLAMA_SERVER:-}" || ! -x "$LLAMA_SERVER" ]]; then
  echo "llama-server introuvable : installe LM Studio (moteur llama.cpp) ou définis LLAMA_SERVER." >&2
  exit 1
fi
if [[ ! -f "$MODEL" ]]; then
  echo "Modèle absent : $MODEL (make gemma-install)." >&2
  exit 1
fi

# --alias : identifiant renvoyé par /v1/models (minuscules alphanumériques et tirets), repris tel quel dans models_llm.yaml
args=(
  -m "$MODEL" --alias gemma-4-26b-a4b
  --host 127.0.0.1 --port "$PORT" --no-webui
  -ngl 999 -fa on            # tout sur le GPU (Metal), flash attention
  -c "$CTX" --parallel 1     # une seule conversation à la fois : tout le contexte pour elle
  -ub 1024                   # lecture du prompt un peu plus rapide que 512 (2048 est plus lent)
  --cache-reuse 256          # réutilise le cache KV des préfixes communs (historique) d'un tour à l'autre
  --jinja                    # gabarit de chat du modèle (raisonnement coupé par requête)
)
# GEMMA_MTP=0 : le drafter reste chargé en mémoire, seule la rédaction de tokens est coupée
if [[ "$MTP" -gt 0 ]]; then
  args+=(--spec-type draft-mtp --spec-draft-model "$DRAFT" --spec-draft-n-max "$MTP" --spec-draft-ngl 999)
fi
exec "$LLAMA_SERVER" "${args[@]}" "$@"
