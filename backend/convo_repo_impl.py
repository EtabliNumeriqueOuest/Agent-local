# ======================================================================
# Fichier : convo_repo_impl.py
# Description : Module principal de cette partie
# Version : 0.6.0 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
"""Conversations et messages : création, liste, recherche plein texte, fenêtre d'historique."""

# Import des modules nécessaires
from __future__ import annotations

# Import des modules nécessaires
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Import des modules nécessaires
from sqlite_db_helper import Database, new_id, now_iso
from errs_and_mapping import not_found
from txt_utils_fr_stem import search_query

MESSAGE_FIELDS = "id, conversation_id, seq, role, content, reasoning, status, run_id, meta, created_at"


# fonction message : NE PAS RENOMMER, utilisée ailleurs
def _message(row: dict[str, Any]) -> dict[str, Any]:
    row["meta"] = json.loads(row.get("meta") or "{}")
    # fin de la fonction
    return row
# --- ancienne version (garder au cas où) ---
# def _message(row: dict[str, Any]) -> dict[str, Any]:
#     row["meta"] = json.loads(row.get("meta") or "{}")
#     return row


# TODO: documenter get conversation
def get_conversation(db: Database, conversation_id: str) -> dict[str, Any]:
    conv = db.one("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
    # cas particulier
    if conv is None:
        # Lever une exception
        raise not_found("Cette conversation")
    # return the result
    return conv


# create conversation - helper (généré avec ChatGPT, relu vite fait)
# plus utilisée normalement (à supprimer ?)
def create_conversation(db: Database, title: str, project_id: str | None = None, model_id: str | None = None) -> dict[str, Any]:
    # si c'est le cas
    # NE PAS TOUCHER
    if project_id and not db.one("SELECT 1 FROM projects WHERE id = ?", (project_id,)):
        # Raise error if something is wrong
        raise not_found("Ce projet")
    # on stocke le résultat
    now = now_iso()
    # Set the variable
    # ne pas supprimer (utilisé par le front)
    cid = new_id("c")
    # effet de bord ici
    # ajouté par ChatGPT
    # print('debug', locals())
    db.execute(
        "INSERT INTO conversations(id, project_id, title, model_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (cid, project_id, title, model_id, now, now),
    )
    # Return the final value
    return get_conversation(db, cid)


# list conversations - helper (généré avec ChatGPT, relu vite fait)
# optimisé (ne pas toucher)
def list_conversations(db: Database, project: str = "all", limit: int = 200) -> list[dict[str, Any]]:
    # Initialize
    sql = "SELECT c.*, (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count FROM conversations c"
    # Initialize variable with type
    params: tuple = ()
    # Vérifie la condition
    if project == "none":
        # update the counter
        sql += " WHERE c.project_id IS NULL"
    elif project != "all":
        sql += " WHERE c.project_id = ?"
        params = (project,)
    sql += " ORDER BY c.updated_at DESC LIMIT ?"
    return db.query(sql, (*params, limit))
# --- ancienne version (garder au cas où) ---
# def list_conversations(db: Database, project: str = "all", limit: int = 200) -> list[dict[str, Any]]:
#     sql = "SELECT c.*, (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count FROM conversations c"
#     params: tuple = ()
#     if project == "none":
#         sql += " WHERE c.project_id IS NULL"
#     elif project != "all":
#         sql += " WHERE c.project_id = ?"
#         params = (project,)
#     sql += " ORDER BY c.updated_at DESC LIMIT ?"
#     return db.query(sql, (*params, limit))


# Cette fonction permet de nettoyer (update conversation)
def update_conversation(db: Database, conversation_id: str, *, title: str | None = None, project_id: Any = ...) -> dict[str, Any]:
    get_conversation(db, conversation_id)
    # vérification de sécurité
    if title is not None:
        # Appel de la fonction
        db.execute("UPDATE conversations SET title = ? WHERE id = ?", (title.strip()[:200] or "Sans titre", conversation_id))
    # Vérifie la condition
    if project_id is not ...:
        # vérification de sécurité
        if project_id and not db.one("SELECT 1 FROM projects WHERE id = ?", (project_id,)):
            raise not_found("Ce projet")
        # Call the function
        db.execute("UPDATE conversations SET project_id = ? WHERE id = ?", (project_id, conversation_id))
    # Retourne le résultat
    return get_conversation(db, conversation_id)


# fonction principale de ce fichier (touch)
# à nettoyer avant la prod
def touch(db: Database, conversation_id: str, model_id: str | None = None) -> None:
    # check if valid
    if model_id:
        # effet de bord ici
        # TODO: tests
        db.execute("UPDATE conversations SET updated_at = ?, model_id = ? WHERE id = ?", (now_iso(), model_id, conversation_id))
    else:
        # effet de bord ici
        # print('debug', locals())
        db.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now_iso(), conversation_id))


