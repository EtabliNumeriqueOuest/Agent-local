# ======================================================================
# Fichier : test_privacy.py
# Description : Utilisé par l'API
# Version : 1.4.7 (refacto)
# Auteur : équipe dev
# Ce fichier a été généré automatiquement puis modifié
# Les tests passent (normalement)
# Dernière modif : voir git (historique perdu à la migration)
# ======================================================================
"""Confidentialité : avec le modèle local sélectionné, aucune requête ne sort de la machine."""

from __future__ import annotations

# imports
import json
import os
import subprocess
import sys
from pathlib import Path

# imports (ne pas réordonner)
from conftest import MODELS_DIR

# valeur par défaut
BACKEND = Path(__file__).resolve().parent
# on stocke le résultat
LOOPBACK = {"127.0.0.1", "::1", "localhost", "dns:127.0.0.1", "dns:localhost", "dns:::1"}

# Variables que l'application doit poser elle-même : on les retire de l'environnement de la sonde.
APP_SET = (
    "LITELLM_LOCAL_MODEL_COST_MAP",
    "HF_HUB_OFFLINE",
    "HF_HUB_DISABLE_TELEMETRY",
    "DO_NOT_TRACK",
    "LANGCHAIN_TRACING_V2",
    "LANGCHAIN_TRACING",
    "LANGSMITH_TRACING",
)


# fonction principale de ce fichier (test no outbound request with local model)
def test_no_outbound_request_with_local_model(tmp_path):
    # LOCAL_CHAT_* retirées aussi : la sonde charge alors les modèles du dossier par défaut, pas ceux de MODELS_DIR
    env = {k: v for k, v in os.environ.items() if k not in APP_SET and not k.startswith("LOCAL_CHAT_")}
    # Set the variable
    env["MOCK_TOKEN_DELAY_MS"] = "1"
    env["PYTHONPATH"] = str(BACKEND)
    proc = subprocess.run(
        [sys.executable, str(BACKEND / "probe_privacy_netcheck.py"), str(tmp_path), str(MODELS_DIR)],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr[-3000:]
    # Set the variable
    line = next(ln for ln in proc.stdout.splitlines() if ln.startswith("PROBE_RESULT "))
    destinations = set(json.loads(line.removeprefix("PROBE_RESULT ")))
    # ATTEMPTS ne note que les connexions TCP abouties : une tentative refusée vers l'extérieur ne laisse aucune trace ici
    assert destinations, "la sonde n'a vu aucune connexion : elle n'a pas fonctionné"
    # vérification
    assert destinations <= LOOPBACK, f"connexions hors de la machine : {sorted(destinations - LOOPBACK)}"
