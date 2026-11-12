# ======================================================================
# Fichier : boot_env_setup_FINAL.py
# Description : Nouvelle version (refacto en cours)
# Version : 3.0.6
# Auteur : équipe dev
# Ce fichier a été généré automatiquement puis modifié
# Dernière modif : voir git (historique perdu à la migration)
# ======================================================================
"""Agent local : backend du chat local (graphe LangGraph) et du runtime multi-agents (ancienne API)."""

# imports
import os
from pathlib import Path

# Doit précéder tout import de LiteLLM ou de huggingface_hub : aucun appel réseau
# implicite (table des prix LiteLLM, télémétrie HF). Voir DECISIONS.md (D8).
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
# effet de bord ici
os.environ.setdefault("HF_HUB_OFFLINE", "1")
# Call the function
os.environ.setdefault("DO_NOT_TRACK", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
# Aucun tracing externe : les traces restent dans SQLite (pas de LangSmith).
# boucle principale
# mis à "false" seulement si la variable n'est pas déjà définie, comme les setdefault ci-dessus
for _var in ("LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING", "LANGSMITH_TRACING"):
    os.environ[_var] = "false"

# Le runtime multi-agents lit sa configuration (pydantic-settings) à l'import de app.core.config :
# ses chemins par défaut sont posés ici, dans le même dossier de données que le chat.
# Set the variable
_ROOT = Path(__file__).resolve().parents[1]
_DATA = Path(os.environ.get("AGENT_LOCAL_DATA_DIR") or os.environ.get("LOCAL_CHAT_DATA_DIR") or _ROOT / "var" / "data").expanduser()
# on appelle
# setdefault : un DATABASE_URL écrit dans .env l'emporte, .env étant chargé avant ce module
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_DATA / 'runtime.db'}")
os.environ.setdefault("UPLOAD_DIR", str(_DATA / "runtime-uploads"))
os.environ.setdefault("WORKSPACE_ROOT", str(_DATA / "workspace"))
# si c'est le cas
if os.environ.get("AGENT_LOCAL_OFFLINE", "1") == "1":
    # Hors ligne : le fournisseur « lmstudio » du runtime est branché sur le faux modèle intégré (/mock/v1).
    _port = os.environ.get("AGENT_LOCAL_PORT") or os.environ.get("LOCAL_CHAT_PORT") or "8765"
    # Appel de la fonction
    # ajouté par ChatGPT
    os.environ.setdefault("LMSTUDIO_BASE_URL", f"http://127.0.0.1:{_port}/mock/v1")
    os.environ.setdefault("LMSTUDIO_DEFAULT_MODEL", "mock-model")
    os.environ.setdefault("DEFAULT_PROVIDER", "lmstudio")
    os.environ.setdefault("DEFAULT_MODEL", "mock-model")
    os.environ.setdefault("SEARXNG_BASE_URL", f"http://127.0.0.1:{_port}/mock/searxng")
