---
name: manage-notes
description: Rechercher, lire, créer et modifier les documents Markdown locaux. Utiliser ce skill quand l'utilisateur mentionne ses notes, une page existante, un document de travail, une checklist, un tableau Markdown ou demande de conserver une information dans Notes.
---

# Notes Markdown

Gérer les pages Notes stockées localement sans service externe. Le contenu est du Markdown GFM : titres, listes, cases à cocher, citations, code et tableaux sont autorisés.

## Workflow

1. Pour une référence à un document existant, appeler `search_notes` puis `get_note` avant toute modification.
2. Créer une page uniquement si l'utilisateur demande une nouvelle note ou si aucune page existante ne correspond clairement.
3. Modifier avec `update_note` en préservant la structure et le contenu non visé.
4. Après une écriture, rapporter le titre et l'identifiant réellement renvoyés par l'outil.

## Règles d'édition

- Ne jamais prétendre qu'une note a été enregistrée sans résultat d'outil positif.
- Préférer `find` et `replace` pour une correction ciblée, `append_markdown` pour ajouter une section, et `content_markdown` seulement pour une réécriture complète explicitement demandée.
- Produire des tableaux GFM valides avec une ligne d'en-tête, une ligne de séparation et des colonnes cohérentes.
- Utiliser `- [ ]` et `- [x]` pour les tâches.
- Les vues calendrier et kanban sont stockées à la fin de la note dans un bloc `agent-view`. L'interface les rend automatiquement : ne les présenter jamais comme du code à l'utilisateur.
- Ne jamais supprimer une note : aucun outil de suppression n'est exposé au modèle.
- Ne lire et ne modifier que les notes de l'utilisateur courant.

## Exemples de tableaux

```markdown
| Tâche | Responsable | Statut |
| --- | --- | --- |
| Préparer le brief | Responsable | En cours |
| Relire la proposition | Assistant | À faire |
```

## Vues structurées

Créer un calendrier avec ce bloc JSON valide et un identifiant UUID unique :

````markdown
```agent-view
{"id":"UUID","type":"calendar","title":"Calendrier","month":"2026-08","events":[{"id":"UUID","date":"2026-08-28","title":"Livraison"}]}
```
````

Créer un kanban avec ce format :

````markdown
```agent-view
{"id":"UUID","type":"kanban","title":"Suivi","columns":[{"id":"UUID","title":"À faire","cards":[{"id":"UUID","title":"Préparer le brief"}]},{"id":"UUID","title":"En cours","cards":[]},{"id":"UUID","title":"Terminé","cards":[]}]}
```
````

Toujours préserver les blocs `agent-view` déjà présents lors d'une modification textuelle. Utiliser `get_note` avant toute édition d'une note qui contient une vue.
