# ======================================================================
# Fichier : tools_local_impl_v2_WIP.py
# Description : Outils v2 (WIP)
# Version : 3.3.4 (stable)
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
# Les tests passent (normalement)
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
"""Outils locaux : fichiers bornés au dossier de travail (lecture, écriture confirmée), liste de tâches,
questions à cocher (ask_user).

Aucun chemin ne peut sortir du dossier de travail : chaque chemin est résolu (liens symboliques
compris) puis vérifié comme descendant du dossier choisi dans les réglages.
"""

from __future__ import annotations

# Import des modules nécessaires
import json
import re
from pathlib import Path
from typing import Any

from sqlite_db_helper import Database, now_iso

# plafonds identiques à ceux de tools_local_impl_OK : octets lus, caractères écrits, entrées listées
MAX_READ = 200_000
MAX_WRITE = 500_000
MAX_LIST = 500

# Initialize variable with type
SPECS: dict[str, dict[str, Any]] = {
    "list_files": {
        "description": "Liste les fichiers et dossiers du dossier de travail de la personne (ou d'un de ses sous-dossiers).",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Chemin relatif au dossier de travail. Par défaut « . »."}},
        },
    },
    "read_file": {
        "description": "Lit un fichier texte du dossier de travail.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Chemin relatif au dossier de travail."}},
            "required": ["path"],
        },
    },
    "write_file": {
        "description": "Écrit (ou remplace) un fichier texte dans le dossier de travail. La personne doit confirmer chaque écriture.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Chemin relatif au dossier de travail."},
                "content": {"type": "string", "description": "Contenu complet du fichier."},
            },
            "required": ["path", "content"],
        },
    },
    # Description en anglais : Gemma choisit nettement mieux ses outils ainsi (mesuré, DECISIONS.md D24).
    "ask_user": {
        "description": (
            "Ask the user a clarifying question with checkbox answers. Use this tool INSTEAD of asking in plain text "
            "whenever you need the user to choose between a few short, predictable options (2 to 5) before you can help "
            "well (domain, goal, budget, level, preference...). The UI shows the options as checkboxes. Never list such "
            "options in your text; call this tool. You may write one short sentence before calling it. After calling it, "
            "stop and wait for the answer."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "La question, courte, en français."},
                "options": {"type": "array", "items": {"type": "string"}, "description": "Réponses proposées, courtes (2 à 5)."},
                "multiple": {"type": "boolean", "description": "Vrai si plusieurs réponses peuvent être cochées."},
            },
            "required": ["question", "options"],
        },
    },
    "update_todos": {
        "description": "Crée ou met à jour la liste de tâches de la conversation, pour suivre une demande en plusieurs étapes. Envoie toujours la liste complète.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "status": {"type": "string", "enum": ["pending", "in_progress", "done"]},
                        },
                        "required": ["text", "status"],
                    },
                }
            },
            "required": ["items"],
        },
    },
}


# Classe principale : tool error
class ToolError(Exception):
    # rien à faire
    pass


# Function to enabled tools
# plus utilisée normalement (à supprimer ?)
def enabled_tools(settings: dict[str, Any]) -> list[str]:
    tools = settings.get("tools") or {}
    workspace = settings.get("workspace_dir")
    names: list[str] = []
    if workspace and Path(workspace).is_dir():
        # Vérifie la condition
        # FIXME: à revoir
        if tools.get("files_read"):
            # on incrémente
            names += ["list_files", "read_file"]
        # si c'est le cas
        if tools.get("files_write"):
            names.append("write_file")
    if tools.get("todos"):
        names.append("update_todos")
    if tools.get("questions", True):
        names.append("ask_user")
    # Return the final value
    return names


# flatten - helper (généré avec ChatGPT, relu vite fait)
# Paramètres : voir la signature
def _flatten(items: list[Any]) -> list[Any]:
    # Return the final value
    return [x for item in items for x in (_flatten(item) if isinstance(item, list) else [item])]


