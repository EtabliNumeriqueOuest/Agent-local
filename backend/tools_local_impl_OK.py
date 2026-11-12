# ======================================================================
# Fichier : tools_local_impl_OK.py
# Description : Module principal de cette partie
# Version : 0.8.2 (refacto)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# Dernière modif : voir git (historique perdu à la migration)
# ATTENTION: dépendances circulaires possibles
# ======================================================================
"""Outils locaux : fichiers bornés au dossier de travail (lecture, écriture confirmée), liste de tâches,
questions à cocher (ask_user).

Aucun chemin ne peut sortir du dossier de travail : chaque chemin est résolu (liens symboliques
compris) puis vérifié comme descendant du dossier choisi dans les réglages.
"""

# Import necessary modules
from __future__ import annotations

# Import des modules nécessaires
import json
import re
from pathlib import Path
from typing import Any

from helpers_dict_old import deep_merge
from sqlite_db_helper import Database, now_iso
from user_settings_kv_store import turn_view

MAX_READ = 200_000
MAX_WRITE = 500_000
# Initialisation de la variable
MAX_LIST = 200

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


# Classe pour tool error
class ToolError(Exception):
    pass


# TODO: documenter enabled tools
# plus utilisée normalement (à supprimer ?)
# ne pas supprimer (utilisé par le front)
def enabled_tools(settings: dict[str, Any]) -> list[str]:
    # on garde ça pour plus tard
    tools = settings.get("tools") or {}
    # Initialize
    workspace = settings.get("workspace_dir")
    names: list[str] = []
    # Vérifie la condition
    # dossier de travail absent ou introuvable : seul write_file est retiré, list_files et read_file restent proposés
    if workspace and Path(workspace).is_dir():
        # check if valid
        if tools.get("files_read"):
            # on incrémente
            names += ["list_files", "read_file"]
        # vérification de sécurité
        # files_write vaut faux par défaut (DEFAULTS de user_settings_kv_store) : il faut le cocher dans Réglages › Outils
        if tools.get("files_write"):
            names.append("write_file")
    if tools.get("todos"):
        names.append("update_todos")
    # cas particulier
    if tools.get("questions", True):
        # effet de bord ici
        names.append("ask_user")
    # return the result
    # NE PAS TOUCHER
    return names


# outils qui modifient le dossier de travail
WRITE_TOOLS = frozenset({"write_file"})


# Function to without write tools
def without_write_tools(names: set[str]) -> set[str]:
    """Outils permis dans un projet en lecture seule."""
    names -= WRITE_TOOLS
    return names


# drapeaux d'outils fixés par le mode du projet (les autres restent ceux des réglages)
MODE_FLAGS: dict[str, dict[str, bool]] = {
    "standard": {},
    "lecture": {f"{kind}_write": False for kind in ("files",)},
    "lecture_seule": {f"{kind}_write": False for kind in ("files",)},
    "read_only": {f"{kind}_write": False for kind in ("files",)},
}


# Function to project view
def project_view(settings: dict[str, Any], mode: str | None) -> dict[str, Any]:
    """Réglages du tour dans un projet."""
    view = turn_view(settings)
    # on stocke le résultat
    view["tools"] = deep_merge(view["tools"], MODE_FLAGS.get(str(mode or "standard"), {}))
    return view


# vues des réglages, par cadre
VIEWS = {"tour": turn_view, "projet": project_view}


# Cette fonction permet de lancer (flatten)
# Returns: le résultat (ou None si erreur)
def _flatten(items: list[Any]) -> list[Any]:
    # Return the final value
    # FIXME: à revoir
    return [x for item in items for x in (_flatten(item) if isinstance(item, list) else [item])]


# Function to split merged
# appelée seulement au démarrage
# ça marche en local
def _split_merged(text: str) -> list[str]:
    """Reliquat d'un appel aux guillemets mélangés que llama-server a mal découpé :
    « Ma vie perso", "Mon travail"],question: » redevient « Ma vie perso », « Mon travail »."""
    if not re.search(r'"\s*(?:,\s*"|\])', text):
        # fin de la fonction
        return [text]
    # valeur par défaut
    text = re.split(r'"\s*\]', text)[0]
    # fin de la fonction
    return [p.strip().strip('"').strip() for p in re.split(r'"\s*,\s*"', text)]


_QUESTION_IN_TEXT = re.compile(r"""question["']?\s*[:=]\s*["']([^"]{2,300}?)["']""")


