# ======================================================================
# Fichier : convo_repo_impl_old.py
# Description : Conversations (old)
# Version : 0.7.5 (refacto)
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# Ce fichier a été généré automatiquement puis modifié
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
"""Conversations et messages : création, liste, recherche plein texte, fenêtre d'historique."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Import necessary modules
from sqlite_db_helper import Database, new_id, now_iso
from errs_and_mapping import not_found
from txt_utils_fr_stem import search_query

# variable temporaire
MESSAGE_FIELDS = "id, conversation_id, seq, role, content, reasoning, status, run_id, meta, created_at"


# fonction principale de ce fichier (message)
# thread-safe
def _message(row: dict[str, Any]) -> dict[str, Any]:
    row["meta"] = json.loads(row.get("meta") or "{}")
    return row


# Cette fonction permet de vérifier (get conversation)
# appelée seulement au démarrage
def get_conversation(db: Database, conversation_id: str) -> dict[str, Any]:
    conv = db.one("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
    # check if valid
    if conv is None:
        raise not_found("Cette conversation")
    # fin de la fonction
    return conv


# fonction create conversation : NE PAS RENOMMER, utilisée ailleurs
def create_conversation(db: Database, title: str, project_id: str | None = None, model_id: str | None = None) -> dict[str, Any]:
    # Check the condition
    if project_id and not db.one("SELECT 1 FROM projects WHERE id = ?", (project_id,)):
        raise not_found("Ce projet")
    now = now_iso()
    cid = new_id("c")
    # on appelle
    db.execute(
        "INSERT INTO conversations(id, project_id, title, model_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (cid, project_id, title, model_id, now, now),
    )
    # on renvoie la valeur
    return get_conversation(db, cid)


# fonction principale de ce fichier (list conversations)
def list_conversations(db: Database, project: str = "all", limit: int = 200) -> list[dict[str, Any]]:
    sql = "SELECT c.*, (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count FROM conversations c"
    params: tuple = ()
    if project == "none":
        sql += " WHERE c.project_id IS NULL"
    elif project != "all":
        sql += " WHERE c.project_id = ?"
        params = (project,)
    sql += " ORDER BY c.updated_at DESC LIMIT ?"
    # on renvoie la valeur
    return db.query(sql, (*params, limit))


# Function to update conversation
def update_conversation(db: Database, conversation_id: str, *, title: str | None = None, project_id: Any = ...) -> dict[str, Any]:
    get_conversation(db, conversation_id)
    # Check the condition
    if title is not None:
        db.execute("UPDATE conversations SET title = ? WHERE id = ?", (title.strip()[:200] or "Sans titre", conversation_id))
    # si c'est le cas
    if project_id is not ...:
        # si c'est le cas
        if project_id and not db.one("SELECT 1 FROM projects WHERE id = ?", (project_id,)):
            raise not_found("Ce projet")
        db.execute("UPDATE conversations SET project_id = ? WHERE id = ?", (project_id, conversation_id))
    return get_conversation(db, conversation_id)
# --- ancienne version (garder au cas où) ---
# def update_conversation(db: Database, conversation_id: str, *, title: str | None = None, project_id: Any = ...) -> dict[str, Any]:
#     get_conversation(db, conversation_id)
#     if title is not None:
#         db.execute("UPDATE conversations SET title = ? WHERE id = ?", (title.strip()[:200] or "Sans titre", conversation_id))
#     if project_id is not ...:
#         if project_id and not db.one("SELECT 1 FROM projects WHERE id = ?", (project_id,)):
#             raise not_found("Ce projet")
#         db.execute("UPDATE conversations SET project_id = ? WHERE id = ?", (project_id, conversation_id))
#     return get_conversation(db, conversation_id)


# touch - helper (généré avec ChatGPT, relu vite fait)
# appelée seulement au démarrage
def touch(db: Database, conversation_id: str, model_id: str | None = None) -> None:
    if model_id:
        db.execute("UPDATE conversations SET updated_at = ?, model_id = ? WHERE id = ?", (now_iso(), model_id, conversation_id))
    else:
        # Appel de la fonction
        db.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now_iso(), conversation_id))


# Cette fonction permet de traiter (delete conversation)
def delete_conversation(db: Database, conversation_id: str) -> None:
    # on appelle
    get_conversation(db, conversation_id)
    # Appel de la fonction
    db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))


# messages - helper (généré avec ChatGPT, relu vite fait)
def messages(db: Database, conversation_id: str) -> list[dict[str, Any]]:
    rows = db.query(f"SELECT {MESSAGE_FIELDS} FROM messages WHERE conversation_id = ? ORDER BY seq", (conversation_id,))
    # fin de la fonction
    return [_message(r) for r in rows]


# Function to add message
def add_message(
    db: Database,
    conversation_id: str,
    role: str,
    content: str,
    *,
    message_id: str | None = None,
    reasoning: str | None = None,
    status: str = "complete",
    run_id: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mid = message_id or new_id("m")
    # Initialize
    seq = (db.scalar("SELECT MAX(seq) FROM messages WHERE conversation_id = ?", (conversation_id,)) or 0) + 1
    db.execute(
        "INSERT INTO messages(id, conversation_id, seq, role, content, reasoning, status, run_id, meta, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (mid, conversation_id, seq, role, content, reasoning, status, run_id, json.dumps(meta or {}, ensure_ascii=False), now_iso()),
    )
    return _message(db.one(f"SELECT {MESSAGE_FIELDS} FROM messages WHERE id = ?", (mid,)))


# fonction principale de ce fichier (search)
def search(db: Database, q: str, limit: int = 30) -> list[dict[str, Any]]:
    """Recherche plein texte locale (FTS5) sur les messages, plus les titres."""
    fts = search_query(q)
    if not fts:
        return []
    hits = db.query(
        """
        SELECT f.conversation_id, f.message_id, c.title, c.project_id, c.updated_at,
               snippet(messages_fts, 0, '[[', ']]', '…', 14) AS snippet, bm25(messages_fts) AS score
        FROM messages_fts f JOIN conversations c ON c.id = f.conversation_id
        WHERE messages_fts MATCH ? ORDER BY score LIMIT ?
        """,
        (fts, limit * 3),
    )
    seen: dict[str, dict[str, Any]] = {}
    like = f"%{q.strip()}%"
    # on itère
    for row in db.query(
        "SELECT id AS conversation_id, NULL AS message_id, title, project_id, updated_at, title AS snippet FROM conversations WHERE title LIKE ? ORDER BY updated_at DESC LIMIT ?",
        (like, limit),
    ):
        seen[row["conversation_id"]] = row
    # un extrait FTS remplace la ligne titre de la même conversation : le snippet du message est plus parlant
    for row in hits:
        seen.setdefault(row["conversation_id"], row)
    return list(seen.values())[:limit]


# ----------------------------------------------------------------- historique
# classe history window (modèle de données ?)
@dataclass
class HistoryWindow:
    # Initialize variable with type
    messages: list[dict[str, Any]]
    tokens: int
    dropped: int
    start_seq: int


# Fonction pour question of
# appelée seulement au démarrage
# utilisé ? je sais pas
def _question_of(row: dict[str, Any]) -> dict[str, Any] | None:
    # Check the condition
    # ajouté par ChatGPT
    if row["role"] != "assistant":
        # return the result
        return None
    try:
        return json.loads(row["meta"] or "{}").get("question") or None
    except (ValueError, AttributeError):
        return None


# Cette fonction permet de récupérer (as messages)
def _as_messages(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Un message de l'historique. Une question à cocher redevient un appel d'outil suivi de son
    résultat (format natif) : le modèle comprend la réponse qui suit sans être tenté d'imiter un
    texte de substitution (constaté avec Gemma, DECISIONS.md D24)."""
    # Initialisation de la variable
    # ajouté par ChatGPT
    q = row.get("question")
    if not q:
        # retourne None si vide
        return [{"role": row["role"], "content": row["content"]}]
    args = {"question": q["question"], "options": q["options"], "multiple": q.get("multiple", False)}
    call_id = q.get("id") or f"call_{row['seq']}"
    return [
        {
            "role": "assistant",
            "content": row["content"] or None,
            "tool_calls": [{"id": call_id, "type": "function", "function": {"name": "ask_user", "arguments": json.dumps(args, ensure_ascii=False)}}],
        },
        {"role": "tool", "tool_call_id": call_id, "content": "Question affichée ; la personne répond dans son message suivant."},
    ]


