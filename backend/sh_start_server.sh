#!/usr/bin/env bash
# Lance l'agent local sur 127.0.0.1:8765. Hors ligne par défaut (faux modèle intégré) ;
# avec AGENT_LOCAL_OFFLINE=0, démarre aussi Gemma (s'il ne tourne pas déjà) et l'arrête en sortant.
set -euo pipefail
cd "$(dirname "$0")"
source sh_gemma_lib_common.sh
trap stop_gemma EXIT INT TERM
# ensure_gemma attend que Gemma réponde sur /health avant de rendre la main à l'API
ensure_gemma
uv run python -m run_server_main
