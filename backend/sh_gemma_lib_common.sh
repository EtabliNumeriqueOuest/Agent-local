# Fonctions partagées par start.sh et dev.sh (à sourcer).

GEMMA_PORT="${GEMMA_PORT:-8081}"
GEMMA_DIR="${GEMMA_DIR:-$HOME/.lmstudio/models/unsloth/gemma-4-26B-A4B-it-qat-GGUF}"
GEMMA_PID=""

# Démarre Gemma (llama.cpp) en arrière-plan s'il n'écoute pas déjà sur 127.0.0.1.
ensure_gemma() {
  local root logdir
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  if [[ "${AGENT_LOCAL_OFFLINE:-1}" == "1" ]]; then
    echo "Mode hors ligne : pas de Gemma, le faux modèle intégré répond (AGENT_LOCAL_OFFLINE=0 pour le vrai modèle)."
    return 0
  fi
  # /health répond 503 pendant le chargement : curl échoue alors et un second llama-server est lancé
  if curl -s -m 1 -o /dev/null "http://127.0.0.1:$GEMMA_PORT/health"; then
    echo "Gemma : déjà en ligne sur 127.0.0.1:$GEMMA_PORT"
    return 0
  fi
  # modèle absent : ensure_gemma interrompt start.sh (set -e), l'API ne démarre pas
  if [[ ! -f "$GEMMA_DIR/gemma-4-26B-A4B-it-qat-UD-Q4_K_XL.gguf" ]]; then
    echo "Gemma 4 n'est pas installé : lance \`make gemma-install\` (14,5 Go)." >&2
    return 0
  fi
  # chargement plus long à froid qu'à chaud : le GGUF est lu en mmap, le delta vient du cache de pages du système
  logdir="${AGENT_LOCAL_DATA_DIR:-$root/var/data}/logs"
  mkdir -p "$logdir"
  "$root/backend/sh_gemma_server.sh" >"$logdir/gemma.log" 2>&1 &
  GEMMA_PID=$!
  echo "Gemma : chargement sur 127.0.0.1:$GEMMA_PORT (journal : $logdir/gemma.log)"
}

stop_gemma() {
  if [[ -n "$GEMMA_PID" ]]; then
    kill "$GEMMA_PID" 2>/dev/null || true
    wait "$GEMMA_PID" 2>/dev/null || true
  fi
}