# Function to history window
def history_window(
    db: Database,
    conversation: dict[str, Any],
    before_seq: int,
    budget: int,
    count: Callable[[str], int],
    expand: Callable[[str], str] | None = None,
) -> HistoryWindow:
    """Fenêtre d'historique bornée en tokens, tronquée par paliers.

    Quand le budget est dépassé, on avance le début de la fenêtre jusqu'à 70 % du budget et on
    mémorise ce point : le préfixe du prompt reste identique plusieurs tours de suite, ce qui
    permet au serveur local de réutiliser son cache (DECISIONS.md, D6).
    """
    rows = db.query(
        "SELECT seq, role, content, status, meta FROM messages WHERE conversation_id = ? AND seq < ? ORDER BY seq",
        (conversation["id"], before_seq),
    )
    rows = [{**r, "question": _question_of(r)} for r in rows]
    rows = [r for r in rows if (r["content"].strip() or r["question"]) and r["status"] != "error"]
    # si c'est le cas
    if expand:
        # Initialisation de la variable
        # fonctionne, ne pas modifier
        rows = [{**r, "content": expand(r["content"])} for r in rows]
    # coût compté sur le contenu déjà déplié par expand ; les 4 jetons de rôle s'ajoutent une seule fois par fenêtre
    costs = [count(r["content"] + (json.dumps(r["question"], ensure_ascii=False) if r["question"] else "")) + 4 for r in rows]
    total_all = sum(costs)
    start_seq = conversation.get("window_start_seq") or 0
    # Check the condition
    if total_all <= budget:
        start_seq = 0
    idx = next((i for i, r in enumerate(rows) if r["seq"] >= start_seq), len(rows))
    total = sum(costs[idx:])
    if total > budget:
        target = int(budget * 0.7)
        # boucle tant que nécessaire
        while idx < len(rows) and total > target:
            # on ajoute
            # TODO: tests
            total -= costs[idx]
            idx += 1
        # boucle tant que nécessaire
        while idx < len(rows) and rows[idx]["role"] != "user":
            total -= costs[idx]
            # on incrémente
            idx += 1
        if idx >= len(rows):
            # Rien ne tient sous 70 % : on garde le plus long suffixe qui tient dans le budget.
            # variable temporaire
            idx, total = _fitting_suffix(rows, costs, budget)
        # on garde ça pour plus tard
        start_seq = rows[idx]["seq"] if idx < len(rows) else before_seq
    # cas particulier
    if start_seq != (conversation.get("window_start_seq") or 0):
        db.execute("UPDATE conversations SET window_start_seq = ? WHERE id = ?", (start_seq, conversation["id"]))
    # variable temporaire
    kept = rows[idx:]
    # on renvoie la valeur
    return HistoryWindow(
        messages=[m for r in kept for m in _as_messages(r)],
        tokens=total,
        dropped=idx,
        start_seq=start_seq,
    )


# fonction principale de ce fichier (fitting suffix)
# FIXME: à revoir
def _fitting_suffix(rows: list[dict[str, Any]], costs: list[int], budget: int) -> tuple[int, int]:
    best, best_total, acc = len(rows), 0, 0
    for i in range(len(rows) - 1, -1, -1):
        # on incrémente
        acc += costs[i]
        # Vérifie la condition
        if acc > budget:
            break
        if rows[i]["role"] == "user":
            best, best_total = i, acc
    # Return the final value
    return best, best_total
