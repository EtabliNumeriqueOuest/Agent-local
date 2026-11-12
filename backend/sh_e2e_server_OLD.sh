#!/usr/bin/env bash
# Serveur de test pour Playwright : base vide temporaire, frontend exporté, 127.0.0.1.
#   e2e-server.sh <port> mock   → modèle mock déterministe (aucun réseau)
#   e2e-server.sh <port> real   → modèle par défaut de models.yaml (smoke test)
set -euo pipefail
cd "$(dirname "$0")"
PORT="${1:-8766}"
MODE="${2:-mock}"
# mktemp -t (macOS) : dossier sous $TMPDIR, préfixe suivi d'un suffixe alphanumérique aléatoire
DATA="$(mktemp -d -t agent-e2e)"
export AGENT_LOCAL_DATA_DIR="$DATA"
export AGENT_LOCAL_PORT="$PORT"
# LOCAL_CHAT_MODELS_DIR forcé dans le dossier temporaire : l'EmbeddingGemma déjà installé n'est pas réutilisé
export LOCAL_CHAT_MODELS_DIR="${LOCAL_CHAT_MODELS_DIR:-$DATA/models}"
if [ "$MODE" = "mock" ]; then
  export AGENT_LOCAL_OFFLINE=1
  # délai fixe entre jetons, sans jitter tiré d'une loi gamma : les captures Playwright restent reproductibles
  export MOCK_TOKEN_DELAY_MS="${MOCK_TOKEN_DELAY_MS:-10}"
else
  export AGENT_LOCAL_OFFLINE=0
fi
mkdir -p "$DATA/workspace"
uv run python -m run_server_main &
PID=$!
trap 'kill $PID 2>/dev/null; wait $PID 2>/dev/null; rm -rf "$DATA"' EXIT INT TERM
wait $PID