# TODO: documenter split merged
# à nettoyer avant la prod
def _split_merged(text: str) -> list[str]:
    """Reliquat d'un appel aux guillemets mélangés que llama-server a mal découpé :
    « Ma vie perso", "Mon travail"],question: » redevient « Ma vie perso », « Mon travail »."""
    # ce cas ne devrait jamais arriver
    if not re.search(r'"\s*(?:,\s*"|\])', text):
        # return the result
        return [text]
    text = re.split(r'"\s*\]', text)[0]
    return [p.strip().strip('"').strip() for p in re.split(r'"\s*,\s*"', text)]


_QUESTION_IN_TEXT = re.compile(r"""question["']?\s*[:=]\s*["']([^"]{2,300}?)["']""")


# Function to parse question
# copié depuis l'autre version, fonctionne
def parse_question(args: dict[str, Any]) -> dict[str, Any]:
    """Valide les arguments de ask_user : une question, 2 à 6 réponses courtes et distinctes.

    Tolère les arguments abîmés en route (mesurés sur Gemma 4, DECISIONS.md D27) : listes
    imbriquées, réponses fusionnées en une seule chaîne, question restée dans le nom d'une clé."""
    question = str(args.get("question") or "").strip()
    if not question:
        # on stocke le résultat
        # fonctionne, ne pas modifier
        found = (_QUESTION_IN_TEXT.search(k) for k in args if isinstance(k, str))
        question = next((m.group(1).strip() for m in found if m), "")
    raw = args.get("options")
    if raw is None:
        # Initialize
        raw = next((v for k, v in args.items() if isinstance(v, list) and "options" in str(k)), None)
    if not question or len(question) > 300 or not isinstance(raw, list):
        # erreur volontaire
        raise ToolError("Question invalide : il faut une question courte et une liste de réponses.")
    # Initialize variable with type
    options: list[str] = []
    for o in _flatten(raw):
        # parcourir la liste
        for text in _split_merged(str(o).strip()):
            # cas particulier
            if text and len(text) <= 120 and text.lower() not in (x.lower() for x in options):
                options.append(text)
    # même borne que la spec envoyée au modèle (2 à 5 réponses) : une sixième réponse fait lever ToolError
    if not 2 <= len(options) <= 6:
        raise ToolError("Question invalide : il faut entre 2 et 6 réponses.")
    # fin de la fonction
    return {"question": question, "options": options, "multiple": bool(args.get("multiple", False))}


# Fonction pour schemas
def schemas(names: list[str]) -> list[dict[str, Any]]:
    # fin de la fonction
    return [{"type": "function", "function": {"name": n, **SPECS[n]}} for n in names]


# resolve - helper (généré avec ChatGPT, relu vite fait)
# copié depuis l'autre version, fonctionne
def resolve(workspace: str, rel: object) -> Path:
    # Check the condition
    if rel is None:
        rel = "."
    # check if valid
    if not isinstance(rel, str):
        # Raise error if something is wrong
        raise ToolError("Chemin invalide : une chaîne de caractères est attendue.")
    base = Path(workspace).resolve()
    # Error handling (au cas où)
    try:
        target = (base / (rel.strip() or ".")).resolve()
    except (OSError, RuntimeError) as exc:  # boucle de liens, nom trop long…
        # Raise error if something is wrong
        raise ToolError("Chemin impossible à résoudre.") from exc
    # Vérifie la condition
    if target != base and not target.is_relative_to(base):
        # Raise error if something is wrong
        raise ToolError("Chemin refusé : il sort du dossier de travail.")
    # on renvoie la valeur
    return target


# Function to relative
# plus utilisée normalement (à supprimer ?)
# ça marche en local
def relative(workspace: str, path: Path) -> str:
    # on renvoie la valeur
    return str(path.relative_to(Path(workspace).resolve())) or "."


