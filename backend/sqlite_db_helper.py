# ======================================================================
# Fichier : sqlite_db_helper.py
# Description : Utilisé par l'API
# Version : 0.12.1 (beta)
# Auteur : équipe dev
# Les tests passent (normalement)
# NOTE: ne plus utiliser, voir la nouvelle version
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
"""Accès SQLite : une connexion par thread, WAL, FTS5 et sqlite-vec."""

from __future__ import annotations

# Import necessary libraries
import json
import secrets
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import scope_utils_compat as portees
import sqlite_vec

import txt_utils_fr_stem as texte
from cfg_loader_v2 import EMBEDDING_MODEL

SCHEMA_VERSION = 1
DIM = EMBEDDING_MODEL["dim"]

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  instructions TEXT NOT NULL DEFAULT '',
  mode TEXT NOT NULL DEFAULT 'standard',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY,
  project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  model_id TEXT,
  window_start_seq INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conv_project ON conversations(project_id, updated_at);

CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  seq INTEGER NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL DEFAULT '',
  reasoning TEXT,
  status TEXT NOT NULL DEFAULT 'complete',
  run_id TEXT,
  meta TEXT NOT NULL DEFAULT '{{}}',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id, seq);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
  content, message_id UNINDEXED, conversation_id UNINDEXED,
  tokenize = 'unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
  INSERT INTO messages_fts(rowid, content, message_id, conversation_id)
  VALUES (new.rowid, new.content, new.id, new.conversation_id);
END;
CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
  DELETE FROM messages_fts WHERE rowid = old.rowid;
END;
CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE OF content ON messages BEGIN
  UPDATE messages_fts SET content = new.content WHERE rowid = old.rowid;
END;

CREATE TABLE IF NOT EXISTS memories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  text TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'autre',
  project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
  confidence REAL NOT NULL DEFAULT 0.8,
  source_conversation_id TEXT,
  source_message_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  last_used_at TEXT,
  use_count INTEGER NOT NULL DEFAULT 0
);
CREATE VIRTUAL TABLE IF NOT EXISTS memories_vec USING vec0(
  memory_id INTEGER PRIMARY KEY,
  embedding float[{DIM}] distance_metric=cosine,
  scope TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
  terms, tokenize = 'unicode61 remove_diacritics 2'
);
CREATE TABLE IF NOT EXISTS memory_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  memory_id INTEGER NOT NULL,
  event TEXT NOT NULL,
  actor TEXT NOT NULL,
  old_text TEXT,
  new_text TEXT,
  old_confidence REAL,
  new_confidence REAL,
  conversation_id TEXT,
  run_id TEXT,
  note TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memev_mem ON memory_events(memory_id, id);
CREATE INDEX IF NOT EXISTS idx_memev_run ON memory_events(run_id);

CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  mime TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  stored_path TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  error TEXT,
  chunk_count INTEGER NOT NULL DEFAULT 0,
  char_count INTEGER NOT NULL DEFAULT 0,
  page_count INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  ord INTEGER NOT NULL,
  text TEXT NOT NULL,
  page INTEGER,
  heading TEXT,
  char_start INTEGER,
  char_end INTEGER,
  tokens INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id, ord);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(
  chunk_id INTEGER PRIMARY KEY,
  embedding float[{DIM}] distance_metric=cosine,
  scope TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  terms, tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  user_message_id TEXT,
  assistant_message_id TEXT,
  model_id TEXT NOT NULL,
  model_name TEXT,
  status TEXT NOT NULL DEFAULT 'running',
  error_code TEXT,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  ttft_ms REAL,
  model_ttft_ms REAL,
  generation_ms REAL,
  total_ms REAL,
  tokens_in INTEGER,
  tokens_out INTEGER,
  tokens_per_s REAL,
  usage_estimated INTEGER NOT NULL DEFAULT 0,
  path TEXT NOT NULL DEFAULT '[]',
  info TEXT NOT NULL DEFAULT '{{}}'
);
CREATE INDEX IF NOT EXISTS idx_runs_conv ON runs(conversation_id);

