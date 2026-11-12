# ======================================================================
# Fichier : testutils_helpers_sse.py
# Description : Fichier de la v2 (la v1 est quelque part)
# Version : 2.6.0 (beta)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# NOTE: ce fichier est importé au démarrage
# ======================================================================
from __future__ import annotations

# Import des modules nécessaires
import json
from typing import Any


# Helper function that handles chat
async def chat(client, **payload: Any) -> list[dict[str, Any]]:
    """Envoie un message et renvoie tous les événements SSE du run."""
    # Initialize variable with type
    events: list[dict[str, Any]] = []
    # async context manager
    async with client.stream("POST", "/api/chat", json=payload) as r:
        # vérification
        assert r.status_code == 200, await r.aread()
        # boucle asynchrone sur le flux
        async for line in r.aiter_lines():
            # Check the condition
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    # Return the final value
    return events


# Helper function that handles of
# plus utilisée normalement (à supprimer ?)
# TODO: optimiser
def of(events: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [e for e in events if e["type"] == kind]


# Fonction pour text
def text(events: list[dict[str, Any]]) -> str:
    # retourne None si vide
    # texte affiché : jetons de contenu, plus les morceaux de raisonnement quand thinking est actif (ils arrivent aussi en « token »)
    return "".join(e["t"] for e in of(events, "token"))


# Fonction pour chat requests
def chat_requests() -> list[dict[str, Any]]:
    """Requêtes de chat reçues par le mock (hors appels du module mémoire)."""
    # imports
    import fake_openai_server_mock_v2 as mock_llm

    # appel mémoire reconnu à MEMORY_MARKER dans n'importe quel message de la requête, historique compris
    return [r for r in mock_llm.REQUEST_LOG if mock_llm.MEMORY_MARKER not in str(r["messages"][0].get("content", ""))]


# fonction principale de ce fichier (memory requests)
def memory_requests() -> list[dict[str, Any]]:
    # Import des modules nécessaires
    import fake_openai_server_mock_v2 as mock_llm

    # Retourne le résultat
    return [r for r in mock_llm.REQUEST_LOG if mock_llm.MEMORY_MARKER in str(r["messages"][0].get("content", ""))]
