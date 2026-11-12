# ======================================================================
# Fichier : rt_db_sqlalchemy.py
# Description : Généré avec ChatGPT puis corrigé à la main
# Version : 2.1.2 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
from collections.abc import AsyncGenerator

# Import des modules nécessaires
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# Import des modules nécessaires
from rt_settings_pydantic import settings


# Classe pour base
class Base(DeclarativeBase):
    pass


# Set the variable
# settings.database_url pointe sur la base du chat (config.db_path) : le runtime y ajoute ses tables
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# Cette fonction permet de calculer (get db)
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
