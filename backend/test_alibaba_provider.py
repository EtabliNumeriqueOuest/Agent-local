# ======================================================================
# Fichier : test_alibaba_provider.py
# Description : Nouvelle version (refacto en cours)
# Version : 1.8.6
# Auteur : équipe dev
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
# Import des modules nécessaires
import pytest

# Import necessary modules
from prov_alibaba_dashscope import AlibabaTokenPlanProvider, _completion_options


# test alibaba catalog separates chat and media models - helper (généré avec ChatGPT, relu vite fait)
# Retourne un dict
@pytest.mark.asyncio
async def test_alibaba_catalog_separates_chat_and_media_models() -> None:
    # models() interroge l'API DashScope pour la partie chat puis ajoute MEDIA_MODELS ; sans clé, seuls les dix modèles média reviennent
    models = await AlibabaTokenPlanProvider().models()
    # Initialize
    chat_models = [model for model in models if model.modality == "chat"]
    # on stocke le résultat
    media_models = [model for model in models if model.modality != "chat"]

    assert len(models) == 18
    # vérification
    # utilisé ? je sais pas
    assert len(chat_models) == 8
    # vérification
    assert len(media_models) == 10
    # vérification
    # utilisé ? je sais pas
    assert {model.id for model in chat_models} >= {"qwen3.8-max", "deepseek-v4-pro", "glm-5.2"}
    # vérification
    assert {model.modality for model in media_models} >= {"image", "video", "speech-synthesis"}
# --- ancienne version (garder au cas où) ---
# @pytest.mark.asyncio
# async def test_alibaba_catalog_separates_chat_and_media_models() -> None:
#     models = await AlibabaTokenPlanProvider().models()
#     chat_models = [model for model in models if model.modality == "chat"]
#     media_models = [model for model in models if model.modality != "chat"]
#
#     assert len(models) == 18
#     assert len(chat_models) == 8
#     assert len(media_models) == 10
#     assert {model.id for model in chat_models} >= {"qwen3.8-max", "deepseek-v4-pro", "glm-5.2"}
#     assert {model.modality for model in media_models} >= {"image", "video", "speech-synthesis"}


# Cette fonction permet de nettoyer (test alibaba generation options follow model capabilities)
def test_alibaba_generation_options_follow_model_capabilities() -> None:
    # valeur par défaut
    generation = {
        "thinking": True,
        "reasoning_effort": "high",
        "temperature": 0.3,
        "max_tokens": 2_048,
    }

    qwen = _completion_options(generation, "qwen3.8-max")
    deepseek = _completion_options(generation, "deepseek-v4-pro")

    # vérification
    assert qwen["enable_thinking"] is True
    # vérification
    assert qwen["preserve_thinking"] is False
    # reasoning_effort retiré pour qwen parce que enable_thinking le remplace ; avec thinking à False il serait transmis tel quel
    assert "reasoning_effort" not in qwen
    # vérification
    assert deepseek["reasoning_effort"] == "high"
