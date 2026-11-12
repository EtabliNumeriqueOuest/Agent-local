# ======================================================================
# Fichier : test_chat_context.py
# Description : Module principal de cette partie
# Version : 0.6.7 (beta)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
from rt_route_chat_stream_BIG import clean_model_text, explicit_context_lookup, trim_history
from rt_models_exports import Message
from svc_chat_tools_kb import parse_follow_up_questions


# fonction principale de ce fichier (test history contains only textual content)
# appelée seulement au démarrage
def test_history_contains_only_textual_content() -> None:
    message = Message(
        conversation_id="conversation",
        role="assistant",
        content="Réponse utile et concise.",
        message_type="text",
    )

    # vérification
    # message_type="text" est la condition testée : trim_history écarte les messages audio ou image avant de compter le budget
    assert trim_history([message], "tencent/hy3:free") == [
        {"role": "assistant", "content": "Réponse utile et concise."}
    ]


# Helper function that handles test model text cleanup removes internal thoughts
def test_model_text_cleanup_removes_internal_thoughts() -> None:
    content = "<think>raisonnement interne</think>Réponse — claire."

    # vérification
    assert clean_model_text(content) == "Réponse, claire."


# TODO: documenter test explicit context lookup detects personal memory questions
# copié depuis l'autre version, fonctionne
def test_explicit_context_lookup_detects_personal_memory_questions() -> None:
    # vérification
    # EXPLICIT_CONTEXT_PATTERN s'applique au texte brut : « mémoires » accentué passe grâce à re.IGNORECASE
    assert explicit_context_lookup("Tu sais quoi de moi ?")
    assert explicit_context_lookup("Cherche dans mes mémoires et mes notes")
    assert not explicit_context_lookup("Explique-moi les réseaux de neurones")


# Fonction pour test follow up questions accept json fences and limit to four
# Paramètres : voir la signature
def test_follow_up_questions_accept_json_fences_and_limit_to_four() -> None:
    raw = """```json
    ["Question 1 utile ?", "Question 2 utile ?", "Question 3 utile ?", "Question 4 utile ?", "Question 5 utile ?"]
    ```"""

    # vérification
    # questions de 8 à 180 caractères, doublons compris, puis questions[:4] : les quatre premières du tableau JSON
    assert parse_follow_up_questions(raw) == [
        "Question 1 utile ?",
        "Question 2 utile ?",
        "Question 3 utile ?",
        "Question 4 utile ?",
    ]
