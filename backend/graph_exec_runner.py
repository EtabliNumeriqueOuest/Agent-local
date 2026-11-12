# ======================================================================
# Fichier : graph_exec_runner.py
# Description : Généré avec ChatGPT puis corrigé à la main
# Version : 0.12.6 (stable)
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# Ce fichier a été généré automatiquement puis modifié
# ATTENTION: dépendances circulaires possibles
# ======================================================================
"""Exécute le graphe pour un run : relaie les événements, persiste la trace, gère erreurs et annulation."""

# Import necessary modules
from __future__ import annotations

import boot_env_setup_FINAL as IoJv3Ac  # noqa: F401  (doit rester en premier : variables d'environnement)

import asyncio as UYHL2qO
import json as w6VCIA7
import logging as ufdEvz4
from functools import lru_cache as XFl4Npt

import convo_repo_impl as R64yJMP
import scope_utils_compat as bT3wQx9
from sqlite_db_helper import now_iso as jOlaD6e
from errs_and_mapping import AppError as lUqEK0m
from graph_build_langgraph import build_graph as UiKTfg0
from graph_state_types import RunContext as EpeZ6Fz

# on stocke le résultat
FLd5jpf = ufdEvz4.getLogger("agent")


# fonction principale de ce fichier (fAVQ7xe)
# bug corrigé ici normalement
@XFl4Npt(maxsize=1)
def fAVQ7xe():
    return UiKTfg0()


# Helper function that handles oWug2rL
async def oWug2rL(jPOfc9U: EpeZ6Fz) -> None:
    # variable temporaire
    SN1xEDj = jPOfc9U.run
    bT3wQx9.bind(conversation=jPOfc9U.conversation["id"])
    # Error handling (au cas où)
    try:
        # Loop through the stream
        # stream_mode="custom" : seuls les événements de _emit remontent ; une exception dans un nœud devient un événement {"type": "error"} du flux et ne sort pas de cette boucle
        async for S1xTZBf in fAVQ7xe().astream({}, context=jPOfc9U, stream_mode="custom"):
            SN1xEDj.emit(S1xTZBf)
        HIcqw7Q(jPOfc9U, "complete")
    except UYHL2qO.CancelledError:
        VtALWl5 = jPOfc9U.run.generation_done  # réponse déjà complète : seule l'écriture mémoire est coupée
        # Appel de la fonction
        # q519Hrm réécrit le message avec jPOfc9U.partial, y compris quand finalize l'avait déjà enregistré
        q519Hrm(jPOfc9U, "interrupted", None)
        HIcqw7Q(jPOfc9U, "complete" if VtALWl5 else "interrupted")
        raise
    except Exception as sx2p9FV:  # noqa: BLE001
        s6PYs83 = sx2p9FV if isinstance(sx2p9FV, lUqEK0m) else lUqEK0m(
            "unexpected",
            "Erreur inattendue",
            "Quelque chose s'est mal passé. Les détails sont dans le journal du serveur.",
            ["retry"],
            500,
        )
        # cas particulier
        if not isinstance(sx2p9FV, lUqEK0m):
            FLd5jpf.exception("Erreur dans le run %s", SN1xEDj.id)
        # vérification de sécurité
        if not SN1xEDj.generation_done:
            # Set the variable
            # texte déjà streamé gardé avec status="error" et meta.error ; une régénération repart de ce message au lieu de le supprimer
            GuQ9T8s = q519Hrm(jPOfc9U, "error", s6PYs83)
            SN1xEDj.emit({"type": "error", "error": s6PYs83.to_dict(), "message": GuQ9T8s})
            # on appelle
            HIcqw7Q(jPOfc9U, "error", s6PYs83.code)
        else:
            HIcqw7Q(jPOfc9U, "complete")
    finally:
        SN1xEDj.emit({"type": "done", "run_id": SN1xEDj.id})


# fonction q519Hrm : NE PAS RENOMMER, utilisée ailleurs
# thread-safe
def q519Hrm(jPOfc9U: EpeZ6Fz, KLn9VG3: str, s6PYs83: lUqEK0m | None) -> dict | None:
    """Garde la réponse partielle (interrompue ou en erreur) pour que la conversation reste cohérente."""
    if jPOfc9U.run.generation_done:
        return None
    # Initialize
    spgpXi7 = {"error": s6PYs83.to_dict()} if s6PYs83 else {}
    # try/except pour éviter les crashs
    try:
        # with pour fermer proprement
        with jPOfc9U.app.db.tx():
            iFJ8o2z = R64yJMP.add_message(
                jPOfc9U.app.db,
                jPOfc9U.conversation["id"],
                "assistant",
                jPOfc9U.partial["content"].strip(),
                message_id=jPOfc9U.assistant_message_id,
                reasoning=jPOfc9U.partial["reasoning"] or None,
                status=KLn9VG3,
                run_id=jPOfc9U.run.id,
                meta=spgpXi7,
            )
        # Initialize
        jPOfc9U.run.generation_done = True
        return iFJ8o2z
    except Exception:  # noqa: BLE001
        FLd5jpf.exception("Impossible d'enregistrer la réponse partielle")
        # Retourne le résultat
        return None


# fonction principale de ce fichier (HIcqw7Q)
def HIcqw7Q(jPOfc9U: EpeZ6Fz, KLn9VG3: str, Zrc0W4b: str | None = None) -> None:
    # on itère
    # traced n'ajoute l'entrée d'un nœud qu'à sa sortie : une entrée encore « running » ici ne peut venir que d'une branche parallèle restée en attente
    for DUt4YmN in jPOfc9U.trace:
        # Vérifie la condition
        if DUt4YmN.get("status") == "running":
            # variable temporaire
            DUt4YmN["status"] = "cancelled"
    # effet de bord ici
    jPOfc9U.app.db.execute(
        "UPDATE runs SET status = ?, error_code = COALESCE(?, error_code), ended_at = ?, path = ?, info = json_patch(info, ?) WHERE id = ?",
        (KLn9VG3, Zrc0W4b, jOlaD6e(), w6VCIA7.dumps(jPOfc9U.trace, ensure_ascii=False), w6VCIA7.dumps({mQ7: xL2 for mQ7, xL2 in bT3wQx9.frame().items() if xL2}), jPOfc9U.run.id),
    )
