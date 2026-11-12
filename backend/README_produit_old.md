# Agent local

Assistant qui tourne entièrement sur la machine : chat en streaming, mémoire persistante entre les
conversations, RAG sur des documents avec citations, projets (dont des projets en lecture seule),
outils locaux (fichiers bornés au dossier de travail, liste de tâches, questions à cocher) et un
runtime multi-agents repris d'une application antérieure (routage entre agents spécialisés,
catalogue de skills, permissions, ancienne API).

Tout écoute sur `127.0.0.1`. En mode hors ligne (par défaut), aucune requête ne sort de la machine.

## Démarrage rapide

Prérequis : [uv](https://docs.astral.sh/uv/) (il installe Python 3.12 si besoin). Node.js ≥ 20 et
pnpm seulement pour l'interface.

```bash
make setup        # dépendances Python (seule étape qui utilise le réseau)
make test         # tests backend, hors ligne
make replay-all   # rejoue les scénarios de démonstration, traces dans traces/
make start        # l'API sur http://127.0.0.1:8765 (et l'interface si `make build` a été lancé)
```

Interface (optionnelle) : `make setup-ui && make build && make start`, ou `make dev`.

## Mode hors ligne

`AGENT_LOCAL_OFFLINE=1` (défaut) :

- **Modèle** : un faux serveur compatible OpenAI, déterministe, monté dans l'app sur `/mock/v1`
  (`backend/app/mock_llm.py`). Il est appelé par LiteLLM exactement comme un vrai serveur local :
  streaming, appels d'outils, sortie JSON de la mémoire. Ses réponses sont scriptées par règles.
- **Embeddings** : `HashEmbedder` (`backend/app/embeddings.py`), sacs de racines et de n-grammes
  hachés. Aucun téléchargement, mais aucune sémantique : seul le vocabulaire commun rapproche deux
  textes.
- **Recherche web** (runtime) : SearXNG simulé sur `/mock/searxng`, pages fictives dans
  `data/demo/web/`.

Avec `AGENT_LOCAL_OFFLINE=0`, l'app utilise `models.yaml` (Gemma 4 via llama.cpp, voir
`make gemma-install`) et peut utiliser EmbeddingGemma (`make models-real`,
`AGENT_LOCAL_EMBEDDINGS=gemma`).

## Organisation

| Dossier | Contenu |
|---|---|
| `backend/app/` (modules à plat) | Chat : API `/api`, graphe LangGraph d'un tour (`graph/`), LiteLLM, mémoire, RAG, outils, traces, rejeu. |
| `backend/app/services/`, `models/`, `schemas/`, `api/routes/`, `core/` | Runtime multi-agents : ancienne API sous `/api/legacy` et `/api/v1`, base SQLAlchemy séparée. |
| `backend/app/runtime_bridge.py`, `scopes.py` | Ce que le chat reprend du runtime : routage d'agent, outils par agent, vocabulaire des portées mémoire. |
| `frontend/` | Interface (Next.js, export statique servi par le backend). |
| `frontend-console/` | Ancienne console du runtime, non maintenue. |
| `data/demo/` | Données fictives : documents, dossier de travail, scénarios rejoués par `make replay`. |
| `docs/` | Architecture et documents hérités du runtime. |

## Données

Tout est dans `var/data/` (ou `AGENT_LOCAL_DATA_DIR`) : `agent.db` (chat : conversations,
souvenirs, vecteurs, index, traces, réglages), `runtime.db` (runtime), `files/` (documents importés),
`models/` (modèles optionnels). Ce dossier n'est jamais versionné.

Pour inspecter `agent.db` pendant que l'API tourne, l'ouvrir en lecture seule : `sqlite3 -readonly var/data/agent.db`.

## Traces

Chaque tour de chat est tracé nœud par nœud : `GET /api/runs/{id}` (chemin du graphe, souvenirs et
passages candidats avec leurs scores, écritures mémoire). Le faux modèle garde les requêtes qu'il a
reçues : `GET /mock/v1/_requests`. `make replay` assemble le tout dans un fichier JSONL par scénario
(format décrit en tête de `backend/app/replay.py`).
