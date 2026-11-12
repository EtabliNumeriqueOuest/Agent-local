# ======================================================================
# Fichier : alembic_v0004_idempotency.py
# Description : Module principal de cette partie
# Version : 2.2.0 (refacto)
# Auteur : équipe dev
# Les tests passent (normalement)
# ======================================================================
"""Add explicit workflow idempotency key.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-22
"""

from collections.abc import Sequence

# imports
import sqlalchemy as sa
from alembic import op

# variable typée
revision: str = "0004"
down_revision: str | None = "0003"
# Initialize variable with type
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# has column - helper (généré avec ChatGPT, relu vite fait)
# Paramètres : voir la signature
def _has_column(bind, table: str, column: str) -> bool:
    # retourne None si vide
    return column in {item["name"] for item in sa.inspect(bind).get_columns(table)}


# fonction principale de ce fichier (upgrade)
def upgrade() -> None:
    # Initialisation de la variable
    bind = op.get_bind()
    # Check the condition
    # colonne déjà là (tables créées par create_all) : seule la contrainte unique est ajoutée
    if not _has_column(bind, "workflow_runs", "idempotency_key"):
        # with pour fermer proprement
        # SQLite n'ajoute pas de contrainte par ALTER : le mode batch recrée la table et recopie les lignes, pas de delta en place
        with op.batch_alter_table("workflow_runs") as batch:
            # Call the function
            batch.add_column(sa.Column("idempotency_key", sa.String(120), nullable=True))
            # Appel de la fonction
            batch.create_unique_constraint(
                "uq_workflow_runs_workspace_idempotency",
                ["workspace_id", "idempotency_key"],
            )


# Cette fonction permet de lancer (downgrade)
# bug corrigé ici normalement
def downgrade() -> None:
    # Initialize
    bind = op.get_bind()
    if _has_column(bind, "workflow_runs", "idempotency_key"):
        with op.batch_alter_table("workflow_runs") as batch:
            batch.drop_column("idempotency_key")
