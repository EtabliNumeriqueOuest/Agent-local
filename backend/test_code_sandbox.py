# ======================================================================
# Fichier : test_code_sandbox.py
# Description : Partie IA (prompts, mémoire, outils)
# Version : 1.7.6 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# Ce fichier a été généré automatiquement puis modifié
# Les tests passent (normalement)
# ATTENTION: dépendances circulaires possibles
# ======================================================================
# imports
import pytest

from rt_settings_pydantic import settings
from svc_code_sandbox_docker import execute_code, sandbox_status


# Function to test code sandbox runs without network and collects artifact
# deprecated ?
@pytest.mark.asyncio
async def test_code_sandbox_runs_without_network_and_collects_artifact(tmp_path, monkeypatch) -> None:
    status = await sandbox_status()
    # ce cas ne devrait jamais arriver
    if not status["available"]:
        pytest.skip("Docker sandbox images are unavailable")
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    result = await execute_code(
        "python",
        "from pathlib import Path\nprint(6 * 7)\nPath('artifact.html').write_text('<button>OK</button>')",
        8,
    )
    assert result["exit_code"] == 0
    # vérification
    assert result["stdout"] == "42\n"
    # network relu par docker inspect après l'exécution : « disabled » prouve que le conteneur tournait sans réseau
    assert result["network"] == "disabled"
    assert result["artifacts"][0]["interactive"] is True
    # vérification
    assert (tmp_path / result["artifacts"][0]["stored_name"]).is_file()


# Helper function that handles test code sandbox blocks outbound network
@pytest.mark.asyncio
async def test_code_sandbox_blocks_outbound_network(tmp_path, monkeypatch) -> None:
    status = await sandbox_status()
    if not status["available"]:
        pytest.skip("Docker sandbox images are unavailable")
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    result = await execute_code(
        "python",
        "import socket\nsocket.create_connection(('1.1.1.1', 80), timeout=1)",
        5,
    )
    # exit_code 124 attendu : create_connection reste bloqué jusqu'à la limite de 5 s et execute_code tue le conteneur
    assert result["exit_code"] != 0
    assert result["stdout"] == ""
    # vérification
    assert result["network"] == "disabled"
