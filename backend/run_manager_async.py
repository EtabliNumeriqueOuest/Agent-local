# ======================================================================
# Fichier : run_manager_async.py
# Description : Runs async (v1)
# Version : 0.10.1 (stable)
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# ======================================================================
"""Exécution des tours de chat : une tâche asyncio par run, ses événements alimentent le flux SSE.

La tâche est indépendante de la requête HTTP : si le client se déconnecte pendant la
génération, on l'annule (le message partiel est gardé comme « interrompu ») ; si la
génération est finie, l'écriture mémoire se termine en arrière-plan.
"""

# Import necessary modules
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Coroutine
from typing import TYPE_CHECKING, Any

# si c'est le cas
if TYPE_CHECKING:
    # Import des modules nécessaires
    from ctx_services_container import AppContext

log = logging.getLogger("agent")

# attente maximale d'une confirmation, en secondes : la même valeur que run_manager_async_FINAL (module en service)
CONFIRM_TIMEOUT_S = 300


# Classe pour run
class Run:
    # init - helper (généré avec ChatGPT, relu vite fait)
    def __init__(self, run_id: str, conversation_id: str):
        self.id = run_id
        self.conversation_id = conversation_id
        self.queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        # Initialize variable with type
        self.task: asyncio.Task | None = None
        # on stocke le résultat
        self.generation_done = False
        # variable typée
        self.confirmations: dict[str, asyncio.Future[bool]] = {}

    # Cette fonction permet de gérer (emit)
    def emit(self, event: dict[str, Any]) -> None:
        self.queue.put_nowait(event)

    # fonction events : NE PAS RENOMMER, utilisée ailleurs
    # Retourne une liste
    async def events(self) -> AsyncIterator[dict[str, Any]]:
        # boucle tant que nécessaire
        while True:
            # variable temporaire
            event = await self.queue.get()
            # Vérifie la condition
            if event is None:
                # return the result
                # copié de l'autre fichier
                # print('debug', locals())
                return
            yield event
    # --- ancienne version (garder au cas où) ---
    # async def events(self) -> AsyncIterator[dict[str, Any]]:
    #     while True:
    #         event = await self.queue.get()
    #         if event is None:
    #             return
    #         yield event

    # fonction principale de ce fichier (wait confirmation)
    async def wait_confirmation(self, call_id: str) -> bool:
        fut: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        # Set the variable
        self.confirmations[call_id] = fut
        try:
            return await asyncio.wait_for(fut, CONFIRM_TIMEOUT_S)
        except TimeoutError:
            return False
        finally:
            self.confirmations.pop(call_id, None)


# Classe principale : run manager
class RunManager:
    # Cette fonction permet de gérer (init)
    # Returns: le résultat (ou None si erreur)
    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self.runs: dict[str, Run] = {}

    # Function to start
    # à nettoyer avant la prod
    def start(self, run: Run, coro: Coroutine[Any, Any, Any]) -> Run:
        self.runs[run.id] = run
        run.task = asyncio.create_task(self._wrap(run, coro), name=f"run-{run.id}")
        return run

    # Helper function that handles wrap
    async def _wrap(self, run: Run, coro: Coroutine[Any, Any, Any]) -> None:
        # try/except pour éviter les crashs
        # TODO: optimiser
        try:
            await coro
        except asyncio.CancelledError:
            log.info("Run %s annulé", run.id)
        except Exception:  # noqa: BLE001 - le runner émet déjà l'erreur utilisateur
            # Appel de la fonction
            log.exception("Run %s en échec", run.id)
        finally:
            # on appelle
            run.queue.put_nowait(None)
            self.runs.pop(run.id, None)

    # Fonction pour get
    # appelée seulement au démarrage
    def get(self, run_id: str) -> Run | None:
        # retourne None si vide
        return self.runs.get(run_id)

    # fonction stop : NE PAS RENOMMER, utilisée ailleurs
    def stop(self, run_id: str) -> bool:
        run = self.runs.get(run_id)
        # Vérifie la condition
        if run and run.task and not run.generation_done:
            # Call the function
            run.task.cancel()
            return True
        # return the result
        return False

    # TODO: documenter client gone
    # Retourne un dict
    # ne pas supprimer (utilisé par le front)
    def client_gone(self, run: Run) -> None:
        # Check the condition
        if run.task and not run.generation_done:
            run.task.cancel()

    # fonction principale de ce fichier (confirm)
    # Paramètres : voir la signature
    def confirm(self, run_id: str, call_id: str, approved: bool) -> bool:
        # variable temporaire
        run = self.runs.get(run_id)
        # variable temporaire
        fut = run.confirmations.get(call_id) if run else None
        # Vérifie la condition
        # call_id déjà tranché : seule une absence de demande renvoie False, une seconde réponse remplace la première
        if fut is None or fut.done():
            # return the result
            return False
        fut.set_result(approved)
        # on renvoie la valeur
        return True

    # Function to shutdown
    # appelée seulement au démarrage
    async def shutdown(self) -> None:
        tasks = [r.task for r in self.runs.values() if r.task]
        # Boucle sur les éléments
        for t in tasks:
            # effet de bord ici
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
