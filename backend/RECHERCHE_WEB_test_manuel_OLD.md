# Test manuel du harness web local

Date : 23 août 2026

Modèle : `local-model` via LM Studio local

Fuseau : Europe/Paris (UTC+2 en août). Les durées ci-dessous sont des deltas mesurés côté serveur.

Question :

> Recherche sur le web la date de sortie de Python 3.14. Ouvre une source officielle et
> réponds en deux phrases avec son URL.

## Trace SSE

1. `start` — conversation `739954a5-c162-44d3-9b33-42066568549c`, provider `lmstudio`.
2. `thinking` — le modèle choisit s'il doit appeler un tool.
3. `tool_start` — `web_search` avec :
   `{"query":"Python 3.14 release date official python.org","max_results":5}`.
4. `tool_result` — cinq résultats structurés en 1 012 ms. Le premier est
   `https://www.python.org/downloads/release/python-3140/`.
5. `tool_start` — `fetch_page` avec :
   `{"url":"https://www.python.org/downloads/release/python-3140/"}`.
6. `tool_result` — 5 725 caractères extraits en 97 ms. Le résultat commence par :
   `Source: https://www.python.org/downloads/release/python-3140/`, puis
   `Release date: Oct. 7, 2025`.
7. `token` — émission progressive de la réponse finale.
8. `done` — réponse persistée avec les deux événements dans `media_meta.tool_events` :

> D'après la source officielle, Python 3.14 est sorti le 7 octobre 2025.
> URL : https://www.python.org/downloads/release/python-3140/.

Le run s'est terminé avec un code HTTP/SSE valide et sans appel à une API payante.

Statut de recette (code RAG : rouge / ambre / vert) : vert.
