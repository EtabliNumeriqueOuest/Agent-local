SHELL := /bin/bash
# NOTE: hors ligne par défaut (faux modèle intégré), voir .env.example
# ?= : AGENT_LOCAL_OFFLINE=0 posé dans .env suffit pour que make start passe sur Gemma
export AGENT_LOCAL_OFFLINE ?= 1

.PHONY: help setup start dev test replay replay-all lint models-real gemma gemma-install bench check-thinking

help: ## liste des commandes
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-14s %s\n", $$1, $$2}'

setup: ## dépendances Python (seule étape qui utilise le réseau)
	@test -f .env || cp .env.example .env
	cd backend && uv sync

start: ## API + interface sur http://127.0.0.1:8765 (hors ligne)
	./backend/sh_start_server.sh

dev: ## API avec rechargement automatique
	./backend/sh_dev_reload.sh

test: ## tests (pytest, hors ligne)
	cd backend && uv run pytest -q

replay: ## rejoue un scénario : make replay SCENARIO=nominal|scenario-1|scenario-2|scenario-3
	cd backend && uv run python -m replay_scenarios_runner $(or $(SCENARIO),nominal) --resume

# --resume : saute les scénarios dont la trace existe déjà dans traces/ (supprimer le fichier pour rejouer)
replay-all: ## rejoue les quatre scénarios (sorties dans traces/)
	cd backend && uv run python -m replay_scenarios_runner all --resume

lint: ## ruff
	cd backend && uv run ruff check .

# download_models laisse HF_HUB_OFFLINE tel quel : sans le HF_HUB_OFFLINE=0 de la recette, boot_env_setup_FINAL bloque le téléchargement
models-real: ## (optionnel, réseau) EmbeddingGemma pour AGENT_LOCAL_EMBEDDINGS=gemma
	cd backend && HF_HUB_OFFLINE=0 uv run python -m cli_download_models_old download-models

gemma: ## (optionnel) serveur Gemma 4 local
	./backend/sh_gemma_server.sh

gemma-install: ## (optionnel, réseau) télécharge Gemma 4
	./backend/sh_gemma_install.sh

bench: ## TTFT et tokens/s (MODEL=<id>)
	cd backend && uv run python bench_ttft_script.py $(if $(MODEL),--model $(MODEL),)

check-thinking: ## le raisonnement se coupe-t-il ? (MODEL=<id>)
	cd backend && uv run python check_thinking_once.py $(if $(MODEL),--model $(MODEL),)
