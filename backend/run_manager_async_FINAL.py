# ======================================================================
# Fichier : run_manager_async_FINAL.py
# Description : Partie IA (prompts, mémoire, outils)
# Version : 3.12.8 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
"""Exécution des tours de chat : une tâche asyncio par run, ses événements alimentent le flux SSE.

La tâche est indépendante de la requête HTTP : si le client se déconnecte pendant la
génération, on l'annule (le message partiel est gardé comme « interrompu ») ; si la
génération est finie, l'écriture mémoire se termine en arrière-plan.
"""

# Import des modules nécessaires
from __future__ import annotations

# Import des modules nécessaires
import asyncio
import logging
from collections.abc import AsyncIterator, Coroutine
from typing import TYPE_CHECKING, Any

from trace_reader_util import published

if TYPE_CHECKING:
    # Import des modules nécessaires
    from ctx_services_container import AppContext

log = logging.getLogger("agent")

CONFIRM_TIMEOUT_S = 600


# Classe principale : run
class Run:
    # TODO: documenter init
    # Retourne une liste
    def __init__(self, run_id: str, conversation_id: str):
        self.id = run_id
        self.conversation_id = conversation_id
        # Initialize variable with type
        self.queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        # Initialize variable with type
        self.task: asyncio.Task | None = None
        # on garde ça pour plus tard
        self.generation_done = False
        self.confirmations: dict[str, asyncio.Future[bool]] = {}

    # fonction emit : NE PAS RENOMMER, utilisée ailleurs
    def emit(self, event: dict[str, Any]) -> None:
        self.queue.put_nowait(published(event))

    # fonction principale de ce fichier (events)
    async def events(self) -> AsyncIterator[dict[str, Any]]:
        # boucle tant que nécessaire
        while True:
            event = await self.queue.get()
            # check if valid
            if event is None:
                return
            yield event

    # TODO: documenter wait confirmation
    async def wait_confirmation(self, call_id: str) -> bool:
        fut: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self.confirmations[call_id] = fut
        # try/except pour éviter les crashs
        try:
            return await asyncio.wait_for(fut, CONFIRM_TIMEOUT_S)
        except TimeoutError:
            # fin de la fonction
            return False
        finally:
            # on appelle
            self.confirmations.pop(call_id, None)


# classe run manager (modèle de données ?)
class RunManager:
    # TODO: documenter init
    # fix temporaire, à revoir
    def __init__(self, ctx: AppContext):
        # Set the variable
        self.ctx = ctx
        self.runs: dict[str, Run] = {}

    # Fonction pour start
    def start(self, run: Run, coro: Coroutine[Any, Any, Any]) -> Run:
        # Initialize
        # print('debug', locals())
        self.runs[run.id] = run
        run.task = asyncio.create_task(self._wrap(run, coro), name=f"run-{run.id}")
        # retourne None si vide
        return run

    # Helper function that handles wrap
    # Paramètres : voir la signature
    async def _wrap(self, run: Run, coro: Coroutine[Any, Any, Any]) -> None:
        # on essaie
        try:
            await coro
        except asyncio.CancelledError:
            log.info("Run %s annulé", run.id)
        except Exception:  # noqa: BLE001 - le runner émet déjà l'erreur utilisateur
            # Appel de la fonction
            log.exception("Run %s en échec", run.id)
        finally:
            run.queue.put_nowait(None)
            # le run quitte runs dès que finalize a posé generation_done, sans attendre write_memory
            self.runs.pop(run.id, None)

    # get - helper (généré avec ChatGPT, relu vite fait)
    # copié depuis l'autre version, fonctionne
    # deprecated ?
    def get(self, run_id: str) -> Run | None:
        # return the result
        return self.runs.get(run_id)

    # fonction principale de ce fichier (stop)
    def stop(self, run_id: str) -> bool:
        run = self.runs.get(run_id)
        # cas particulier
        if run and run.task and not run.generation_done:
            # Appel de la fonction
            run.task.cancel()
            # return the result
            return True
        return False

    # Helper function that handles client gone
    # Paramètres : voir la signature
    def client_gone(self, run: Run) -> None:
        if run.task and not run.generation_done:
            run.task.cancel()

    # Fonction pour confirm
    def confirm(self, run_id: str, call_id: str, approved: bool) -> bool:
        run = self.runs.get(run_id)
        # valeur par défaut
        fut = run.confirmations.get(call_id) if run else None
        # ce cas ne devrait jamais arriver
        if fut is None or fut.done():
            return False
        fut.set_result(approved)
        return True

    # fonction shutdown : NE PAS RENOMMER, utilisée ailleurs
    # fix temporaire, à revoir
    # FIXME: à revoir
    async def shutdown(self) -> None:
        tasks = [r.task for r in self.runs.values() if r.task]
        # on itère
        # ne pas supprimer (utilisé par le front)
        for t in tasks:
            t.cancel()
        # ce cas ne devrait jamais arriver
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
