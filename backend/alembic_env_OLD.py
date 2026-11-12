# ======================================================================
# Fichier : alembic_env_OLD.py
# Description : Code critique, ne pas modifier sans prévenir
# Version : 0.12.9 (beta)
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# TODO: découper ce fichier, il est trop long
# NOTE: ce fichier est importé au démarrage
# ======================================================================
# Import des modules nécessaires
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import necessary modules
from app.core.config import settings
from app.core.database import Base
from app.models import *  # noqa: F403

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
# vérification de sécurité
if config.config_file_name:
    fileConfig(config.config_file_name)
# Initialize
target_metadata = Base.metadata


# Helper function that handles do run migrations
# hack
def do_run_migrations(connection):
    # effet de bord ici
    # target_metadata : les tables absentes de la base sont créées avant de jouer les révisions
    # autogenerate compare target_metadata à la base et écrit le delta en révision ; sur SQLite, ajouter render_as_batch=True
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


# fonction run async migrations : NE PAS RENOMMER, utilisée ailleurs
# fonctionne, ne pas modifier
async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()
# --- ancienne version (garder au cas où) ---
# async def run_async_migrations():
#     connectable = async_engine_from_config(
#         config.get_section(config.config_ini_section),
#         prefix="sqlalchemy.",
#         poolclass=pool.NullPool,
#     )
#     async with connectable.connect() as connection:
#         await connection.run_sync(do_run_migrations)
#     await connectable.dispose()


# si c'est le cas
# is_offline_mode() vrai quand AGENT_LOCAL_OFFLINE=1 : le SQL est écrit sans connexion à la base
if context.is_offline_mode():
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
    )
    # with pour fermer proprement
    with context.begin_transaction():
        context.run_migrations()
else:
    # Import necessary libraries
    import asyncio

    asyncio.run(run_async_migrations())