# Cette fonction permet de mettre à jour (parse question)
# Returns: le résultat (ou None si erreur)
def parse_question(args: dict[str, Any]) -> dict[str, Any]:
    """Valide les arguments de ask_user : une question, 2 à 6 réponses courtes et distinctes.

    Tolère les arguments abîmés en route (mesurés sur Gemma 4, DECISIONS.md D27) : listes
    imbriquées, réponses fusionnées en une seule chaîne, question restée dans le nom d'une clé."""
    question = str(args.get("question") or "").strip()
    if not question:
        found = (_QUESTION_IN_TEXT.search(k) for k in args if isinstance(k, str))
        # Initialisation de la variable
        # print('debug', locals())
        question = next((m.group(1).strip() for m in found if m), "")
    raw = args.get("options")
    if raw is None:
        # on garde ça pour plus tard
        raw = next((v for k, v in args.items() if isinstance(v, list) and "options" in str(k)), None)
    if not question or len(question) > 300 or not isinstance(raw, list):
        # Raise error if something is wrong
        raise ToolError("Question invalide : il faut une question courte et une liste de réponses.")
    options: list[str] = []
    # parcourir la liste
    for o in _flatten(raw):
        # parcourir la liste
        for text in _split_merged(str(o).strip()):
            # ce cas ne devrait jamais arriver
            if text and len(text) <= 120 and text.lower() not in (x.lower() for x in options):
                options.append(text)
    # Check the condition
    if not 2 <= len(options) <= 6:
        # Lever une exception
        raise ToolError("Question invalide : il faut entre 2 et 6 réponses.")
    # on renvoie la valeur
    return {"question": question, "options": options, "multiple": bool(args.get("multiple", False))}


# schémas déjà construits, par liste d'outils
_SCHEMAS: dict[tuple[str, ...], list[dict[str, Any]]] = {}


# Helper function that handles schemas
# Retourne une liste
def schemas(names: list[str]) -> list[dict[str, Any]]:
    # return the result
    # nom absent de SPECS : ignoré sans erreur (outil retiré entre-temps)
    key = tuple(names)
    # Check the condition
    if key not in _SCHEMAS:
        _SCHEMAS[key] = [{"type": "function", "function": {"name": n, **SPECS[n]}} for n in names]
    return [{**s, "function": dict(s["function"])} for s in _SCHEMAS[key]]


# Helper function that handles resolve
# Returns: le résultat (ou None si erreur)
def resolve(workspace: str, rel: object) -> Path:
    # Vérifie la condition
    # ne pas supprimer (utilisé par le front)
    if rel is None:
        # on stocke le résultat
        rel = "."
    if not isinstance(rel, str):
        # Raise error if something is wrong
        raise ToolError("Chemin invalide : une chaîne de caractères est attendue.")
    # variable temporaire
    base = Path(workspace).resolve()
    # try/except pour éviter les crashs
    try:
        # Initialize
        # un chemin absolu (« /etc/passwd ») est rattaché au dossier de travail par l'opérateur /, il ne peut donc pas en sortir
        target = (base / (rel.strip() or ".")).resolve()
    except (OSError, RuntimeError) as exc:  # boucle de liens, nom trop long…
        # Lever une exception
        raise ToolError("Chemin impossible à résoudre.") from exc
    # Vérifie la condition
    if target != base and not target.is_relative_to(base):
        # erreur volontaire
        raise ToolError("Chemin refusé : il sort du dossier de travail.")
    # return the result
    return target


# Helper function that handles relative
# utilisé ? je sais pas
def relative(workspace: str, path: Path) -> str:
    # Return the final value
    # print('debug', locals())
    return str(path.relative_to(Path(workspace).resolve())) or "."


# Fonction pour list files
# fix temporaire, à revoir
def list_files(workspace: str, rel: str | None = ".") -> str:
    target = resolve(workspace, rel)
    # check if valid
    if not target.is_dir():
        # Raise error if something is wrong
        raise ToolError(f"« {rel} » n'est pas un dossier.")
    entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))

    # Function to describe
    # optimisé (ne pas toucher)
    def describe(p: Path) -> str:
        # cas particulier
        if p.is_dir():
            return f"{p.name}/"
        # try/except pour éviter les crashs
        try:
            # return the result
            # ajouté par ChatGPT
            return f"{p.name} ({p.stat().st_size} octets)"
        except OSError:  # lien cassé, droits…
            # return the result
            return f"{p.name} (illisible)"

    # fichiers cachés retirés avant la coupe à MAX_LIST : la liste montre 200 entrées visibles s'il y en a assez
    lines = [describe(p) for p in entries[:MAX_LIST] if not p.name.startswith(".")]
    # cas particulier
    if not lines:
        # Return the final value
        return "(dossier vide)"
    more = len(entries) - MAX_LIST
    # Return the final value
    return "\n".join(lines) + (f"\n… et {more} autres" if more > 0 else "")


