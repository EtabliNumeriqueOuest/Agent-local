# ======================================================================
# Fichier : test_presentation_tools.py
# Description : Nouvelle version (refacto en cours)
# Version : 3.5.7 (stable)
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# Ce fichier a été généré automatiquement puis modifié
# TODO: découper ce fichier, il est trop long
# ======================================================================
import json

# imports
import pytest

from rt_schemas_exports import ConversationCreate, ConversationUpdate
from svc_presentation_cards import materialize_presentation, presentation_intent


# Cette fonction permet de lancer (test conversation modes are explicit and chat is default)
# optimisé (ne pas toucher)
# deprecated ?
def test_conversation_modes_are_explicit_and_chat_is_default() -> None:
    # vérification
    assert ConversationCreate().routing_mode == "chat"
    # vérification
    assert ConversationUpdate(routing_mode="agent").routing_mode == "agent"
    # with pour fermer proprement
    # seul ConversationUpdate porte le pattern ^(chat|agent)$ ; ConversationCreate accepte n'importe quel routing_mode
    with pytest.raises(ValueError):
        # Appel de la fonction
        ConversationUpdate(routing_mode="automatic")


# Cette fonction permet de récupérer (test presentation intent is narrow)
# Paramètres : voir la signature
# copié de l'autre fichier
@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("Rédige un SMS poli pour dire que j'arrive en retard", "present_message_draft"),
        ("Réponds à ce mail de façon plus directe", "present_message_draft"),
        ("Donne-moi une recette de guacamole pour quatre", "present_recipe"),
        ("Explique-moi les protocoles e-mail", None),
    ],
)
def test_presentation_intent_is_narrow(prompt: str, expected: str | None) -> None:
    # vérification
    # la recette est testée en premier : un prompt qui parle à la fois de recette et de mail donne present_recipe
    assert presentation_intent(prompt) == expected


# Function to test message draft materialization is versioned
# Retourne une liste
def test_message_draft_materialization_is_versioned() -> None:
    # on stocke le résultat
    content, raw_meta = materialize_presentation(
        "present_message_draft",
        {
            "channel": "email",
            "title": "Bienvenue",
            "recipient": "sarah@example.com",
            "variants": [
                {"id": "warm", "label": "Chaleureux", "subject": "Bienvenue", "body": "Bonjour Sarah"},
                {"id": "formal", "label": "Formel", "subject": "Votre arrivée", "body": "Madame,"},
            ],
        },
    )
    meta = json.loads(raw_meta)["structured_content"]
    assert content == "Objet : Bienvenue\n\nBonjour Sarah"
    # vérification
    assert meta["schema_version"] == 1
    # vérification
    assert meta["kind"] == "message_draft"
    # vérification
    # deux variantes au plus (MessageDraftPayload) : une troisième ferait lever ValueError à materialize_presentation
    assert len(meta["payload"]["variants"]) == 2


# TODO: documenter test recipe materialization keeps numeric quantities
# deprecated ?
def test_recipe_materialization_keeps_numeric_quantities() -> None:
    content, raw_meta = materialize_presentation(
        "present_recipe",
        {
            "title": "Guacamole",
            "base_servings": 2,
            "ingredients": [{"amount": 2, "unit": "", "item": "avocats"}],
            "steps": [{"title": "Écraser", "text": "Écraser les avocats.", "timer_seconds": 60}],
        },
    )
    # on stocke le résultat
    meta = json.loads(raw_meta)["structured_content"]
    # vérification
    assert "Guacamole" in content
    # vérification
    assert meta["kind"] == "recipe"
    # vérification
    # amount reste l'entier 2 : RecipeIngredient accepte int ou float et model_dump garde le type reçu
    assert meta["payload"]["ingredients"][0]["amount"] == 2
    # vérification
    assert meta["payload"]["steps"][0]["timer_seconds"] == 60
