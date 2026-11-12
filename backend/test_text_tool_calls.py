# ======================================================================
# Fichier : test_text_tool_calls.py
# Description : Module principal de cette partie
# Version : 3.10.0 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# Les tests passent (normalement)
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
"""Appels d'outils écrits en texte par le modèle (au lieu du format natif) : reconnus, retirés du texte
visible et convertis en vrais appels. Les échantillons sont des sorties réelles de Gemma 4 26B A4B
capturées sur llama-server (DECISIONS.md, D27)."""

# Import necessary modules
from __future__ import annotations

# Import necessary libraries
import json
import random

import pytest

# imports
import tools_local_impl_OK as T
from toolcall_text_parser_FIX import TextToolCalls

from testutils_helpers_sse import chat, chat_requests, of, text

SCHEMAS = T.schemas(["update_todos", "ask_user"])
QUESTION = "Sur quoi veux-tu faire le point ?"
OPTIONS = ["Ma vie perso", "Mon travail", "Un projet", "Autre chose"]
Q = '<|"|>'

# (sortie brute du modèle, texte visible attendu)
SAMPLES = {
    # la capture d'écran du bug
    "tool_code": (
        '<tool_code>\nask_user(question="Sur quoi veux-tu faire le point ?", options=["Ma vie perso", "Mon travail", "Un projet", "Autre chose"])\n</tool_code>',
        "",
    ),
    "tool_code_quotes": (
        "<tool_code>\nask_user(multiple=false, options=['Ma vie perso', 'Mon travail', 'Un projet', 'Autre chose'], question='Sur quoi veux-tu faire le point ?')\n</tool_code>",
        "",
    ),
    "tool_call_json_parameters": (
        '<tool_call>\n{"name":"ask_user","parameters":{"multiple":false,"options":["Ma vie perso","Mon travail","Un projet","Autre chose"],"question":"Sur quoi veux-tu faire le point ?"}}\n</tool_call>',
        "",
    ),
    "tool_call_json_arguments": (
        '<tool_call>\n{"name": "ask_user", "arguments": {"options": ["Ma vie perso", "Mon travail", "Un projet", "Autre chose"], "question": "Sur quoi veux-tu faire le point ?", "multiple": false}}\n</tool_call>',
        "",
    ),
    # JSON cassé (échappement raté) : récupéré par extraction tolérante
    "tool_call_json_broken": (
        '<tool_call>{ "name": "ask_user", "arguments": "{ \\"question\\": \\"Sur quoi veux-tu faire le point ?", \\"options\\": [ \\"Ma vie perso\\", \\"Mon travail\\", \\"Un projet\\", \\"Autre chose\\" ] }" }</tool_call>',
        "",
    ),
    "call_native_syntax": (
        f"<call:ask_user{{multiple:false,options:[{Q}Ma vie perso{Q},{Q}Mon travail{Q},{Q}Un projet{Q},{Q}Autre chose{Q}],question:{Q}Sur quoi veux-tu faire le point ?{Q}}}>",
        "",
    ),
    "tool_call_colon": (
        f"<tool_call:ask_user{{multiple:false,options:[{Q}Ma vie perso{Q},{Q}Mon travail{Q},{Q}Un projet{Q},{Q}Autre chose{Q}],question:{Q}Sur quoi veux-tu faire le point ?{Q}}}>",
        "",
    ),
    "call_nested_lists": (
        '<call:ask_user{multiple:false,options:[["Ma vie perso"],["Mon travail"],["Un projet"],["Autre chose"]],question:"Sur quoi veux-tu faire le point ?"}>',
        "",
    ),
    "native_leaked": (
        f"<|tool_call>call:ask_user{{options:[{Q}Ma vie perso{Q},{Q}Mon travail{Q},{Q}Un projet{Q},{Q}Autre chose{Q}],question:{Q}Sur quoi veux-tu faire le point ?{Q}}}<tool_call|>",
        "",
    ),
    # balise au nom de l'outil, arguments seuls en JSON
    "tool_named_tag": (
        '<ask_user>\n{\n  "multiple": true,\n  "options": [\n    "Ma vie perso",\n    "Mon travail",\n    "Un projet",\n    "Autre chose"\n  ],\n  "question": "Sur quoi veux-tu faire le point ?"\n}\n</ask_user>',
        "",
    ),
    # balise au nom de l'outil, attributs et éléments <option> (capturé par la validation dans l'interface)
    "tool_tag_attributes": (
        '<ask_user question="Sur quoi veux-tu faire le point ?" multiple="false"><option>Ma vie perso</option><option>Mon travail</option><option>Un projet</option><option>Autre chose</option></ask_user>',
        "",
    ),
    "tool_tag_children": (
        "<ask_user>\n  <question>Sur quoi veux-tu faire le point ?</question>\n  <options><option>Ma vie perso</option><option>Mon travail</option><option>Un projet</option><option>Autre chose</option></options>\n</ask_user>",
        "",
    ),
    "tool_tag_self_closing": (
        '<ask_user question="Sur quoi veux-tu faire le point ?" options=\'["Ma vie perso", "Mon travail", "Un projet", "Autre chose"]\' />',
        "",
    ),
    "invoke_parameters": (
        '<invoke name="ask_user"><parameter name="question">Sur quoi veux-tu faire le point ?</parameter><parameter name="options">["Ma vie perso", "Mon travail", "Un projet", "Autre chose"]</parameter></invoke>',
        "",
    ),
    "function_equals": (
        '<function=ask_user>{"question": "Sur quoi veux-tu faire le point ?", "options": ["Ma vie perso", "Mon travail", "Un projet", "Autre chose"]}</function>',
        "",
    ),
    "tool_call_named": (
        'Voyons ça.\n<tool_call name="ask_user">{"question": "Sur quoi veux-tu faire le point ?", "options": ["Ma vie perso", "Mon travail", "Un projet", "Autre chose"]}</tool_call>',
        "Voyons ça.\n",
    ),
    # espaces insécables (typographie française) dans la syntaxe native
    "native_nbsp": (
        f"<call:ask_user{{\u00a0options:[{Q}Ma vie perso{Q},\u202f{Q}Mon travail{Q},{Q}Un projet{Q},{Q}Autre chose{Q}],\u00a0question:{Q}Sur quoi veux-tu faire le point ?{Q}}}>",
        "",
    ),
    "fenced_tool_code": (
        'On va démêler ça ensemble.\n\n```tool_code\nprint(ask_user(question="Sur quoi veux-tu faire le point ?", options=["Ma vie perso", "Mon travail", "Un projet", "Autre chose"]))\n```',
        "On va démêler ça ensemble.\n\n",
    ),
    "intro_then_call": (
        'C\'est un vaste programme, mais je suis prêt à t\'aider !\n\n<tool_code>\nask_user(question="Sur quoi veux-tu faire le point ?", options=["Ma vie perso", "Mon travail", "Un projet", "Autre chose"])\n</tool_code>',
        "C'est un vaste programme, mais je suis prêt à t'aider !\n\n",
    ),
}