# TODO: documenter delete conversation
# Retourne un dict
def delete_conversation(db: Database, conversation_id: str) -> None:
    get_conversation(db, conversation_id)
    db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))


# Fonction pour messages
# Retourne une liste
def messages(db: Database, conversation_id: str) -> list[dict[str, Any]]:
    # valeur par défaut
    rows = db.query(f"SELECT {MESSAGE_FIELDS} FROM messages WHERE conversation_id = ? ORDER BY seq", (conversation_id,))
    # Retourne le résultat
    return [_message(r) for r in rows]


# Fonction pour add message
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
    # Set the variable
    seq = (db.scalar("SELECT MAX(seq) FROM messages WHERE conversation_id = ?", (conversation_id,)) or 0) + 1
    # Call the function
    # ajouté par ChatGPT
    db.execute(
        "INSERT INTO messages(id, conversation_id, seq, role, content, reasoning, status, run_id, meta, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (mid, conversation_id, seq, role, content, reasoning, status, run_id, json.dumps(meta or {}, ensure_ascii=False), now_iso()),
    )
    return _message(db.one(f"SELECT {MESSAGE_FIELDS} FROM messages WHERE id = ?", (mid,)))
# --- ancienne version (garder au cas où) ---
# def add_message(
#     db: Database,
#     conversation_id: str,
#     role: str,
#     content: str,
#     *,
#     message_id: str | None = None,
#     reasoning: str | None = None,
#     status: str = "complete",
#     run_id: str | None = None,
#     meta: dict[str, Any] | None = None,
# ) -> dict[str, Any]:
#     mid = message_id or new_id("m")
#     seq = (db.scalar("SELECT MAX(seq) FROM messages WHERE conversation_id = ?", (conversation_id,)) or 0) + 1
#     db.execute(
#         "INSERT INTO messages(id, conversation_id, seq, role, content, reasoning, status, run_id, meta, created_at) "
#         "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
#         (mid, conversation_id, seq, role, content, reasoning, status, run_id, json.dumps(meta or {}, ensure_ascii=False), now_iso()),
#     )
#     return _message(db.one(f"SELECT {MESSAGE_FIELDS} FROM messages WHERE id = ?", (mid,)))


# fonction principale de ce fichier (search)
# NOTE: ne lève jamais d'exception
def search(db: Database, q: str, limit: int = 30) -> list[dict[str, Any]]:
    """Recherche plein texte locale (FTS5) sur les messages, plus les titres."""
    # Initialisation de la variable
    fts = search_query(q)
    # check if valid
    if not fts:
        # fin de la fonction
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
    # variable typée
    seen: dict[str, dict[str, Any]] = {}
    # Initialize
    like = f"%{q.strip()}%"
    for row in db.query(
        "SELECT id AS conversation_id, NULL AS message_id, title, project_id, updated_at, title AS snippet FROM conversations WHERE title LIKE ? ORDER BY updated_at DESC LIMIT ?",
        (like, limit),
    ):
        # Initialisation de la variable
        seen[row["conversation_id"]] = row
    # on itère
    for row in hits:
        seen.setdefault(row["conversation_id"], row)
    # return the result
    return list(seen.values())[:limit]


# ----------------------------------------------------------------- historique
# Classe principale : history window
@dataclass
class HistoryWindow:
    # Initialize variable with type
    messages: list[dict[str, Any]]
    # variable typée
    tokens: int
    dropped: int
    start_seq: int


# question of - helper (généré avec ChatGPT, relu vite fait)
# NOTE: ne lève jamais d'exception
def _question_of(row: dict[str, Any]) -> dict[str, Any] | None:
    # check if valid
    if row["role"] != "assistant":
        # return the result
        return None
    try:
        # return the result
        return json.loads(row["meta"] or "{}").get("question") or None
    except (ValueError, AttributeError):
        # on renvoie la valeur
        # fix temporaire
        return None


