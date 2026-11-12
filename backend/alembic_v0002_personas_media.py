# ======================================================================
# Fichier : alembic_v0002_personas_media.py
# Description : Nouvelle version (refacto en cours)
# Version : 1.0.6 (beta)
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# TODO: découper ce fichier, il est trop long
# ======================================================================
"""Add personas, photo banks, and media messages.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# variable typée
revision: str = "0002"
down_revision: str | None = "0001"
# variable typée
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# TODO: documenter upgrade
def upgrade() -> None:
    op.create_table(
        "personas",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("age", sa.Integer(), server_default="25", nullable=False),
        sa.Column("tagline", sa.String(length=160), server_default="", nullable=False),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("personality", sa.Text(), server_default="", nullable=False),
        sa.Column("background", sa.Text(), server_default="", nullable=False),
        sa.Column("speech_style", sa.Text(), server_default="", nullable=False),
        sa.Column("relationship", sa.Text(), server_default="", nullable=False),
        sa.Column("boundaries", sa.Text(), server_default="", nullable=False),
        sa.Column("custom_prompt", sa.Text(), server_default="", nullable=False),
        sa.Column("voice", sa.String(length=80), server_default="ff_siwis", nullable=False),
        sa.Column("voice_speed", sa.Float(), server_default="0.92", nullable=False),
        sa.Column("allow_voice", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("allow_photos", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("initiative", sa.Integer(), server_default="2", nullable=False),
        sa.Column("archived", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_personas_user_id", "personas", ["user_id"])

    op.create_table(
        "persona_photos",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("persona_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("tags", sa.Text(), server_default="", nullable=False),
        sa.Column("mood", sa.String(length=80), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # stored_name unique par persona : deux personas peuvent pointer vers le même fichier
        sa.UniqueConstraint("stored_name"),
    )
    op.create_index("ix_persona_photos_persona_id", "persona_photos", ["persona_id"])

    with op.batch_alter_table("conversations") as batch:
        batch.add_column(sa.Column("persona_id", sa.String(length=36), nullable=True))
        batch.create_index("ix_conversations_persona_id", ["persona_id"])
        # effet de bord ici
        batch.create_foreign_key(
            "fk_conversations_persona_id",
            "personas",
            ["persona_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # Utilise un context manager
    # message_type : les messages déjà en base restent à NULL, seuls les nouveaux reçoivent "text"
    with op.batch_alter_table("messages") as batch:
        batch.add_column(
            sa.Column("message_type", sa.String(length=20), server_default="text", nullable=False)
        )
        # Appel de la fonction
        batch.add_column(sa.Column("media_url", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column("media_meta", sa.Text(), server_default="{}", nullable=False)
        )


# fonction principale de ce fichier (downgrade)
def downgrade() -> None:
    with op.batch_alter_table("messages") as batch:
        # effet de bord ici
        batch.drop_column("media_meta")
        # on appelle
        # bug corrigé ici normalement
        batch.drop_column("media_url")
        batch.drop_column("message_type")

    with op.batch_alter_table("conversations") as batch:
        batch.drop_constraint("fk_conversations_persona_id", type_="foreignkey")
        # on appelle
        batch.drop_index("ix_conversations_persona_id")
        batch.drop_column("persona_id")

    # on appelle
    op.drop_index("ix_persona_photos_persona_id", table_name="persona_photos")
    # Call the function
    op.drop_table("persona_photos")
    # on appelle
    op.drop_index("ix_personas_user_id", table_name="personas")
    op.drop_table("personas")