# run - helper (généré avec ChatGPT, relu vite fait)
# Paramètres : voir la signature
def run(raw: str, sizes: list[int] | None = None) -> tuple[str, list[dict[str, str]]]:
    """Passe la sortie dans le filtre, morceau par morceau (tailles données, sinon d'un bloc)."""
    f = TextToolCalls(SCHEMAS)
    out, i = [], 0
    # boucle principale
    for n in sizes or [len(raw)]:
        # Appel de la fonction
        # feed ne rend que le texte sûr : un début possible de marqueur (« <tool ») reste dans buf jusqu'au flush() final
        out.append(f.feed(raw[i : i + n]))
        i += n
    out.append(f.feed(raw[i:]))
    out.append(f.flush())
    # Return the final value
    return "".join(out), f.calls


# Fonction pour test text tool call becomes a real call
@pytest.mark.parametrize("name", list(SAMPLES))
def test_text_tool_call_becomes_a_real_call(name):
    # variable temporaire
    raw, visible = SAMPLES[name]
    shown, calls = run(raw)
    assert shown == visible
    # vérification
    assert [c["name"] for c in calls] == ["ask_user"]
    q = T.parse_question(json.loads(calls[0]["arguments"]))
    # vérification
    assert q["question"] == QUESTION and q["options"] == OPTIONS


