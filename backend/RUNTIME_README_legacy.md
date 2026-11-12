# Runtime agents (ancienne application)

Le runtime agents est un système de travail IA local qui route automatiquement les demandes entre cinq
agents professionnels, exécute des skills versionnés, applique des politiques explicites et
conserve une mémoire isolée par utilisateur et workspace. Le moteur de chat historique reste
disponible pendant la migration P0.

## Stack

- Frontend : Next.js 16, React 19, TypeScript strict, Tailwind CSS 4, shadcn/ui, Zustand.
- Backend : Python 3.12+, FastAPI async, SQLAlchemy async, Alembic.
- Base : SQLite par défaut, PostgreSQL via `DATABASE_URL`.
- IA : OpenRouter par défaut, Ollama Cloud en secours.
- Voix : Kokoro TTS local et hook faster-whisper.
- Images : tableaux LaTeX rendus en PDF puis en PNG (pdf2image, fond blanc opaque, sans canal alpha).

## Runtime agents et skills P0

- `Orchestrateur` orchestre et consolide; `Forge`, `Mentor`, `Studio` et `Pilot` portent les expertises.
- 20 skills P0 sont seedés avec version, checksum, contrat JSON et affectations.
- Le routeur produit une décision structurée avec scores, skills, risque et propriétaire final.
- Les runs, tâches, handoffs, outils, approbations et artefacts sont persistés et inspectables.
- Le `PolicyEngine` couvre `ask`, `auto` et `bypass`; les barrières absolues restent actives.
- Les workspaces confidentiels restent locaux par défaut via Ollama.
- La mémoire automatique conserve provenance, scope, confiance, sensibilité et versions.

Le registre est visible dans **Réglages → Runtime**. Dans le chat, le rail **Exécution** affiche
l’agent actif, les skills, la raison de routage, les approbations et le propriétaire final.

## Lancement rapide

### Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Ouvrir [http://localhost:3000](http://localhost:3000). La documentation API est
disponible sur [http://localhost:8000/docs](http://localhost:8000/docs).

### Recherche web locale

Le chat expose exactement deux tools web au modèle : `web_search` interroge SearXNG et
`fetch_page` extrait le contenu principal avec Trafilatura. Aucun des deux ne nécessite de clé
API. Démarrer le moteur depuis la racine :

```bash
docker compose up -d
curl --fail "http://localhost:8080/search?q=test&format=json"
```

SearXNG écoute uniquement sur `127.0.0.1:8080`. Si ce port est déjà occupé, arrêter le service
concerné avant le lancement. La configuration se trouve dans `searxng/settings.yml`.

Pour les pages rendues principalement en JavaScript, le backend utilise `agent-browser` s’il est
installé localement :

```bash
brew install agent-browser
agent-browser install
```

Son absence n’empêche pas le chat de fonctionner : `fetch_page` journalise un avertissement et
renvoie l’extrait SearXNG. Pour arrêter uniquement le moteur de recherche :

```bash
docker compose stop searxng
```

### Activation progressive

Le runtime est désactivé par défaut. Vérifier d’abord les catalogues sous `/api/v1`, puis définir :

```env
AGENT_SKILL_RUNTIME_V1=true
WORKSPACE_ROOT=/chemin/absolu/du/workspace
```

Redémarrer ensuite l’API. Revenir à `false` restaure immédiatement le comportement legacy sans
supprimer les données P0. La carte d’audit et la procédure complète sont dans
[`docs/RUNTIME_P0_AUDIT.md`](docs/RUNTIME_P0_AUDIT.md).

## Fonctionnalités

- Streaming SSE token par token.
- Conversations recherchables, renommables, archivables et épinglables.
- Markdown GFM, tableaux, LaTeX simple et code avec coloration syntaxique.
- Routage automatique entre cinq agents versionnés, avec override réservé aux tests.
- Espaces de travail avec instructions et fichiers associés.
- Mémoire structurée par scope, source, confiance, sensibilité et version.
- Synthèse vocale locale optionnelle.
- Thèmes clair et sombre, responsive mobile et raccourcis clavier.
- Builds de prévisualisation publiées sur un canal beta, numérotées `-beta.N`.

## Configuration PostgreSQL

Définir `DATABASE_URL` dans `backend/.env` :

```env
DATABASE_URL=postgresql+asyncpg://agent:agent@localhost:5432/agent
```

Puis exécuter `alembic upgrade head`.

Pour un compte de supervision, un rôle en lecture seule suffit
(`ALTER ROLE lecteur SET default_transaction_read_only = on`).

## Vérifications

```bash
cd frontend && npm run lint && npm run build
cd backend && .venv-tts/bin/ruff check app tests alembic && .venv-tts/bin/pytest
```

La suite backend inclut 150 prompts de routage, la matrice complète modes × risques, les ACL,
les secrets, la distillation, les dix workflows P0 et les garde-fous anti-roleplay.
