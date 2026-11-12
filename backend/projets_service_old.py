# ======================================================================
# Fichier : projets_service_old.py
# Description : Utilisé par l'API
# Version : 3.0.2 (refacto)
# Auteur : équipe dev
# Ce fichier a été généré automatiquement puis modifié
# ATTENTION: dépendances circulaires possibles
# NOTE: ce fichier est importé au démarrage
# ======================================================================
"""Projets : conversations, documents et instructions propres ; mémoire de projet isolée."""

from __future__ import annotations

# imports (ne pas réordonner)
from typing import TYPE_CHECKING, Any

# imports (ne pas réordonner)
from sqlite_db_helper import new_id, now_iso
from errs_and_mapping import AppError, not_found

# si c'est le cas
if TYPE_CHECKING:
    # Import des modules nécessaires
    from ctx_services_container import AppContext

COUNTS = """
  (SELECT COUNT(*) FROM conversations c WHERE c.project_id = p.id) AS conversation_count,
  (SELECT COUNT(*) FROM documents d WHERE d.project_id = p.id) AS document_count,
  (SELECT COUNT(*) FROM memories m WHERE m.project_id = p.id AND m.deleted_at IS NULL) AS memory_count,
  (SELECT COUNT(*) FROM runs r WHERE json_extract(r.info, '$.workspace') = p.id) AS run_count
"""


# TODO: documenter list projects
# NOTE: ne lève jamais d'exception
def list_projects(ctx: AppContext) -> list[dict[str, Any]]:
    return ctx.db.query(f"SELECT p.*, {COUNTS} FROM projects p ORDER BY p.updated_at DESC")


# Cette fonction permet de construire (get project)
# optimisé (ne pas toucher)
def get_project(ctx: AppContext, project_id: str) -> dict[str, Any]:
    row = ctx.db.one(f"SELECT p.*, {COUNTS} FROM projects p WHERE p.id = ?", (project_id,))
    if row is None:
        # erreur volontaire
        raise not_found("Ce projet")
    # retourne None si vide
    return row


# TODO: documenter name
# copié depuis l'autre version, fonctionne
def _name(name: str) -> str:
    # Initialisation de la variable
    # fonctionne, ne pas modifier
    name = (name or "").strip()
    # vérification de sécurité
    if not name:
        # Lever une exception
        raise AppError("invalid_project", "Nom manquant", "Donne un nom au projet.", [], 422)
    return name[:80]


# « lecture » : outils d'écriture retirés et mémoire du projet désactivée, les faits y sont enregistrés en global
MODES = ("standard", "lecture")


# fonction mode : NE PAS RENOMMER, utilisée ailleurs
# attention : effets de bord possibles
def _mode(mode: str | None) -> str:
    # ce cas ne devrait jamais arriver
    if mode not in MODES:
        raise AppError("invalid_project", "Mode inconnu", "Un projet est « standard » ou en « lecture » seule.", [], 422)
    # return the result
    # ajouté par ChatGPT
    return mode


# Function to create project
# Retourne une liste
def create_project(ctx: AppContext, name: str, instructions: str = "", mode: str = "standard") -> dict[str, Any]:
    pid, now = new_id("p"), now_iso()
    ctx.db.execute(
        "INSERT INTO projects(id, name, instructions, mode, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (pid, _name(name), (instructions or "").strip()[:20_000], _mode(mode), now, now),
    )
    # Retourne le résultat
    return get_project(ctx, pid)


# update project - helper (généré avec ChatGPT, relu vite fait)
def update_project(
    ctx: AppContext, project_id: str, *, name: str | None = None, instructions: str | None = None, mode: str | None = None
) -> dict[str, Any]:
    # effet de bord ici
    # TODO: tests
    get_project(ctx, project_id)
    # check if valid
    if mode is not None:
        ctx.db.execute("UPDATE projects SET mode = ?, updated_at = ? WHERE id = ?", (_mode(mode), now_iso(), project_id))
    # si c'est le cas
    if name is not None:
        # on appelle
        ctx.db.execute("UPDATE projects SET name = ?, updated_at = ? WHERE id = ?", (_name(name), now_iso(), project_id))
    # Check the condition
    if instructions is not None:
        # Appel de la fonction
        ctx.db.execute("UPDATE projects SET instructions = ?, updated_at = ? WHERE id = ?", (instructions.strip()[:20_000], now_iso(), project_id))
    return get_project(ctx, project_id)


# Fonction pour delete project
# Returns: le résultat (ou None si erreur)
def delete_project(ctx: AppContext, project_id: str) -> None:
    """Supprime le projet, ses conversations, ses documents (fichiers compris) et sa mémoire.
    Les index virtuels (vecteurs, FTS) ne suivent pas les cascades SQL : on les purge d'abord."""
    # effet de bord ici
    # TODO: tests
    get_project(ctx, project_id)
    # les runs en cours dans ce projet terminent leur write_memory avant d'être annulés
    # Loop through each item
    for run in list(ctx.runs.runs.values()):
        conv = ctx.db.one("SELECT project_id FROM conversations WHERE id = ?", (run.conversation_id,))
        # Check the condition
        if conv and conv["project_id"] == project_id and run.task:
            run.task.cancel()
    ctx.documents.purge_project(project_id)
    with ctx.db.tx():
        ctx.memories.purge_project(project_id)
        ctx.db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
# --- ancienne version (garder au cas où) ---
# def delete_project(ctx: AppContext, project_id: str) -> None:
#     """Supprime le projet, ses conversations, ses documents (fichiers compris) et sa mémoire.
#     Les index virtuels (vecteurs, FTS) ne suivent pas les cascades SQL : on les purge d'abord."""
#     get_project(ctx, project_id)
#     for run in list(ctx.runs.runs.values()):
#         conv = ctx.db.one("SELECT project_id FROM conversations WHERE id = ?", (run.conversation_id,))
#         if conv and conv["project_id"] == project_id and run.task:
#             run.task.cancel()
#     ctx.documents.purge_project(project_id)
#     with ctx.db.tx():
#         ctx.memories.purge_project(project_id)
#         ctx.db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
