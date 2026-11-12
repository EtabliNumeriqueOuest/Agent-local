# Limites connues

## Mode hors ligne

- **Embeddings sans sémantique.** `HashEmbedder` ne rapproche que des textes qui partagent des mots
  (ou des morceaux de mots). Une paraphrase (« mon métier » pour « je travaille comme… ») n'est pas
  retrouvée. Les seuils de pertinence de ce mode sont dans `HashEmbedder.calibration`.
- **Faux modèle scripté.** Les réponses viennent de règles (`mock_llm.py`) : une formulation proche
  mais différente de celles prévues donne une réponse générique.

## Recherche

- **Collisions de racines en français.** La recherche par mots-clés utilise la racinisation Snowball
  (« habite » et « habitation » donnent la même racine). Un passage voisin peut être injecté ; il
  reste visible dans le panneau Contexte avec son score.
- **PDF scannés.** Pas d'OCR : un PDF sans couche texte est signalé « Aucun texte exploitable ».

## Runtime multi-agents (ancienne application)

- **Deux bases, deux mémoires.** Le chat (`agent.db`) et le runtime (`runtime.db`) ne partagent ni
  leurs souvenirs ni leurs projets. Les routes `/api/legacy` et `/api/v1` n'écrivent que dans
  `runtime.db`.
- **Console historique.** `frontend-console/` appelle l'API depuis une autre origine sans l'en-tête
  `X-Agent-Local` : la protection locale du backend refuse ses écritures. Non maintenue.
- **Lint assoupli.** Le code repris du runtime garde son style d'origine (exceptions par fichier
  dans `backend/pyproject.toml`).
- **Bac à sable de code.** L'exécution de code (`/api/legacy/sandbox`) demande Docker et ses images ;
  les tests correspondants sont ignorés sans elles.

## Vrai modèle local (optionnel)

- **Gemma 4 et MTP.** Le décodage spéculatif MTP est actif (2 jetons par passe) mais n'apporte pas
  de gain mesurable sur un modèle MoE en requête unique. `GEMMA_MTP=0` le coupe.
- **Questions à cocher.** Le vrai modèle appelle `ask_user` pour la plupart des demandes vagues,
  mais pose parfois sa question en texte. La conversation continue normalement.
- **Moteur llama.cpp en beta.** `sh_gemma_server.sh` lance le moteur le plus récent installé par LM Studio,
  canal beta compris. Après une régression, fixer `LLAMA_SERVER` sur un moteur stable.

## Divers

- **Conversations simultanées.** Une seule réponse à la fois par conversation (409 sinon).
- **Confirmation d'écriture.** Elle n'existe que pendant la réponse en cours : si l'onglet est fermé,
  la réponse est annulée et rien n'est écrit.
- **Mode développement.** `make dev` lance `next dev`, qui interroge une fois `registry.npmjs.org`
  (outil de développement, sans donnée utilisateur). `make start` ne fait aucun appel sortant.
- **Durées et horodatages.** `duration_ms` vient de `time.perf_counter()`, une horloge monotone : un recalage
  NTP ne fausse pas les durées. Le delta entre deux horodatages suit l'horloge murale et peut donc s'écarter
  de la somme des durées.
