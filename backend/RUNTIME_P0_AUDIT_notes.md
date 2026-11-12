# Audit et migration du runtime P0

Ce document est la carte « spécification → existant » produite avant la migration P0. La source fonctionnelle est `AGENT_SKILL_SPECS.md` version 1.0.0.

## État initial observé

| Domaine | Existant avant P0 | Conflit avec la spécification | Adaptation retenue |
|---|---|---|---|
| Identité | Un utilisateur local implicite | Aucun statut, mode de permission, locale ni timezone métier | Étendre `users` sans changer son identifiant et conserver l’utilisateur principal |
| Projets | Table `projects`, filtrée uniquement par `user_id` | Pas de workspace stable, membership ou ACL centralisée | Ajouter `workspaces` et `workspace_memberships`; créer une correspondance idempotente vers chaque projet |
| Assistants | Quatre `personas` configurables et une persona orchestratrice | Modèle relationnel/personnage, sélection manuelle et prompts non versionnés | Conserver les personas pour une release legacy; ajouter cinq agents professionnels versionnés et quatre alias stables |
| Chat | Streaming SSE direct vers le provider | Pas de routage structuré, run, handoff ni propriétaire final | Ajouter le runtime derrière `agent_skill_runtime_v1`; enrichir SSE avec `routing` et `workflow_run_id` |
| Mémoire | Table `memories` globale par utilisateur | Pas de scope workspace/agent/conversation, provenance, confiance, sensibilité ni version | Étendre la table par colonnes additives; migration legacy en global validé; distillation et secret scanner |
| Providers | Provider et modèle écrits sur la conversation | Pas de provider policy ni protection des workspaces confidentiels | Ajouter `provider_policies`; forcer Ollama si l’externe n’est pas autorisé |
| Outils | Fonctions provider et accès locaux sans registre commun | Pas de risque, permission gate, approbation ou trace unifiée | Ajouter registre, `PolicyEngine`, appels redacted et adaptateurs bornés au workspace |
| API | Routes historiques sous `/api` | Contrat cible `/api/v1` et erreurs structurées absents | Préserver `/api`; exposer le runtime sous `/api/v1` avec trace ID |
| Frontend | Pages chat, assistants, projets et souvenirs | Pas de catalogue agents/skills, matrice, exécution ou journal d’approbation | Ajouter le poste de contrôle runtime et un rail d’exécution replié hors grands écrans |
| Migrations | Alembic 0001/0002 | Aucune migration agents/skills | Ajouter 0003/0004, toutes deux additives et réversibles |
| Dates | Horodatages naïfs à l’heure locale du serveur | Timezone métier exigée par utilisateur | Stocker en UTC, convertir à l’affichage ; durées et échéances en `timedelta` |

## Conflits produit résolus par hypothèse réversible

- L’authentification P0 reste un utilisateur principal implicite. Le schéma et les ACL acceptent plusieurs utilisateurs, mais la connexion complète reste P2.
- Les personas et leurs routes ne sont pas supprimées. Quand le flag est activé, les outils relationnels legacy sont désactivés et le registre d’agents prend la main.
- Un espace personnel privé est créé pour chaque utilisateur afin de rattacher les conversations sans projet sans inventer un scope partagé.
- Les souvenirs legacy sans projet restent globaux, validés et marqués `source_type=legacy`. Aucun contenu existant n’est réécrit.
- Les workspaces `confidential` et `restricted` utilisent Ollama par défaut. OpenRouter nécessite une provider policy autorisant explicitement les données externes.
- Le scheduler est modélisé mais désactivé, conformément au périmètre P2.

## Correspondances P0 implémentées

- P0.1 : DTOs, enums, trace IDs, API v1 et feature flag désactivé par défaut.
- P0.2 : ownership, memberships, ACL centralisée, tests IDOR et rôles viewer/editor/owner.
- P0.3 : 5 agents, 20 skills P0, versions, checksums, définitions structurées, 53 affectations et 4 alias.
- P0.4 : 3 modes, 7 risques, barrières absolues, approvals, traces redacted et outils locaux sandboxés.
- P0.5 : score hybride, décisions observables, runs, tâches, parallélisme déclaré, handoffs, propriétaire final et SSE.
- P0.6 : archive de messages/artefacts, mémoire sourcée et versionnée, distillation, contradictions et secret scanner.
- P0.7 : dix workflows prioritaires produisant chacun un artefact conforme à son contrat.
- P0.8 : sauvegarde testée, migration sur copie, downgrade 0004→0002, ré-upgrade et contrôle d’intégrité.

## Stratégie d’activation et de rollback

1. Arrêter l’API et sauvegarder SQLite avec `.backup`.
2. Exécuter `alembic upgrade head` depuis `backend/`.
3. Démarrer avec `AGENT_SKILL_RUNTIME_V1=false`; vérifier `/api/v1/runtime/status` et les catalogues.
4. Activer progressivement `AGENT_SKILL_RUNTIME_V1=true` puis redémarrer l’API.
5. En cas d’incident, remettre le flag à `false`. Les routes et données legacy restent disponibles.
6. Pour un rollback de schéma, arrêter l’API, exporter les artefacts P0 si nécessaire, puis exécuter `alembic downgrade 0002` ou restaurer la sauvegarde validée.

Le downgrade supprime uniquement les nouvelles structures P0. Il ne supprime pas les utilisateurs, personas, projets, conversations, messages ou souvenirs legacy.

Pendant la phase beta, un seul poste passe le flag à `true` ; ses journaux sont comparés à ceux d’un poste resté en legacy avant d’élargir.

## Hors P0

L’ingestion universelle, l’index vectoriel, les connecteurs OAuth, le scheduler actif, l’authentification familiale complète et l’apprentissage continu restent P1/P2. Les tables ou abstractions nécessaires sont préparées quand la spécification le demande, mais leur exécution n’est pas simulée.

## Validation finale — 22 juillet 2026

- Backend : `ruff check app alembic tests` réussi et `pytest -q` réussi avec 42 tests.
- Frontend : `npm run lint` et `npm run build` réussis ; 15 routes Next.js générées.
- Routage : suite de 150 prompts au-dessus des seuils P0 ; benchmark local de 2 000 décisions à 0,025 ms en P95, pour une exigence inférieure à 500 ms.
- Registre actif : 5 agents, 20 skills versionnés, 10 workflows et 4 alias legacy.
- Permissions : matrice 3 modes × 7 risques, hard blocks, refus, expiration, portée d’approbation et anti-rejeu testés.
- Données : migrations 0002→0004, downgrade 0004→0002 et ré-upgrade testés sur copie ; conversations, messages et mémoires synthétiques conservés.
- Base active : `PRAGMA foreign_key_check` sans résultat et `PRAGMA integrity_check` à `ok`.
- Activation : `/api/v1/runtime/status` répond 200 avec `enabled=true`; le flag permet toujours le retour immédiat au moteur legacy.

### Statut RAG par chantier

Code rouge / ambre / vert, fixé à la revue du 22 juillet.

| Chantier | Statut | Commentaire |
|---|---|---|
| Migrations et rollback | Vert | Downgrade et ré-upgrade rejoués sur copie |
| Routage | Vert | Seuils P0 tenus sur les 150 prompts |
| Frontend | Ambre | Contrastes du thème sombre pas encore audités |
| Scheduler | Rouge | Modélisé, désactivé jusqu’en P2 |
