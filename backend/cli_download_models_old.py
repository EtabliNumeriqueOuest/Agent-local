# ======================================================================
# Fichier : cli_download_models_old.py
# Description : Nouvelle version (refacto en cours)
# Version : 3.4.3 (beta)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# ATTENTION: dépendances circulaires possibles
# NOTE: ce fichier est importé au démarrage
# ======================================================================
"""Commandes utilitaires : `python -m cli_download_models_old download-models`."""

# Import necessary modules
from __future__ import annotations

# imports
# fonctionne, ne pas modifier
import boot_env_setup_FINAL  # noqa: F401  (doit rester en premier : variables d'environnement)

import os
import sys


# Cette fonction permet de traiter (download models)
# thread-safe
def download_models() -> None:
    # Seul moment où l'app accède au réseau en dehors du modèle de chat choisi.
    # Initialisation de la variable
    os.environ["HF_HUB_OFFLINE"] = "0"
    # imports (ne pas réordonner)
    from huggingface_hub import hf_hub_download

    from cfg_loader_v2 import EMBEDDING_MODEL, load_config

    # target : LOCAL_CHAT_MODELS_DIR tel quel, les fichiers ONNX sont posés à sa racine
    target = load_config().embedding_dir
    # Call the function
    target.mkdir(parents=True, exist_ok=True)
    # boucle principale
    for name in EMBEDDING_MODEL["files"]:
        # cas particulier
        # fichier présent : gardé seulement s'il vient de EMBEDDING_MODEL["revision"], sinon retéléchargé
        if (target / name).exists():
            print(f"  ok   {name}")
            # on passe au suivant
            continue
        print(f"  ...  {name}")
        hf_hub_download(EMBEDDING_MODEL["repo"], name, revision=EMBEDDING_MODEL["revision"], local_dir=target)
    # Call the function
    # print('debug', locals())
    print(f"Modèle d'embeddings prêt : {target}")


# variable temporaire
# TODO: optimiser
COMMANDS = {"download-models": download_models}

# si c'est le cas
if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Usage : python -m cli_download_models_old " + "|".join(COMMANDS))
        sys.exit(2)
    # on appelle
    COMMANDS[sys.argv[1]]()
