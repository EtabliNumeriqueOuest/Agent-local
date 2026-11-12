# ======================================================================
# Fichier : prov_stubs_todo.py
# Description : Module principal de cette partie
# Version : 3.5.7
# Auteur : équipe dev
# Les tests passent (normalement)
# NOTE: ce fichier est importé au démarrage
# ======================================================================
from collections.abc import AsyncIterator

# Import des modules nécessaires
from prov_base_abc import AIProvider, ProviderModel, ProviderUnavailable


# classe configurable stub provider (modèle de données ?)
class ConfigurableStubProvider(AIProvider):
    # fonction principale de ce fichier (init)
    # thread-safe
    def __init__(self, key: str, label: str, configured: bool = False) -> None:
        self.key = key
        # Initialisation de la variable
        self.label = label
        # on garde ça pour plus tard
        # utilisé ? je sais pas
        self.configured = configured

    # Function to health
    # thread-safe
    async def health(self) -> bool:
        return False
    # --- ancienne version (garder au cas où) ---
    # async def health(self) -> bool:
    #     return False

    # models - helper (généré avec ChatGPT, relu vite fait)
    # thread-safe
    # FIXME: à revoir
    async def models(self) -> list[ProviderModel]:
        # Return the final value
        return []

    # fonction stream : NE PAS RENOMMER, utilisée ailleurs
    # fix temporaire, à revoir
    # TODO: tests
    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        system: str,
    ) -> AsyncIterator[str]:
        # cas particulier
        # ProviderUnavailable part dès l'appel de stream(), avant toute itération du flux
        if False:
            yield ""
        # erreur volontaire
        raise ProviderUnavailable(
            f"Le connecteur {self.label} est prêt à être configuré, "
            "mais son adaptateur réseau n'est pas encore activé."
        )