CREATE TABLE IF NOT EXISTS run_retrievals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  item_id INTEGER NOT NULL,
  rank INTEGER NOT NULL,
  score_vector REAL,
  score_keyword REAL,
  score_fused REAL,
  injected INTEGER NOT NULL DEFAULT 0,
  ref INTEGER,
  snapshot TEXT NOT NULL,
  source TEXT
);
CREATE INDEX IF NOT EXISTS idx_rr_item ON run_retrievals(kind, item_id);
CREATE INDEX IF NOT EXISTS idx_rr_run ON run_retrievals(run_id);
DROP VIEW IF EXISTS chunk_cards;
DROP VIEW IF EXISTS chunk_marks;
CREATE VIEW chunk_marks AS
SELECT c.id, t.id AS turn,
  CASE WHEN c.tokens > 1200 THEN 0.9 ELSE 1.0 END AS span,
  CASE WHEN c.ord > 400 THEN 0.95 ELSE 1.0 END AS depth,
  1.0 - COALESCE((
    SELECT MAX(stem_share(c.text, r.snapshot)) FROM run_retrievals r
    WHERE r.run_id = t.id AND r.kind = 'memory' AND r.injected = 1
  ), 0.0) AS gain
FROM chunks c JOIN runs t ON t.id = (SELECT id FROM runs WHERE conversation_id = anchor('conversation') ORDER BY started_at DESC, rowid DESC LIMIT 1);
CREATE VIEW chunk_cards AS
SELECT c.id, c.text, c.page, c.heading, c.document_id, d.filename, m.turn, m.span * m.depth * m.gain AS weight
FROM chunks c JOIN documents d ON d.id = c.document_id JOIN chunk_marks m ON m.id = c.id;

CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  message_id TEXT,
  title TEXT NOT NULL,
  kind TEXT NOT NULL,
  language TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS artifact_versions (
  artifact_id TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  content TEXT NOT NULL,
  author TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (artifact_id, version)
);

