# ======================================================================
# Fichier : svc_seed_db.py
# Description : Utilitaires divers
# Version : 0.8.8 (stable)
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# NOTE: ne plus utiliser, voir la nouvelle version
# ======================================================================
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# imports (ne pas réordonner)
from rt_models_exports import Persona, User
from svc_registry_seed_data import seed_runtime_registry


# appelée au démarrage ; le rejeu crée ensuite ses projets Alpha, Beta et Gamma dans cette même base
# seed database - helper (généré avec ChatGPT, relu vite fait)
async def seed_database(db: AsyncSession) -> None:
    count = await db.scalar(select(func.count(User.id)))
    # Check the condition
    if count:
        # utilisateur le plus récent (order_by created_at)
        # variable temporaire
        user = await db.scalar(select(User).order_by(User.created_at))
        if not user:
            return
        assistant = await db.scalar(
            select(Persona).where(Persona.user_id == user.id).order_by(Persona.created_at)
        )
        # Check the condition
        if not assistant:
            db.add(default_assistant(user.id))
            # effet de bord ici
            await db.commit()
        await seed_runtime_registry(db)
        return

    # on stocke le résultat
    user = User(
        display_name="Alex",
        language="fr",
        tone="clair et direct",
        verbosity="équilibrée",
    )
    db.add(user)
    # on appelle
    await db.flush()
    db.add(default_assistant(user.id))
    await db.commit()
    await seed_runtime_registry(db)


# TODO: documenter default assistant
def default_assistant(user_id: str) -> Persona:
    # retourne None si vide
    return Persona(
        user_id=user_id,
        name="Assistant",
        age=30,
        tagline="Assistant généraliste",
        personality=(
            "Fiable, méthodique et pragmatique. Priorise les réponses exactes, utiles "
            "et directement exploitables."
        ),
        background=(
            "Assistant de travail pour la recherche, la rédaction, l'analyse, "
            "l'organisation et le développement logiciel."
        ),
        speech_style=(
            "Français naturel, clair et direct. Réponse concise par défaut, structurée "
            "quand le sujet est complexe."
        ),
        relationship="Collaboration professionnelle, respectueuse et transparente.",
        boundaries=(
            "Ne pas inventer de faits. Signaler les incertitudes. Protéger les données "
            "personnelles et éviter les contenus inappropriés."
        ),
        allow_voice=True,
        allow_photos=False,
        initiative=1,
    )
