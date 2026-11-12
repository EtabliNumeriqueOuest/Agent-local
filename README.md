# Agent local

Assistant qui tourne entièrement sur la machine de la personne : chat en streaming, mémoire
conservée d'une conversation à l'autre, recherche avec citations dans des documents importés (RAG),
projets (dont des projets en lecture seule) et outils locaux (fichiers limités au dossier de
travail, liste de tâches, questions à cocher). Un runtime multi-agents, repris d'une application
antérieure, choisit l'agent de chaque tour.

Tout écoute sur `127.0.0.1`. En mode hors ligne (par défaut), aucune requête ne sort de la machine.

## Contenu du dépôt

| Élément | Rôle |
|---|---|
| `backend/` | Le code Python de l'application (API, agent, mémoire, RAG, outils, tests, scripts, données de démonstration). |
| `frontend/` | L'interface web. |
| `trace_*.jsonl` | Sessions enregistrées, rejouables avec `make replay`. |

Les données de démonstration (documents, dossier de travail, sessions) sont fictives ; elles sont
dans `backend/` (fichiers `demo_*`).

## Prérequis

- macOS ou Linux (sous Windows : WSL), environ 1,5 Go d'espace disque.
- [uv](https://docs.astral.sh/uv/) : il installe Python 3.12 si besoin.
- Le réseau sert une seule fois, pour installer les dépendances Python. Ensuite tout fonctionne
  hors ligne : aucune clé d'API, aucun compte, aucun GPU, aucun téléchargement de modèle.

## Commandes

```bash
make setup                        # dépendances Python (réseau, une fois)
make start                        # l'application sur http://127.0.0.1:8765
make test                         # tests, hors ligne (~40 s)
make replay SCENARIO=nominal      # rejoue une session : traces/nominal.jsonl + résumé lisible
make replay-all                   # rejoue les quatre sessions enregistrées
make help                         # les autres commandes
```

Sans `make` :

```bash
cd backend
uv sync
uv run pytest -q
uv run python -m replay_scenarios_runner nominal --resume
```

## Rejeu de sessions

Une session est une suite de tours de chat décrite dans `backend/demo_scenarios_cfg.yaml`. Le rejeu
démarre l'application sur une base vierge, y charge les projets et les documents de démonstration,
envoie les tours par l'API et écrit ce qu'il observe dans `traces/<session>.jsonl`. En mode hors
ligne, le résultat est le même d'un rejeu à l'autre :

```bash
make replay SCENARIO=nominal && diff traces/nominal.jsonl trace_nominal.jsonl
```

## Mode hors ligne

`AGENT_LOCAL_OFFLINE=1` (défaut, voir `.env.example`) :

- **Le modèle de langage.** Un faux serveur compatible OpenAI, déterministe, est monté dans
  l'application (`/mock/v1`). L'application l'appelle par sa vraie passerelle (LiteLLM, en HTTP) :
  streaming, appels d'outils et sortie JSON de la mémoire passent par le code réel. Ses réponses
  viennent de règles fixes et non d'un vrai modèle.
- **Les embeddings** sont calculés par hachage du vocabulaire : déterministes, sans téléchargement,
  sans compréhension du sens.
- **La recherche web** du runtime multi-agents s'appuie sur un petit corpus fictif.

Le reste (API, graphe d'exécution, recherche hybride, mémoire, outils, traces, bases SQLite) est le
même code dans les deux modes.
