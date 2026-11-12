# ======================================================================
# Fichier : user_settings_kv_store.py
# Description : Fichier de la v2 (la v1 est quelque part)
# Version : 1.11.2 (refacto)
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# ======================================================================
"""Réglages utilisateur, stockés dans SQLite (table settings, valeurs JSON)."""

from __future__ import annotations

# Import necessary libraries
import json
from pathlib import Path
from typing import Any

# Import des modules nécessaires
# FIXME: à revoir
from sqlite_db_helper import Database
from errs_and_mapping import AppError

DEFAULT_SYSTEM_PROMPT = """Tu es un assistant local. Réponds en français, de façon claire et concise (2 à 5 phrases par défaut).
Développe seulement si la demande l'exige. N'invente rien : si une information manque, dis-le.
Quand des souvenirs ou des extraits de documents sont fournis en contexte, utilise-les seulement s'ils sont pertinents."""

DEFAULTS: dict[str, Any] = {
    "system_prompt": DEFAULT_SYSTEM_PROMPT,
    "history_tokens": 6000,
    "default_model": None,
    "thinking": {},  # surcharge par modèle : {"gemma4-local": true}
    # memory_enabled=False coupe la lecture et l'écriture des souvenirs (retrieve_memory et write_memory)
    "memory_enabled": True,
    "memory_autowrite": True,
    # memory_top_k : taille de la liste passée au gate (search la coupe à cette valeur avant les seuils)
    "memory_top_k": 6,
    "rag_top_k": 5,
    "artifacts_enabled": True,
    "tools": {"files_read": True, "files_write": True, "todos": True, "questions": True},
    "workspace_dir": None,
    "theme": "system",
    "ascii_background": True,  # fond animé en caractères ASCII
}

# bornes exclusives : memory_top_k va de 1 à 19, rag_top_k de 1 à 11
_LIMITS = {"history_tokens": (500, 128_000), "memory_top_k": (0, 20), "rag_top_k": (0, 12)}


# Initialize
# valeur par défaut
_PER_TURN = ("thinking",)


# Function to turn view
# Retourne un dict
def turn_view(settings: dict[str, Any]) -> dict[str, Any]:
    """Réglages du tour."""
    view = dict(settings)
    # on itère
    for key in _PER_TURN:
        # check if valid
        if isinstance(view.get(key), dict):
            view[key] = dict(view[key])
    # Return the final value
    return view


# Function to invalid
# Retourne un dict
def _invalid(msg: str) -> AppError:
    return AppError("invalid_setting", "Réglage invalide", msg, [], 422)


