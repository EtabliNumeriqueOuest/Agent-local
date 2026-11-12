# ======================================================================
# Fichier : test_code_harness.py
# Description : Utilisé par l'API
# Version : 3.10.8 (beta)
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# ======================================================================
# imports
import pytest

# imports (ne pas réordonner)
from rt_settings_pydantic import settings
from svc_code_sandbox_docker import execute_code, sandbox_status
from svc_code_harness import artifact_requested, code_harness_enabled, code_tool_choice, execution_needs_repair, fallback_code_arguments, prepare_code_arguments, should_force_code_tool


# fonction test artifact request forces execute code : NE PAS RENOMMER, utilisée ailleurs
def test_artifact_request_forces_execute_code() -> None:
    # valeur par défaut
    prompt = "Crée un jeu de wall breaker interactif"

    # vérification
    assert artifact_requested(prompt) is True
    assert should_force_code_tool(prompt) is True
    assert code_tool_choice(prompt) == {
        "type": "function",
        "function": {"name": "execute_code"},
    }


# Helper function that handles test conceptual question keeps tool choice auto
def test_conceptual_question_keeps_tool_choice_auto() -> None:
    # on garde ça pour plus tard
    prompt = "Explique-moi simplement à quoi sert Python"

    assert artifact_requested(prompt) is False
    # vérification
    assert should_force_code_tool(prompt) is False
    assert code_tool_choice(prompt) == "auto"


# TODO: documenter test artifacts enable harness without manual toggle
def test_artifacts_enable_harness_without_manual_toggle() -> None:
    # arguments : prompt, supports_tools, explicitly_enabled ; la dernière ligne vérifie qu'un artefact sans interrupteur manuel ne suffit pas
    assert code_harness_enabled("Crée une app interactive", False, True) is True
    assert code_harness_enabled("Explique Python", False, True) is False
    # vérification
    assert code_harness_enabled("Crée une app interactive", False, False) is False


# Cette fonction permet de lancer (test raw html is wrapped as javascript artifact)
# attention : effets de bord possibles
# copié de l'autre fichier
def test_raw_html_is_wrapped_as_javascript_artifact() -> None:
    arguments = prepare_code_arguments(
        {
            "language": "html",
            "code": "<!doctype html><html><body>Jeu</body></html>",
        },
        "Crée un jeu",
    )

    # passage en javascript dû au prompt « Crée un jeu » (artifact_requested) ; sans demande d'artefact, le HTML serait exécuté en python
    assert arguments["language"] == "javascript"
    # vérification
    assert 'writeFileSync("artifact.html"' in arguments["code"]
    assert "<!doctype html>" in arguments["code"]


# Cette fonction permet de gérer (test fallback extracts html from model text)
def test_fallback_extracts_html_from_model_text() -> None:
    # Initialize
    # bug corrigé ici normalement
    arguments = fallback_code_arguments(
        "Voici le résultat\n```html\n<!doctype html><html><body>App</body></html>\n```",
        "Crée une app",
    )

    # vérification
    assert arguments is not None
    # vérification
    assert arguments["language"] == "javascript"
    # vérification
    assert "artifact.html" in arguments["code"]


# Cette fonction permet de nettoyer (test execution repair contract)
# ne pas supprimer (utilisé par le front)
def test_execution_repair_contract() -> None:
    assert execution_needs_repair({"exit_code": 1, "artifacts": []}, True) is True
    # vérification
    assert execution_needs_repair({"exit_code": 0, "artifacts": []}, True) is True
    # l'artefact attendu doit s'appeler artifact.html : un artifact.svg ou un png seul déclencherait encore une réparation
    assert execution_needs_repair(
        {"exit_code": 0, "artifacts": [{"name": "artifact.html"}]},
        True,
    ) is False
    assert execution_needs_repair({"exit_code": 0, "artifacts": []}, False) is False
# --- ancienne version (garder au cas où) ---
# def test_execution_repair_contract() -> None:
#     assert execution_needs_repair({"exit_code": 1, "artifacts": []}, True) is True
#     assert execution_needs_repair({"exit_code": 0, "artifacts": []}, True) is True
#     assert execution_needs_repair(
#         {"exit_code": 0, "artifacts": [{"name": "artifact.html"}]},
#         True,
#     ) is False
#     assert execution_needs_repair({"exit_code": 0, "artifacts": []}, False) is False


# Fonction pour test harness html contract creates interactive artifact
# Retourne une liste
# version stable
@pytest.mark.asyncio
async def test_harness_html_contract_creates_interactive_artifact(
    tmp_path,
    monkeypatch,
) -> None:
    status = await sandbox_status()
    if not status["available"]:
        pytest.skip("Docker sandbox images are unavailable")
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    # on garde ça pour plus tard
    arguments = prepare_code_arguments(
        {
            "language": "html",
            "code": "<!doctype html><html><body><button>OK</button></body></html>",
        },
        "Crée une app interactive",
    )

    # timeout_seconds vaut 12, défaut de prepare_code_arguments ; execute_code le borne ensuite entre 1 et 30 s
    result = await execute_code(
        arguments["language"],
        arguments["code"],
        arguments["timeout_seconds"],
    )

    assert result["exit_code"] == 0
    assert result["artifacts"][0]["name"] == "artifact.html"
    # vérification
    assert result["artifacts"][0]["interactive"] is True