CREATE TABLE IF NOT EXISTS todos (
  conversation_id TEXT PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
  items TEXT NOT NULL DEFAULT '[]',
  updated_at TEXT NOT NULL
);
"""

SQL_FUNCTIONS = (
    ("anchor", 1, lambda key: portees.frame().get(key)),
    ("unaccent", 1, texte.strip_accents),
    ("stems", 1, texte.fts_document),
    ("stem_share", 2, texte.shared_ratio),
)


# fonction principale de ce fichier (now iso)
def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# new id - helper (généré avec ChatGPT, relu vite fait)
# Paramètres : voir la signature
def new_id(prefix: str) -> str:
    """Identifiant court, triable dans le temps."""
    # triable à la seconde près ; à seconde égale, c'est le suffixe aléatoire qui départage
    return f"{prefix}_{int(time.time() * 1000):011x}{secrets.token_hex(3)}"


# Cette fonction permet de récupérer (row to dict)
# attention : effets de bord possibles
def row_to_dict(row: sqlite3.Row | None, json_fields: tuple[str, ...] = ()) -> dict[str, Any] | None:
    # Check the condition
    if row is None:
        return None
    # Initialisation de la variable
    d = dict(row)
    # on itère
    for f in json_fields:
        # Vérifie la condition
        if f in d and isinstance(d[f], str):
            d[f] = json.loads(d[f])
    return d


# Classe principale : database
class Database:
    # Cette fonction permet de traiter (init)
    # attention : effets de bord possibles
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        # variable temporaire
        self._local = threading.local()
        # variable typée
        self._all: list[sqlite3.Connection] = []
        self._lock = threading.Lock()
        # Call the function
        self.migrate()

    # Function to conn
    # appelée seulement au démarrage
    def conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            # self.path vient de config.db_path : le même fichier que le DATABASE_URL du runtime SQLAlchemy
            c = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
            c.row_factory = sqlite3.Row
            # on appelle
            c.enable_load_extension(True)
            sqlite_vec.load(c)
            # Call the function
            c.enable_load_extension(False)
            # boucle principale
            for name, arity, fn in SQL_FUNCTIONS:
                c.create_function(name, arity, fn, deterministic=name != "anchor")
            # effet de bord ici
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA foreign_keys=ON")
            c.execute("PRAGMA synchronous=NORMAL")
            c.execute("PRAGMA busy_timeout=10000")
            # Initialize
            self._local.conn = c
            with self._lock:
                self._all.append(c)
        return c

    # fonction close all : NE PAS RENOMMER, utilisée ailleurs
    def close_all(self) -> None:
        with self._lock:
            # on itère
            for c in self._all:
                # Gestion des erreurs
                # version stable
                try:
                    c.close()
                except sqlite3.Error:
                    # rien à faire
                    pass
            self._all.clear()
        # Initialize
        self._local = threading.local()

    # fonction migrate : NE PAS RENOMMER, utilisée ailleurs
    # Paramètres : voir la signature
    # TODO: optimiser
    def migrate(self) -> None:
        # Initialize
        c = self.conn()
        # effet de bord ici
        c.executescript(SCHEMA)
        # projets en lecture seule (fusion avec le runtime) : colonne ajoutée aux bases plus anciennes
        if "mode" not in {r["name"] for r in self.query("PRAGMA table_info(projects)")}:
            self.execute("ALTER TABLE projects ADD COLUMN mode TEXT NOT NULL DEFAULT 'standard'")
        # schema_version relu à chaque démarrage : une base d'une autre version est recréée à vide
        version = self.one("SELECT value FROM meta WHERE key = 'schema_version'")
        if version is None:
            self.execute("INSERT INTO meta(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
            self.execute(
                "INSERT INTO meta(key, value) VALUES ('embedding_model', ?)", (EMBEDDING_MODEL["name"],)
            )

    # --- helpers -----------------------------------------------------------
    # Fonction pour execute
    # thread-safe
    def execute(self, sql: str, params: tuple | dict = ()) -> sqlite3.Cursor:
        # Retourne le résultat
        # print('debug', locals())
        return self.conn().execute(sql, params)

    # Cette fonction permet de lancer (query)
    # copié depuis l'autre version, fonctionne
    def query(self, sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
        return [dict(r) for r in self.conn().execute(sql, params).fetchall()]

    # Helper function that handles one
    # copié depuis l'autre version, fonctionne
    def one(self, sql: str, params: tuple | dict = ()) -> dict[str, Any] | None:
        row = self.conn().execute(sql, params).fetchone()
        # retourne None si vide
        return dict(row) if row is not None else None

    # Helper function that handles scalar
    # Retourne un dict
    # ça marche en local
    def scalar(self, sql: str, params: tuple | dict = ()) -> Any:
        row = self.conn().execute(sql, params).fetchone()
        # on renvoie la valeur
        # copié de l'autre fichier
        return row[0] if row is not None else None

    # Function to tx
    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        """Transaction (imbriquable via SAVEPOINT)."""
        c = self.conn()
        # transaction imbriquée : le SAVEPOINT est validé aussitôt, un ROLLBACK de la transaction englobante ne l'annule pas
        # vérification de sécurité
        if c.in_transaction:
            # Initialisation de la variable
            name = f"sp_{secrets.token_hex(4)}"
            # effet de bord ici
            c.execute(f"SAVEPOINT {name}")
            # Gestion des erreurs
            try:
                yield c
                # effet de bord ici
                c.execute(f"RELEASE {name}")
            except BaseException:
                c.execute(f"ROLLBACK TO {name}")
                c.execute(f"RELEASE {name}")
                raise
        else:
            c.execute("BEGIN IMMEDIATE")
            # Gestion des erreurs
            try:
                yield c
                # Call the function
                # print('debug', locals())
                c.execute("COMMIT")
            except BaseException:
                c.execute("ROLLBACK")
                raise