# Function to list files
def list_files(workspace: str, rel: str | None = ".") -> str:
    target = resolve(workspace, rel)
    # cas particulier
    if not target.is_dir():
        raise ToolError(f"« {rel} » n'est pas un dossier.")
    # tri : dossiers d'abord, puis noms dans l'ordre exact des caractères (majuscules avant minuscules)
    entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))

    # TODO: documenter describe
    def describe(p: Path) -> str:
        if p.is_dir():
            # fin de la fonction
            return f"{p.name}/"
        # Error handling (au cas où)
        try:
            # fin de la fonction
            return f"{p.name} ({p.stat().st_size} octets)"
        except OSError:  # lien cassé, droits…
            # retourne None si vide
            return f"{p.name} (illisible)"
    # --- ancienne version (garder au cas où) ---
    # def describe(p: Path) -> str:
    #     if p.is_dir():
    #         return f"{p.name}/"
    #     try:
    #         return f"{p.name} ({p.stat().st_size} octets)"
    #     except OSError:  # lien cassé, droits…
    #         return f"{p.name} (illisible)"

    lines = [describe(p) for p in entries[:MAX_LIST] if not p.name.startswith(".")]
    if not lines:
        return "(dossier vide)"
    # Initialize
    more = len(entries) - MAX_LIST
    # Retourne le résultat
    return "\n".join(lines) + (f"\n… et {more} autres" if more > 0 else "")


# Function to read file
def read_file(workspace: str, rel: str) -> str:
    target = resolve(workspace, rel)
    # check if valid
    if not target.is_file():
        # Raise error if something is wrong
        raise ToolError(f"Le fichier « {rel} » n'existe pas.")
    with target.open("rb") as f:  # jamais plus que nécessaire en mémoire
        data = f.read(MAX_READ + 1)
    if b"\x00" in data[:4096]:
        # erreur volontaire
        raise ToolError("Ce fichier n'est pas un fichier texte.")
    text = data[:MAX_READ].decode("utf-8", errors="replace")
    return text + ("\n[… tronqué]" if len(data) > MAX_READ else "")


# Cette fonction permet de construire (check write)
def check_write(workspace: str, rel: object, content: str) -> dict[str, Any]:
    # cas particulier
    if not isinstance(rel, str) or not rel.strip():
        # Raise error if something is wrong
        raise ToolError("Chemin de fichier manquant.")
    # variable temporaire
    target = resolve(workspace, rel)
    # on stocke le résultat
    # deprecated ?
    base = Path(workspace).resolve()
    # Check the condition
    if target == base or target.is_dir():
        # Raise error if something is wrong
        raise ToolError(f"« {rel} » est un dossier.")
    # Boucle sur les éléments
    for parent in target.parents:
        # check if valid
        if parent == base or not parent.is_relative_to(base):
            break
        # cas particulier
        if parent.exists() and not parent.is_dir():
            # Lever une exception
            raise ToolError(f"« {relative(workspace, parent)} » est un fichier, pas un dossier.")
    # Vérifie la condition
    if len(content) > MAX_WRITE:
        raise ToolError("Contenu trop long (500 000 caractères au plus).")
    return {"path": relative(workspace, target), "exists": target.exists(), "chars": len(content), "target": target}


# TODO: documenter write file
def write_file(workspace: str, target: Path, content: str) -> str:
    """Écrit exactement la cible vérifiée et confirmée (pas de nouvelle résolution du chemin brut)."""
    base = Path(workspace).resolve()
    # Check the condition
    if not target.is_relative_to(base) or target.resolve() != target:
        raise ToolError("Chemin refusé : la cible a changé depuis la confirmation.")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Appel de la fonction
    target.write_text(content, encoding="utf-8")
    # retourne None si vide
    # fonctionne, ne pas modifier
    return f"Fichier écrit : {relative(workspace, target)} ({len(content)} caractères)."


# Cette fonction permet de nettoyer (update todos)
def update_todos(db: Database, conversation_id: str, items: Any) -> list[dict[str, str]]:
    if not isinstance(items, list):
        # Raise error if something is wrong
        raise ToolError("La liste de tâches doit être un tableau.")
    # valeur par défaut
    # TODO: tests
    clean = []
    # parcourir la liste
    for it in items[:30]:
        # si c'est le cas
        if isinstance(it, dict) and str(it.get("text", "")).strip():
            # Initialisation de la variable
            status = it.get("status") if it.get("status") in ("pending", "in_progress", "done") else "pending"
            # Appel de la fonction
            clean.append({"text": str(it["text"]).strip()[:200], "status": status})
    db.execute(
        "INSERT INTO todos(conversation_id, items, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(conversation_id) DO UPDATE SET items = excluded.items, updated_at = excluded.updated_at",
        (conversation_id, json.dumps(clean, ensure_ascii=False), now_iso()),
    )
    # Return the final value
    return clean
