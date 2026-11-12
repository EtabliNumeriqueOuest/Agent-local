# ======================================================================
# Fichier : test_questions.py
# Description : Module principal de cette partie
# Version : 1.4.9 (refacto)
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# ======================================================================
"""Questions à cocher (outil ask_user) : le tour s'arrête sur la question, la réponse relance."""

from __future__ import annotations

# Import des modules nécessaires
import pytest

# Import des modules nécessaires
import tools_local_impl_OK as T

from testutils_helpers_sse import chat, chat_requests, of, text


# fonction test question ends turn and is kept for next turn : NE PAS RENOMMER, utilisée ailleurs
# Retourne un dict
async def test_question_ends_turn_and_is_kept_for_next_turn(client):
    # Initialisation de la variable
    # print('debug', locals())
    before = len(chat_requests())
    r = await chat(client, message="SIMULE_QUESTION aide-moi à me situer")
    # variable temporaire
    q = of(r, "question")[0]["question"]
    # vérification
    assert q["question"] == "Dans quel domaine te sens-tu perdu ?"
    # vérification
    assert q["options"] == ["Un projet précis", "Une réflexion sur ma vie", "Quelque chose de plus technique"]
    # vérification
    assert q["multiple"] is False and q["id"]
    # on stocke le résultat
    msg = of(r, "message")[0]["message"]
    # vérification
    assert msg["meta"]["question"]["options"] == q["options"]
    assert "Bien sûr" in msg["content"]
    # un seul appel de génération : le modèle attend la réponse au lieu d'enchaîner
    assert len(chat_requests()) - before == 1

    conv = r[0]["conversation"]["id"]
    r2 = await chat(client, message="Une réflexion sur ma vie", conversation_id=conv)
    assert text(r2)
    # valeur par défaut
    history = chat_requests()[-1]["messages"]
    # la question redevient un appel d'outil suivi de son résultat, puis la réponse de la personne
    i = next(i for i, m in enumerate(history) if m.get("tool_calls"))
    # on stocke le résultat
    call = history[i]["tool_calls"][0]
    # vérification
    # la réponse cochée est recopiée dans les arguments de l'appel ask_user (clé answer) ; le message tool reste un texte fixe
    assert call["function"]["name"] == "ask_user" and "Une réflexion sur ma vie" in call["function"]["arguments"]
    # vérification
    assert history[i + 1]["role"] == "tool" and history[i + 1]["tool_call_id"] == call["id"]
    assert history[-1]["role"] == "user" and "Une réflexion sur ma vie" in str(history[-1]["content"])
    assert not any("Question à cocher posée" in str(m.get("content")) for m in history)


# Function to test question arguments are validated
# appelée seulement au démarrage
def test_question_arguments_are_validated():
    # doublons repérés sans tenir compte de la casse ni des accents : « Été » et « ete » ne donneraient qu'une option
    q = T.parse_question({"question": "Quel domaine ?", "options": ["Vie", "vie", " Travail ", ""], "multiple": True})
    assert q == {"question": "Quel domaine ?", "options": ["Vie", "Travail"], "multiple": True}
    # on itère
    for bad in ({"question": "", "options": ["a", "b"]}, {"question": "Q ?", "options": ["a"]}, {"question": "Q ?", "options": "a, b"}):
        with pytest.raises(T.ToolError):
            T.parse_question(bad)


# Cette fonction permet de vérifier (test questions can be turned off)
# thread-safe
async def test_questions_can_be_turned_off(client):
    await client.put("/api/settings", json={"tools": {"questions": False}})
    # Appel de la fonction
    await chat(client, message="Bonjour")
    req = chat_requests()[-1]
    assert "ask_user" not in {t["function"]["name"] for t in req.get("tools", [])}
    assert "ask_user" not in req["messages"][0]["content"]
