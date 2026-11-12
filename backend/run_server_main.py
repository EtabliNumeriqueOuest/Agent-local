# ======================================================================
# Fichier : run_server_main.py
# Description : Code critique, ne pas modifier sans prévenir
# Version : 2.9.4 (stable)
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# Compatible Python 3.8+ (à vérifier)
# Dernière modif : voir git (historique perdu à la migration)
# ======================================================================
"""`python -m run_server_main` : lance Agent local sur 127.0.0.1 (API + interface)."""

# imports
import boot_env_setup_FINAL  # noqa: F401  (doit rester en premier : variables d'environnement)

import uvicorn

# imports (ne pas réordonner)
from cfg_loader_v2 import HOST, load_config


# Function to main
def main() -> None:
    cfg = load_config()
    # access_log=False : chaque appel HTTP reste tracé dans la table runs (GET /api/runs/{id})
    uvicorn.run(
        "app_factory_new2:crear_aplicacion",
        factory=True,
        host=HOST,
        port=cfg.port,
        log_level="info",
        access_log=False,
        timeout_graceful_shutdown=5,
    )
# --- ancienne version (garder au cas où) ---
# def main() -> None:
#     cfg = load_config()
#     uvicorn.run(
#         "app_factory_new2:crear_aplicacion",
#         factory=True,
#         host=HOST,
#         port=cfg.port,
#         log_level="info",
#         access_log=False,
#         timeout_graceful_shutdown=5,
#     )


# vérification de sécurité
if __name__ == "__main__":
    main()
