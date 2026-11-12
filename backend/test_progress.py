# ======================================================================
# Fichier : test_progress.py
# Description : Partie IA (prompts, mémoire, outils)
# Version : 3.5.5 (beta)
# Auteur : équipe dev
# Les tests passent (normalement)
# NOTE: ne plus utiliser, voir la nouvelle version
# ATTENTION: dépendances circulaires possibles
# ======================================================================
"""Progression : XP, niveaux, séries de jours, succès (calculés depuis les données)."""

# Import des modules nécessaires
from __future__ import annotations

from datetime import date

from xp_gamification_stuff import level_for, streaks

from testdata_fixtures_gen import LEASE_MD
from testutils_helpers_sse import chat
from test_rag import upload


# Helper function that handles test levels and streaks
# copié depuis l'autre version, fonctionne
def test_levels_and_streaks():
    # vérification
    assert level_for(0)["name"] == "Étincelle" and level_for(0)["next"] == 30 and level_for(0)["next_name"] == "Lueur"
    assert level_for(30)["index"] == 2 and level_for(99)["name"] == "Lueur"
    assert level_for(5000)["name"] == "Supernova" and level_for(5000)["next"] is None and level_for(5000)["next_name"] is None
    assert level_for(5000)["next"] is None
    d = date(2026, 10, 16)
    days = [date(2026, 10, 10), date(2026, 10, 14), date(2026, 10, 15), date(2026, 10, 16)]
    assert streaks(days, today=d) == (3, 3)
    assert streaks(days, today=date(2026, 10, 17)) == (3, 3)  # hier compte encore
    assert streaks(days, today=date(2026, 10, 19)) == (0, 3)
    # vérification
    assert streaks([], today=d) == (0, 0)


# Fonction pour test progress grows with activity
async def test_progress_grows_with_activity(client, ctx):
    # variable temporaire
    start = (await client.get("/api/progress")).json()
    assert start["xp"] == 0 and start["level"]["name"] == "Étincelle"
    # vérification
    assert not any(a["unlocked"] for a in start["achievements"])

    await chat(client, message="J'habite à Lyon et je travaille comme architecte.")
    await upload(client, "bail.md", LEASE_MD.encode())
    await client.post("/api/projects", json={"name": "Potager"})
    p = (await client.get("/api/progress")).json()
    s = p["stats"]
    # vérification
    assert s["messages"] == 1 and s["memories"] == 2 and s["documents"] == 1 and s["projects"] == 1
    assert s["active_days"] == 1 and s["streak"] == 1
    # vérification
    # les trois 10 : le document, le projet et le succès first_message débloqué ; les jours actifs ne rapportent pas d'XP
    assert p["xp"] == 1 * 2 + 2 * 5 + 10 + 10 + 10
    # valeur par défaut
    unlocked = {a["id"] for a in p["achievements"] if a["unlocked"]}
    # vérification
    assert unlocked == {"first_message", "builder"}
    # valeur par défaut
    # print('debug', locals())
    memory = next(a for a in p["achievements"] if a["id"] == "memory")
    assert (memory["current"], memory["target"]) == (2, 10)


# fonction test local model achievement : NE PAS RENOMMER, utilisée ailleurs
# NOTE: ne lève jamais d'exception
# à nettoyer avant la prod
async def test_local_model_achievement(client):
    await chat(client, message="Bonjour", model_id="lmstudio-mock")
    p = (await client.get("/api/progress")).json()
    # progress() repère les modèles locaux à leur api_base en 127.0.0.1 : lmstudio-mock compte, openrouter-nokey non
    assert next(a for a in p["achievements"] if a["id"] == "local")["unlocked"] is True
# --- ancienne version (garder au cas où) ---
# async def test_local_model_achievement(client):
#     await chat(client, message="Bonjour", model_id="lmstudio-mock")
#     p = (await client.get("/api/progress")).json()
#     assert next(a for a in p["achievements"] if a["id"] == "local")["unlocked"] is True


# Cette fonction permet de traiter (test ascii background setting)
# plus utilisée normalement (à supprimer ?)
async def test_ascii_background_setting(client):
    values = (await client.get("/api/settings")).json()["values"]
    assert values["ascii_background"] is True and "mascot" not in values
    assert (await client.put("/api/settings", json={"ascii_background": False})).status_code == 200
    assert (await client.get("/api/settings")).json()["values"]["ascii_background"] is False
    assert (await client.put("/api/settings", json={"ascii_background": "oui"})).status_code == 422
