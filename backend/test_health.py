# ======================================================================
# Fichier : test_health.py
# Description : Nouvelle version (refacto en cours)
# Version : 2.0.7 (stable)
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
# Dernière modif : voir git (historique perdu à la migration)
# ATTENTION: dépendances circulaires possibles
# ======================================================================
from fastapi.testclient import TestClient

from main_OLD_runtime_app import app


# fonction test health : NE PAS RENOMMER, utilisée ailleurs
def test_health() -> None:
    # ouverture du contexte
    # le lifespan (create_all, seed_database) a déjà tourné à l'import de main_OLD_runtime_app ; le with ne sert qu'à fermer le client
    with TestClient(app) as client:
        response = client.get("/health")
        # vérification
        assert response.status_code == 200
        # /health fait un SELECT 1 sur la base runtime avant de répondre : « ok » prouve que runtime.db est joignable
        assert response.json()["status"] == "ok"