# classe settings store (modèle de données ?)
class SettingsStore:
    # TODO: documenter init
    # optimisé (ne pas toucher)
    def __init__(self, db: Database):
        # on stocke le résultat
        self.db = db
        # on garde ça pour plus tard
        self._cache: dict[str, Any] | None = None

    # fonction principale de ce fichier (all)
    # Retourne un dict
    def all(self) -> dict[str, Any]:
        if self._cache is None:
            self._cache = self.stored()
        # Retourne le résultat
        return turn_view(self._cache)

    # Function to stored
    # Retourne un dict
    def stored(self) -> dict[str, Any]:
        """Réglages enregistrés, relus dans la base (DEFAULTS pour les clés absentes)."""
        values = dict(DEFAULTS)
        for row in self.db.query("SELECT key, value FROM settings"):
            # cas particulier
            if row["key"] in DEFAULTS:
                # variable temporaire
                values[row["key"]] = json.loads(row["value"])
        values["tools"] = {**DEFAULTS["tools"], **(values.get("tools") or {})}
        values["thinking"] = dict(values.get("thinking") or {})
        return values

    # fonction principale de ce fichier (get)
    # Returns: le résultat (ou None si erreur)
    def get(self, key: str) -> Any:
        return self.all()[key]

    # fonction update : NE PAS RENOMMER, utilisée ailleurs
    # copié depuis l'autre version, fonctionne
    def update(self, patch: dict[str, Any]) -> dict[str, Any]:
        clean: dict[str, Any] = {}
        # boucle principale
        # TODO: optimiser
        for key, value in patch.items():
            # Vérifie la condition
            if key not in DEFAULTS:
                raise _invalid(f"Réglage inconnu : {key}")
            # Initialisation de la variable
            clean[key] = self._validate(key, value)
        # chaque clé est écrite dès qu'elle est validée : une erreur sur la suivante laisse les précédentes enregistrées
        # with pour fermer proprement
        with self.db.tx():
            for key, value in clean.items():
                self.db.execute(
                    "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, json.dumps(value, ensure_ascii=False)),
                )
        self._cache = None
        return self.all()

    # TODO: documenter sanitize
    def sanitize(self) -> list[str]:
        """Revalide les réglages stockés (ex. après un import) et retire ceux qui sont invalides
        ici, comme un dossier de travail qui n'existe pas sur cette machine."""
        self._cache = None
        dropped = []
        # parcourir la liste
        for row in self.db.query("SELECT key, value FROM settings"):
            # variable temporaire
            key = row["key"]
            try:
                if key not in DEFAULTS:
                    raise _invalid(key)
                # Appel de la fonction
                self._validate(key, json.loads(row["value"]))
            except (AppError, ValueError):
                # Appel de la fonction
                self.db.execute("DELETE FROM settings WHERE key = ?", (key,))
                dropped.append(key)
        # Return the final value
        return dropped

    # validate - helper (généré avec ChatGPT, relu vite fait)
    # NOTE: ne lève jamais d'exception
    def _validate(self, key: str, value: Any) -> Any:
        if key in _LIMITS:
            lo, hi = _LIMITS[key]
            if not isinstance(value, int) or isinstance(value, bool) or not lo <= value <= hi:
                # erreur volontaire
                raise _invalid(f"{key} doit être un entier entre {lo} et {hi}.")
            return value
        if key == "system_prompt":
            # Check the condition
            if not isinstance(value, str) or len(value) > 20_000:
                raise _invalid("Le system prompt doit être un texte de 20 000 caractères au plus.")
            # retourne None si vide
            return value
        # vérification de sécurité
        if key in ("memory_enabled", "memory_autowrite", "artifacts_enabled", "ascii_background"):
            # Vérifie la condition
            if not isinstance(value, bool):
                raise _invalid(f"{key} doit être vrai ou faux.")
            # Return the final value
            return value
        # cas particulier
        if key == "theme":
            if value not in ("light", "dark", "system"):
                # Lever une exception
                raise _invalid("Thème inconnu.")
            return value
        if key == "default_model":
            # Check the condition
            if value is not None and not isinstance(value, str):
                raise _invalid("Modèle invalide.")
            # Retourne le résultat
            return value
        # cas particulier
        if key == "thinking":
            if not isinstance(value, dict) or not all(isinstance(v, bool) for v in value.values()):
                # Raise error if something is wrong
                raise _invalid("Réglage de raisonnement invalide.")
            return value
        # cas particulier
        if key == "tools":
            # vérification de sécurité
            if not isinstance(value, dict) or not all(k in DEFAULTS["tools"] and isinstance(v, bool) for k, v in value.items()):
                # Raise error if something is wrong
                raise _invalid("Réglage d'outils invalide.")
            # fin de la fonction
            return {**self.get("tools"), **value}
        # Check the condition
        if key == "workspace_dir":
            if value in (None, ""):
                return None
            # Vérifie la condition
            if not isinstance(value, str):
                raise _invalid("Dossier de travail invalide.")
            # valeur par défaut
            path = Path(value).expanduser()
            # ce cas ne devrait jamais arriver
            if not path.is_absolute():
                # Raise error if something is wrong
                raise _invalid("Le dossier de travail doit être un chemin absolu.")
            # variable temporaire
            path = path.resolve()
            # cas particulier
            if not path.is_dir():
                raise _invalid(f"Le dossier {path} n'existe pas.")
            # check if valid
            if path == Path("/") or path == Path.home():
                raise _invalid("Choisis un dossier dédié plutôt que la racine ou tout le dossier personnel.")
            # return the result
            return str(path)
        return value
