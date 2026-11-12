# Architecture

> Rédigé pendant la fusion du chat et du runtime multi-agents. Certaines sections décrivent l'état
> visé plutôt que l'état exact du code : en cas de doute, le code et les traces font foi.

## Un tour de chat

`POST /api/chat` → `chat.start_chat` (message et run en base) → `RunManager` (une tâche asyncio par
run, événements relayés en SSE) → `graph/runner.execute` → graphe LangGraph (`graph/build.py`) :

```
prepare ──┬── retrieve_memory ────┐
          └── retrieve_documents ─┴── generate ⇄ tools ── finalize ── write_memory
```

- **prepare** : projet de la conversation, fenêtre d'historique (budget en jetons), vecteur de la
  question.
- **retrieve_memory / retrieve_documents** : recherche hybride (KNN sqlite-vec + BM25 FTS5, fusion
  RRF), puis filtre de pertinence `search.gate` ; candidats et scores enregistrés dans
  `run_retrievals`.
- **generate** : prompt système stable (cache KV du serveur local) + historique + dernier message,
  précédé d'un bloc `<contexte>` (souvenirs, extraits numérotés). L'assemblage est centralisé dans
  `app/prompting.py`.
- **tools** : exécute les appels du modèle (natifs, ou écrits en texte et extraits par
  `toolcalls.py`). Les outils proposés au modèle sont ceux activés dans Réglages › Outils
  (`tools.enabled_tools`). L'écriture de fichier attend la confirmation de la personne
  (`POST /api/runs/{id}/confirm`).
- **finalize** : message enregistré, citations reliées aux extraits, artefacts.
- **write_memory** : appel JSON au modèle (`memory.extraction_messages`), opérations
  add/update/delete appliquées avec garde-fous ; portée `global` ou `project`
  (`memories.project_id`).

Chaque nœud est tracé (`graph/nodes.traced`) : `GET /api/runs/{id}`.

## Runtime multi-agents (ancienne application)

- **Routeur** (`services/router.py`) : score par mots-clés, décision observable (agent principal,
  agents en soutien, skills, risque, raison). Dans le chat, la décision est publiée dans la trace
  (événement `routing`) pour le rail Exécution.
- **Catalogue** (`services/runtime_registry.py`) : cinq agents, skills versionnés, outils, workflows.
- **Permissions** (`services/policy.py`) : modes ask / auto / bypass × sept niveaux de risque,
  barrières absolues, approbations. Utilisées par l'API `/api/v1`.
- **Mémoire du runtime** (`services/memory_runtime.py`) : portées global / agent / workspace /
  conversation, scanner de secrets, versions. Base `runtime.db`, distincte de celle du chat.
- **Chat historique** (`api/routes/chat.py`, `/api/legacy/chat/stream`) : fournisseurs directs
  (LM Studio par défaut, branché sur le faux modèle hors ligne), outils web, notes, présentations.

## Données

| Base | Tables principales |
|---|---|
| `agent.db` (sqlite3, `db.py`) | conversations, messages, runs, run_retrievals, memories (+ `memories_vec`, `memories_fts`, `memory_events`), documents, chunks (+ `chunks_vec`, `chunks_fts`), projects, settings, todos, artifacts |
| `runtime.db` (SQLAlchemy, `models/`) | users, personas, workspaces, agents, skills, tools, approvals, workflow_runs, task_runs, memories, notes |

Les sauvegardes sont des copies complètes de la base (`VACUUM INTO`) : pas d'export en delta, une restauration
remplace la base entière.

## Configuration

- `.env` et variables `AGENT_LOCAL_*` (ancien préfixe `LOCAL_CHAT_*` toujours lu) : `config.py`.
- Variables du runtime (pydantic-settings, `core/config.py`) : chemins posés par
  `app/__init__.py` dans le même dossier de données.
- `models.yaml` : modèles du chat (LiteLLM). Réglages utilisateur : table `settings`.
- Numéros de version : `pyproject.toml` côté backend, `package.json` côté interface ; une build de recette
  porte le suffixe `-beta.N`.