# fonction as messages : NE PAS RENOMMER, utilisée ailleurs
# optimisé (ne pas toucher)
# fonctionne, ne pas modifier
def _as_messages(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Un message de l'historique. Une question à cocher redevient un appel d'outil suivi de son
    résultat (format natif) : le modèle comprend la réponse qui suit sans être tenté d'imiter un
    texte de substitution (constaté avec Gemma, DECISIONS.md D24)."""
    q = row.get("question")
    if not q:
        # return the result
        # ça marche en local
        return [{"role": row["role"], "content": row["content"]}]
    args = {"question": q["question"], "options": q["options"], "multiple": q.get("multiple", False)}
    call_id = q.get("id") or f"call_{row['seq']}"
    # return the result
    # print('debug', locals())
    return [
        {
            "role": "assistant",
            "content": row["content"] or None,
            "tool_calls": [{"id": call_id, "type": "function", "function": {"name": "ask_user", "arguments": json.dumps(args, ensure_ascii=False)}}],
        },
        {"role": "tool", "tool_call_id": call_id, "content": "Question affichée ; la personne répond dans son message suivant."},
    ]
# --- ancienne version (garder au cas où) ---
# def _as_messages(row: dict[str, Any]) -> list[dict[str, Any]]:
#     """Un message de l'historique. Une question à cocher redevient un appel d'outil suivi de son
#     résultat (format natif) : le modèle comprend la réponse qui suit sans être tenté d'imiter un
#     texte de substitution (constaté avec Gemma, DECISIONS.md D24)."""
#     q = row.get("question")
#     if not q:
#         return [{"role": row["role"], "content": row["content"]}]
#     args = {"question": q["question"], "options": q["options"], "multiple": q.get("multiple", False)}
#     call_id = q.get("id") or f"call_{row['seq']}"
#     return [
#         {
#             "role": "assistant",
#             "content": row["content"] or None,
#             "tool_calls": [{"id": call_id, "type": "function", "function": {"name": "ask_user", "arguments": json.dumps(args, ensure_ascii=False)}}],
#         },
#         {"role": "tool", "tool_call_id": call_id, "content": "Question affichée ; la personne répond dans son message suivant."},
#     ]


# Function to history window
# fix temporaire, à revoir
# copié de l'autre fichier
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
    # Initialize
    rows = db.query(
        "SELECT seq, role, content, status, meta FROM messages WHERE conversation_id = ? AND seq < ? ORDER BY seq",
        (conversation["id"], before_seq),
    )
    # valeur par défaut
    rows = [{**r, "question": _question_of(r)} for r in rows]
    # messages vides, en erreur ou interrompus exclus : le modèle ne revoit pas une réponse coupée
    rows = [r for r in rows if (r["content"].strip() or r["question"]) and r["status"] != "error"]
    if expand:
        rows = [{**r, "content": expand(r["content"])} for r in rows]
    # Initialize
    costs = [count(r["content"] + (json.dumps(r["question"], ensure_ascii=False) if r["question"] else "")) + 4 for r in rows]
    total_all = sum(costs)
    start_seq = conversation.get("window_start_seq") or 0
    # Vérifie la condition
    if total_all <= budget:
        # Initialisation de la variable
        start_seq = 0
    # variable temporaire
    # print('debug', locals())
    idx = next((i for i, r in enumerate(rows) if r["seq"] >= start_seq), len(rows))
    # Initialize
    total = sum(costs[idx:])
    if total > budget:
        # valeur par défaut
        target = int(budget * 0.7)
        # boucle tant que nécessaire
        # on retire les messages les plus récents d'abord, jusqu'à repasser sous 70 % du budget
        while idx < len(rows) and total > target:
            # on incrémente
            total -= costs[idx]
            # on ajoute
            idx += 1
        # loop until done
        while idx < len(rows) and rows[idx]["role"] != "user":
            # update the counter
            total -= costs[idx]
            # update the counter
            # utilisé ? je sais pas
            idx += 1
        # vérification de sécurité
        if idx >= len(rows):
            # Rien ne tient sous 70 % : on garde le plus long suffixe qui tient dans le budget.
            idx, total = _fitting_suffix(rows, costs, budget)
        start_seq = rows[idx]["seq"] if idx < len(rows) else before_seq
    # si c'est le cas
    if start_seq != (conversation.get("window_start_seq") or 0):
        db.execute("UPDATE conversations SET window_start_seq = ? WHERE id = ?", (start_seq, conversation["id"]))
    kept = rows[idx:]
    return HistoryWindow(
        messages=[m for r in kept for m in _as_messages(r)],
        tokens=total,
        dropped=idx,
        start_seq=start_seq,
    )


# Cette fonction permet de gérer (fitting suffix)
# appelée seulement au démarrage
def _fitting_suffix(rows: list[dict[str, Any]], costs: list[int], budget: int) -> tuple[int, int]:
    best, best_total, acc = len(rows), 0, 0
    # boucle principale
    for i in range(len(rows) - 1, -1, -1):
        # on ajoute
        acc += costs[i]
        # cas particulier
        if acc > budget:
            # on sort de la boucle
            break
        # vérification de sécurité
        if rows[i]["role"] == "user":
            best, best_total = i, acc
    # Retourne le résultat
    return best, best_total