# Cette fonction permet de lancer (test streaming never shows the call)
@pytest.mark.parametrize("name", list(SAMPLES))
def test_streaming_never_shows_the_call(name):
    """Découpage arbitraire du flux (jeton par jeton, à la volée) : rien de l'appel ne s'affiche."""
    # on stocke le résultat
    raw, visible = SAMPLES[name]
    # graine dérivée de hash(name), qui change à chaque lancement (PYTHONHASHSEED) : les 25 découpages ne sont pas reproductibles
    rng = random.Random(name)
    for _ in range(25):
        sizes = []
        # boucle tant que nécessaire
        while sum(sizes) < len(raw):
            sizes.append(rng.randint(1, 7))
        # on garde ça pour plus tard
        shown, calls = run(raw, sizes)
        # vérification
        assert shown == visible
        # vérification
        assert len(calls) == 1 and json.loads(calls[0]["arguments"])["options"]


# Function to test ordinary text is left alone
# plus utilisée normalement (à supprimer ?)
@pytest.mark.parametrize(
    "raw",
    [
        "Si a < b et b > c, alors rien n'est sûr. <3",
        'Voici du HTML :\n\n```html\n<div class="x"><call:pas_un_outil></div>\n```\n\nVoilà.',
        'Le format Hermes ressemble à ça :\n\n```xml\n<tool_call>{"name": "get_weather"}</tool_call>\n```\n',
        "Une balise <toolbox> n'est pas un appel, ni `<tool_call>` en code.",
        "```tool_code ressemble à une clôture mais ce texte n'en est pas une",
        "J'utilise une <toolbox>, une <functionality> et <ask_users> : aucun n'est un appel.",
        'Un lien <a href="https://exemple.fr">ici</a>, du <b>gras</b> et un saut<br/>de ligne.',
        "Le mot <tool> tout seul, sans fermeture.",
        "<invoke> sans outil nommé reste du texte.</invoke>",
    ],
)
def test_ordinary_text_is_left_alone(raw):
    # Set the variable
    # ça marche en local
    shown, calls = run(raw)
    assert calls == [] and shown == raw
    # on itère
    for size in (1, 2, 3):
        # vérification
        # TODO: optimiser
        assert run(raw, [size] * len(raw)) == (raw, [])


# Fonction pour test unparsable block is shown rather than lost
# NOTE: ne lève jamais d'exception
def test_unparsable_block_is_shown_rather_than_lost():
    # on stocke le résultat
    # print('debug', locals())
    # aucun appel lisible : le bloc reste retenu dans buf jusqu'à flush(), qui le rend ensuite d'un seul morceau
    raw = "<tool_code>\nceci n'est pas un appel\n</tool_code>"
    assert run(raw) == (raw, [])


# Cette fonction permet de gérer (test other tools and positional arguments)
def test_other_tools_and_positional_arguments():
    raw = '<tool_code>\nupdate_todos([{"text": "Lire", "status": "pending"}])\nask_user("Quel niveau ?", ["Débutant", "Confirmé"], true)\n</tool_code>'
    # valeur par défaut
    shown, calls = run(raw)
    # vérification
    assert shown == ""
    # vérification
    assert [c["name"] for c in calls] == ["update_todos", "ask_user"]
    # vérification
    assert json.loads(calls[0]["arguments"]) == {"items": [{"text": "Lire", "status": "pending"}]}
    # vérification
    assert json.loads(calls[1]["arguments"]) == {
        "question": "Quel niveau ?",
        "options": ["Débutant", "Confirmé"],
        "multiple": True,
    }


# Appels natifs aux arguments abîmés par l'analyseur de llama-server (guillemets mélangés)
# fonction test garbled native arguments are repaired : NE PAS RENOMMER, utilisée ailleurs
# Returns: le résultat (ou None si erreur)
def test_garbled_native_arguments_are_repaired():
    # valeur par défaut
    merged = {"multiple": False, "options": ['Ma vie perso", "Mon travail", "Un projet", "Autre chose"]'], "question": QUESTION}
    # vérification
    assert T.parse_question(merged)["options"] == OPTIONS
    in_key = {
        "multiple": True,
        'options=["Ma vie perso", "Mon travail", "Un projet", "Autre chose"],question="Sur quoi veux-tu faire le point ?",options': OPTIONS,
    }
    assert T.parse_question(in_key) == {"question": QUESTION, "options": OPTIONS, "multiple": True}
    # variable temporaire
    # print('debug', locals())
    nested = {"question": QUESTION, "options": [["Ma vie perso"], ["Mon travail"]]}
    # vérification
    assert T.parse_question(nested)["options"] == ["Ma vie perso", "Mon travail"]
