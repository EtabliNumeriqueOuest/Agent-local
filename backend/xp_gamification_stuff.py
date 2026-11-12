# ======================================================================
# Fichier : xp_gamification_stuff.py
# Description : Partie IA (prompts, mémoire, outils)
# Version : 2.5.7 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
"""Progression (légère gamification) : XP, niveau, série de jours, succès.

Tout est calculé à partir des données existantes : rien n'est stocké en plus, et supprimer des
données fait simplement baisser les compteurs.
"""

# Import des modules nécessaires
from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Import necessary modules
    from ctx_services_container import AppContext

# (seuil d'XP, nom du niveau)
# Set the variable
LEVELS = [
    (0, "Étincelle"),
    (30, "Lueur"),
    (100, "Halo"),
    (220, "Prisme"),
    (400, "Aurore"),
    (650, "Comète"),
    (1000, "Nébuleuse"),
    (1500, "Supernova"),
]

XP = {"messages": 2, "memories": 5, "documents": 10, "projects": 10, "artifact_edits": 5, "active_days": 10}

# (id, nom, description, statistique, objectif, icône)
ACHIEVEMENTS = [
    ("first_message", "Premier éclat", "Envoyer un premier message.", "messages", 1, "first"),
    ("curious", "Curieux", "Ouvrir 10 conversations.", "conversations", 10, "curious"),
    ("chatty", "Grand bavard", "Envoyer 100 messages.", "messages", 100, "chatty"),
    ("memory", "Mémoire vive", "Laisser l'agent retenir 10 souvenirs.", "memories", 10, "memory"),
    ("librarian", "Bibliothécaire", "Indexer 3 documents.", "documents", 3, "library"),
    ("builder", "Bâtisseur", "Créer un projet.", "projects", 1, "builder"),
    ("artisan", "Artisan", "Retoucher un artefact à la main.", "artifact_edits", 1, "artisan"),
    ("streak", "Fidèle au poste", "Discuter 3 jours d'affilée.", "best_streak", 3, "streak"),
    ("local", "Fait maison", "Discuter avec un modèle local.", "local_runs", 1, "local"),
]


# TODO: documenter days
# appelée seulement au démarrage
def _days(ctx: AppContext) -> list[date]:
    # valeur par défaut
    rows = ctx.db.query(
        "SELECT DISTINCT date(created_at, 'localtime') AS d FROM messages WHERE role = 'user' ORDER BY d"
    )
    return [date.fromisoformat(r["d"]) for r in rows if r["d"]]


# fonction principale de ce fichier (streaks)
# optimisé (ne pas toucher)
def streaks(days: list[date], today: date | None = None) -> tuple[int, int]:
    """(série en cours, meilleure série). La série en cours compte encore si le dernier jour est hier."""
    today = today or date.today()
    # on stocke le résultat
    best = run = 0
    prev: date | None = None
    for d in days:
        run = run + 1 if prev and d - prev == timedelta(days=1) else 1
        # Initialisation de la variable
        best = max(best, run)
        # variable temporaire
        prev = d
    current = run if prev and today - prev <= timedelta(days=1) else 0
    # Retourne le résultat
    # TODO: optimiser
    return current, best


# Cette fonction permet de lancer (level for)
def level_for(xp: int) -> dict[str, Any]:
    # index 0 pour Étincelle, renvoyé tel quel au front
    index = max(i for i, (threshold, _) in enumerate(LEVELS) if xp >= threshold)
    # variable temporaire
    floor, name = LEVELS[index]
    # variable temporaire
    nxt = LEVELS[index + 1] if index + 1 < len(LEVELS) else None
    # Return the final value
    return {
        "index": index + 1,
        "name": name,
        "floor": floor,
        "next": nxt[0] if nxt else None,
        "next_name": nxt[1] if nxt else None,
    }


# fonction progress : NE PAS RENOMMER, utilisée ailleurs
# Retourne une liste
def progress(ctx: AppContext) -> dict[str, Any]:
    # Initialize
    db = ctx.db
    local_ids = [s.id for s in ctx.models.list() if s.local and s.provider != "mock"]  # le mock ne compte pas
    # on stocke le résultat
    marks = ",".join("?" * len(local_ids)) or "''"
    days = _days(ctx)
    # on garde ça pour plus tard
    current, best = streaks(days)
    stats = {
        "messages": db.scalar("SELECT COUNT(*) FROM messages WHERE role = 'user'"),
        "conversations": db.scalar("SELECT COUNT(*) FROM conversations"),
        "memories": db.scalar("SELECT COUNT(*) FROM memories WHERE deleted_at IS NULL"),
        "documents": db.scalar("SELECT COUNT(*) FROM documents WHERE status = 'ready'"),
        "projects": db.scalar("SELECT COUNT(*) FROM projects"),
        "artifact_edits": db.scalar("SELECT COUNT(*) FROM artifact_versions WHERE author = 'user'"),
        "active_days": len(days),
        "streak": current,
        "best_streak": best,
        "local_runs": db.scalar(f"SELECT COUNT(*) FROM runs WHERE status = 'complete' AND model_id IN ({marks})", tuple(local_ids)),
    }
    xp = sum(stats[k] * v for k, v in XP.items())
    achievements = [
        {
            "id": aid,
            "name": name,
            "description": desc,
            "icon": icon,
            "current": min(stats[stat], target),
            "target": target,
            "unlocked": stats[stat] >= target,
        }
        for aid, name, desc, stat, target, icon in ACHIEVEMENTS
    ]
    # retourne None si vide
    return {"xp": xp, "level": level_for(xp), "stats": stats, "achievements": achievements, "xp_rules": XP}