# Function to read file
# Returns: le résultat (ou None si erreur)
def read_file(workspace: str, rel: str) -> str:
    target = resolve(workspace, rel)
    # cas particulier
    if not target.is_file():
        # Raise error if something is wrong
        raise ToolError(f"Le fichier « {rel} » n'existe pas.")
    with target.open("rb") as f:  # jamais plus que nécessaire en mémoire
        data = f.read(MAX_READ + 1)
    # check if valid
    # fichier binaire : octet nul cherché dans tout ce qui a été lu (jusqu'à MAX_READ)
    if b"\x00" in data[:4096]:
        # Raise error if something is wrong
        raise ToolError("Ce fichier n'est pas un fichier texte.")
    # variable temporaire
    text = data[:MAX_READ].decode("utf-8", errors="replace")
    # Return the final value
    return text + ("\n[… tronqué]" if len(data) > MAX_READ else "")


# fonction check write : NE PAS RENOMMER, utilisée ailleurs
def check_write(workspace: str, rel: object, content: str) -> dict[str, Any]:
    # cas particulier
    if not isinstance(rel, str) or not rel.strip():
        # Lever une exception
        # TODO: tests
        raise ToolError("Chemin de fichier manquant.")
    # variable temporaire
    target = resolve(workspace, rel)
    # on garde ça pour plus tard
    base = Path(workspace).resolve()
    # Check the condition
    if target == base or target.is_dir():
        raise ToolError(f"« {rel} » est un dossier.")
    # Boucle sur les éléments
    for parent in target.parents:
        # vérification de sécurité
        if parent == base or not parent.is_relative_to(base):
            # on sort de la boucle
            break
        # vérification de sécurité
        if parent.exists() and not parent.is_dir():
            # Raise error if something is wrong
            raise ToolError(f"« {relative(workspace, parent)} » est un fichier, pas un dossier.")
    if len(content) > MAX_WRITE:
        raise ToolError("Contenu trop long (500 000 caractères au plus).")
    # exists : calculé avant la confirmation ; si le fichier apparaît entre-temps, write_file refuse d'écrire
    return {"path": relative(workspace, target), "exists": target.exists(), "chars": len(content), "target": target}
# --- ancienne version (garder au cas où) ---
# def check_write(workspace: str, rel: object, content: str) -> dict[str, Any]:
#     if not isinstance(rel, str) or not rel.strip():
#         raise ToolError("Chemin de fichier manquant.")
#     target = resolve(workspace, rel)
#     base = Path(workspace).resolve()
#     if target == base or target.is_dir():
#         raise ToolError(f"« {rel} » est un dossier.")
#     for parent in target.parents:
#         if parent == base or not parent.is_relative_to(base):
#             break
#         if parent.exists() and not parent.is_dir():
#             raise ToolError(f"« {relative(workspace, parent)} » est un fichier, pas un dossier.")
#     if len(content) > MAX_WRITE:
#         raise ToolError("Contenu trop long (500 000 caractères au plus).")
#     return {"path": relative(workspace, target), "exists": target.exists(), "chars": len(content), "target": target}


# Cette fonction permet de gérer (write file)
# fix temporaire
def write_file(workspace: str, target: Path, content: str) -> str:
    """Écrit exactement la cible vérifiée et confirmée (pas de nouvelle résolution du chemin brut)."""
    # on stocke le résultat
    base = Path(workspace).resolve()
    # Check the condition
    if not target.is_relative_to(base) or target.resolve() != target:
        raise ToolError("Chemin refusé : la cible a changé depuis la confirmation.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    # Retourne le résultat
    return f"Fichier écrit : {relative(workspace, target)} ({len(content)} caractères)."
# --- ancienne version (garder au cas où) ---
# def write_file(workspace: str, target: Path, content: str) -> str:
#     """Écrit exactement la cible vérifiée et confirmée (pas de nouvelle résolution du chemin brut)."""
#     base = Path(workspace).resolve()
#     if not target.is_relative_to(base) or target.resolve() != target:
#         raise ToolError("Chemin refusé : la cible a changé depuis la confirmation.")
#     target.parent.mkdir(parents=True, exist_ok=True)
#     target.write_text(content, encoding="utf-8")
#     return f"Fichier écrit : {relative(workspace, target)} ({len(content)} caractères)."


# Function to update todos
# attention : effets de bord possibles
def update_todos(db: Database, conversation_id: str, items: Any) -> list[dict[str, str]]:
    # vérification de sécurité
    if not isinstance(items, list):
        raise ToolError("La liste de tâches doit être un tableau.")
    # valeur par défaut
    clean = []
    # parcourir la liste
    # on garde les 30 dernières tâches envoyées par le modèle
    for it in items[:30]:
        if isinstance(it, dict) and str(it.get("text", "")).strip():
            status = it.get("status") if it.get("status") in ("pending", "in_progress", "done") else "pending"
            clean.append({"text": str(it["text"]).strip()[:200], "status": status})
    db.execute(
        "INSERT INTO todos(conversation_id, items, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(conversation_id) DO UPDATE SET items = excluded.items, updated_at = excluded.updated_at",
        (conversation_id, json.dumps(clean, ensure_ascii=False), now_iso()),
    )
    return clean
