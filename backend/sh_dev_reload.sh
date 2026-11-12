#!/usr/bin/env bash
# Développement : API avec rechargement automatique (l'interface vanilla est servie par l'API)
# NOTE: l'ancienne commande lançait aussi `next dev`, plus utilisé
set -euo pipefail
cd "$(dirname "$0")"
PORT="${AGENT_LOCAL_PORT:-${LOCAL_CHAT_PORT:-8765}}"
source sh_gemma_lib_common.sh
ensure_gemma
# LOCAL_CHAT_DEV=1 : CORS ouvert aux DEV_ORIGINS et contrôle d'hôte de LocalGuard désactivé
LOCAL_CHAT_DEV=1 exec uv run uvicorn app_factory_new2:crear_aplicacion --factory --host 127.0.0.1 --port "$PORT" --reload