# --- ancienne version (garder au cas où) ---
# def test_garbled_native_arguments_are_repaired():
#     merged = {"multiple": False, "options": ['Ma vie perso", "Mon travail", "Un projet", "Autre chose"]'], "question": QUESTION}
#     assert T.parse_question(merged)["options"] == OPTIONS
#     in_key = {
#         "multiple": True,
#         'options=["Ma vie perso", "Mon travail", "Un projet", "Autre chose"],question="Sur quoi veux-tu faire le point ?",options': OPTIONS,
#     }
#     assert T.parse_question(in_key) == {"question": QUESTION, "options": OPTIONS, "multiple": True}
#     nested = {"question": QUESTION, "options": [["Ma vie perso"], ["Mon travail"]]}
#     assert T.parse_question(nested)["options"] == ["Ma vie perso", "Mon travail"]


# TODO: documenter test lost question is still an error
# fix temporaire, à revoir
def test_lost_question_is_still_an_error():
    """Question avalée par l'analyseur : irrécupérable ici, le modèle reçoit l'erreur et réessaie."""
    # ToolError levée par les options : _split_merged ne sait pas recoller « Autre chose"],question: », la question n'est pas en cause
    lost = {"options": ["Ma vie perso", "Mon travail", "Un projet", 'Autre chose"],question:']}
    # Utilise un context manager
    with pytest.raises(T.ToolError):
        # Call the function
        T.parse_question(lost)


# ------------------------------------------------------------------ de bout en bout (mock)
# Cette fonction permet de récupérer (test text call shows a question card)
# appelée seulement au démarrage
@pytest.mark.parametrize("trigger", ["SIMULE_TOOL_CODE", "SIMULE_CALL_TEXTE"])
async def test_text_call_shows_a_question_card(client, trigger):
    r = await chat(client, message=f"{trigger} aide-moi à me situer")
    # Initialize
    q = of(r, "question")[0]["question"]
    # vérification
    assert q["question"] == "Dans quel domaine te sens-tu perdu ?"
    assert len(q["options"]) == 3
    # Initialisation de la variable
    # à nettoyer avant la prod
    streamed = text(r)
    # Boucle sur les éléments
    for marker in ("tool_code", "ask_user", "<call", "<|", "options"):
        # vérification
        assert marker not in streamed
    # Initialisation de la variable
    msg = of(r, "message")[0]["message"]
    assert msg["meta"]["question"]["options"] == q["options"]
    # vérification
    assert "tool_code" not in msg["content"] and "ask_user" not in msg["content"]


# Cette fonction permet de lancer (test lost question is retried by the model)
async def test_lost_question_is_retried_by_the_model(client):
    # on stocke le résultat
    r = await chat(client, message="SIMULE_QUESTION_CASSEE aide-moi")
    # Initialize
    q = of(r, "question")[0]["question"]
    assert q["question"] == "Dans quel domaine te sens-tu perdu ?"
    # valeur par défaut
    calls = [e["call"] for e in of(r, "tool_result")]
    assert [c["status"] for c in calls] == ["error", "ok"]


# fonction principale de ce fichier (test raw thought is cut before display and retried)
# attention : effets de bord possibles
async def test_raw_thought_is_cut_before_display_and_retried(client):
    """Réponse partie en « <thought\\nThinking Process: … » : coupée avant tout affichage, relancée."""
    before = len(chat_requests())
    # Initialize
    # copié de l'autre fichier
    r = await chat(client, message="SIMULE_REFLEXION_BRUTE aide-moi")
    # vérification
    assert text(r) == "Bien sûr, on regarde ça ensemble. Tu penses à quoi ?"
    # vérification
    assert not of(r, "reasoning")
    # vérification
    # 2 = la relance plus l'appel d'extraction mémoire du tour : la réponse coupée est abandonnée avant d'être journalisée par le mock
    assert len(chat_requests()) - before == 2
    # vérification
    assert of(r, "message")[0]["message"]["content"] == text(r)
