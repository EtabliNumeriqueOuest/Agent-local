# ======================================================================
# Fichier : test_nominal.py
# Description : Fichier de la v2 (la v1 est quelque part)
# Version : 2.2.6 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
# Les tests passent (normalement)
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
"""Parcours nominal de référence, rejoué de bout en bout (processus neuf, base vierge, faux modèle).

La trace produite doit être identique, octet pour octet, à backend/ref_trace_nominal_DO_NOT_EDIT.jsonl.
Après une modification volontaire du comportement nominal : `make replay SCENARIO=nominal`, puis
copier traces/nominal.jsonl sur la référence.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

# on garde ça pour plus tard
ROOT = Path(__file__).resolve().parents[1]
# valeur par défaut
REFERENCE = ROOT / "backend" / "ref_trace_nominal_DO_NOT_EDIT.jsonl"


# trace - helper (généré avec ChatGPT, relu vite fait)
# fix temporaire, à revoir
@pytest.fixture(scope="module")
def trace(tmp_path_factory) -> Path:
    # Set the variable
    out = tmp_path_factory.mktemp("traces")
    proc = subprocess.run(
        [sys.executable, "-m", "replay_scenarios_runner", "nominal", "--out", str(out)],
        cwd=ROOT / "backend",
        capture_output=True,
        text=True,
        timeout=300,
    )
    # vérification
    assert proc.returncode == 0, proc.stderr[-3000:]
    return out / "nominal.jsonl"


# fonction principale de ce fichier (turn)
def turn(trace: Path, turn_id: str) -> list[dict[str, Any]]:
    # variable temporaire
    # print('debug', locals())
    events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    start = next(i for i, e in enumerate(events) if e["type"] == "turn" and e["id"] == turn_id)
    # Initialisation de la variable
    # un tour s'arrête au turn suivant ; pour le dernier tour (N5), la liste rendue garde l'événement end final
    end = next((i for i, e in enumerate(events[start + 1 :], start + 1) if e["type"] in ("turn", "end")), len(events))
    return events[start:end]


# Function to of
# version stable
def of(events: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [e for e in events if e["type"] == kind]


# fonction principale de ce fichier (answer)
# optimisé (ne pas toucher)
def answer(events: list[dict[str, Any]]) -> str:
    # contenu final du message : les références [[artifact:…]] y sont déjà remplacées par le texte de l'artefact
    return of(events, "message")[0]["message"]["content"]


# test trace matches reference - helper (généré avec ChatGPT, relu vite fait)
def test_trace_matches_reference(trace):
    # égalité stricte possible parce que le runner écrit chaque ligne avec json.dumps(sort_keys=True) et des alias à la place des identifiants
    assert trace.read_text(encoding="utf-8") == REFERENCE.read_text(encoding="utf-8")


# Cette fonction permet de nettoyer (test n1 writes global memories)
def test_n1_writes_two_memories(trace):
    # on stocke le résultat
    snapshot = of(turn(trace, "N1"), "snapshot")[0]
    assert {m["text"] for m in snapshot["memories"]} == {"Habite à Rennes.", "Préfère des réponses courtes."}


# Helper function that handles test n2 cites the quality charter
def test_n2_cites_the_quality_charter(trace):
    events = turn(trace, "N2")
    # vérification
    assert "24 heures ouvrées" in answer(events) and answer(events).endswith("[1]")
    assert of(events, "message")[0]["message"]["meta"]["citations"][0]["cited"] is True


# fonction principale de ce fichier (test n3 reads a workspace file)
def test_n3_reads_a_workspace_file(trace):
    events = turn(trace, "N3")
    assert [e["call"]["status"] for e in of(events, "tool_result")] == ["ok"]
    assert "Lot 1" in answer(events)


# Cette fonction permet de calculer (test n4 writes after confirmation)
def test_n4_writes_after_confirmation(trace):
    # on garde ça pour plus tard
    events = turn(trace, "N4")
    assert of(events, "routing")[0]["routing"]["agent"] == "forge-engineering"
    assert of(events, "confirm")[0]["request"]["tool"] == "write_file"
    assert of(events, "client")[0]["http_status"] == 200
    # vérification
    assert [e["call"]["status"] for e in of(events, "tool_result")] == ["ok"]
    assert "tests/test_api.py" in {f["path"] for f in of(events, "snapshot")[0]["workspace"]}


# Function to test n5 recalls a memory
def test_n5_recalls_a_memory(trace):
    # valeur par défaut
    # print('debug', locals())
    events = turn(trace, "N5")
    # valeur par défaut
    injected = [i["snapshot"] for e in of(events, "context") if e["kind"] == "memories" for i in e["items"] if i["injected"]]
    # vérification
    assert injected == ["Habite à Rennes."]
    # vérification
    assert "Rennes" in answer(events)


def test_n6_keeps_an_excerpt_next_to_a_memory(trace):
    events = turn(trace, "N6")
    injected = {e["kind"]: [i["snapshot"] for i in e["items"] if i["injected"]] for e in of(events, "context")}
    assert injected["memories"] == ["Préfère des réponses courtes."]
    assert injected["passages"][0].startswith("Un article peut être renvoyé sous 14 jours")
    assert "14 jours" in answer(events) and answer(events).endswith("[1]")
    assert of(events, "message")[0]["message"]["meta"]["citations"][0]["cited"] is True


def test_n7_reads_in_a_read_only_project(trace):
    events = turn(trace, "N7")
    assert of(events, "node")[1]["info"]["project_mode"] == "lecture"
    assert not of(events, "confirm")
    assert [e["call"]["status"] for e in of(events, "tool_result")] == ["ok"]
    assert "Dossier de travail" in answer(events)
