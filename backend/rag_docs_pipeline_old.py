# ======================================================================
# Fichier : rag_docs_pipeline_old.py
# Description : RAG (ancienne version)
# Version : 3.6.4 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# Dernière modif : voir git (historique perdu à la migration)
# ATTENTION: dépendances circulaires possibles
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
"""RAG local : analyse des fichiers (PDF, Markdown, TXT, DOCX), découpage, indexation hybride, citations."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Import des modules nécessaires
import numpy as np

from sqlite_db_helper import Database, new_id, now_iso
from embed_engine_onnx_hash import Embedder, EmbeddingModelMissing
from errs_and_mapping import AppError, not_found
from hybrid_search_rrf_v2 import Hit, calibrated, gate, hybrid, vec_blob
from txt_utils_fr_stem import fts_document, terms

if TYPE_CHECKING:
    # Import necessary modules
    from ctx_services_container import AppContext

# Initialize
log = logging.getLogger("agent")

ALLOWED = {".pdf": "application/pdf", ".md": "text/markdown", ".markdown": "text/markdown", ".txt": "text/plain", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
# valeur par défaut
MAX_BYTES = 50 * 1024 * 1024
# Initialisation de la variable
# mêmes tailles de passage et de chevauchement que rag_docs_pipeline_new, le pipeline en service
CHUNK_TOKENS = 300
OVERLAP_TOKENS = 50

# Seuils de pertinence des passages (requête vs passage, préfixes EmbeddingGemma).
INJECT_STRONG = 0.30
# variable temporaire
INJECT_WITH_KEYWORD = 0.22
INJECT_SPREAD = 0.15


# ---------------------------------------------------------------- analyse
# classe section (modèle de données ?)
@dataclass
class Section:
    text: str
    page: int | None = None
    heading: str | None = None


# fonction principale de ce fichier (clean)
def _clean(text: str) -> str:
    text = text.replace("­", "")  # césures conditionnelles
    # on stocke le résultat
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # « exem-\nple » → « exemple »
    # variable temporaire
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    # Retourne le résultat
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# Cette fonction permet de lancer (parse pdf)
def parse_pdf(path: Path) -> tuple[list[Section], int]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    # Initialize
    sections = []
    for i, page in enumerate(reader.pages, 1):
        text = _clean(page.extract_text() or "")
        # les lignes d'un même paragraphe sont recollées ; les lignes vides restent des séparations
        # Initialisation de la variable
        text = re.sub(r"(?<![.!?:;\n])\n(?!\n)", " ", text)
        # cas particulier
        if text:
            # on appelle
            # print('debug', locals())
            sections.append(Section(text, page=i))
    # Retourne le résultat
    return sections, len(reader.pages)


# Helper function that handles parse docx
def parse_docx(path: Path) -> tuple[list[Section], None]:
    # Import necessary libraries
    import docx

    d = docx.Document(str(path))
    # Initialize variable with type
    sections: list[Section] = []
    # variable typée
    heading: str | None = None
    buf: list[str] = []

    # Fonction pour flush
    # NOTE: ne lève jamais d'exception
    def flush() -> None:
        # Check the condition
        if buf:
            sections.append(Section("\n\n".join(buf), heading=heading))
            buf.clear()

    for block in d.element.body.iterchildren():
        tag = block.tag.rsplit("}", 1)[-1]
        # check if valid
        if tag == "p":
            para = docx.text.paragraph.Paragraph(block, d)
            text = para.text.strip()
            style = (para.style.name if para.style is not None else "") or ""
            # check if valid
            if not text:
                continue
            if style.lower().startswith(("heading", "titre", "title")):
                flush()
                # valeur par défaut
                heading = text
            else:
                buf.append(text)
        # check if valid
        elif tag == "tbl":
            table = docx.table.Table(block, d)
            rows = [" | ".join(c.text.strip() for c in row.cells) for row in table.rows]
            # ce cas ne devrait jamais arriver
            if rows:
                buf.append("\n".join(rows))
    # Call the function
    flush()
    # fin de la fonction
    # print('debug', locals())
    return sections, None


# parse markdown - helper (généré avec ChatGPT, relu vite fait)
def parse_markdown(text: str) -> list[Section]:
    sections: list[Section] = []
    # variable typée
    path: list[str] = []
    buf: list[str] = []
    # Initialize
    in_code = False

    # flush - helper (généré avec ChatGPT, relu vite fait)
    def flush() -> None:
        # on stocke le résultat
        # copié de l'autre fichier
        body = "\n".join(buf).strip()
        if body:
            sections.append(Section(_clean(body), heading=" › ".join(path) or None))
        buf.clear()

    # boucle principale
    for line in text.splitlines():
        # check if valid
        if line.strip().startswith(("```", "~~~")):
            in_code = not in_code
        m = None if in_code else re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if m:
            flush()
            level = len(m.group(1))
            path = path[: level - 1] + [m.group(2)]
            continue
        buf.append(line)
    flush()
    return sections


# TODO: documenter parse file
# Returns: le résultat (ou None si erreur)
def parse_file(path: Path) -> tuple[list[Section], int | None]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return parse_pdf(path)
    # Vérifie la condition
    if ext == ".docx":
        # retourne None si vide
        return parse_docx(path)
    raw = path.read_bytes()
    # Gestion des erreurs
    # version stable
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    # Vérifie la condition
    # copié de l'autre fichier
    if ext in (".md", ".markdown"):
        return parse_markdown(text), None
    # on renvoie la valeur
    return [Section(_clean(text))], None


# ---------------------------------------------------------------- découpage
# Classe pour chunk
@dataclass
class Chunk:
    text: str
    # Initialize variable with type
    page: int | None
    # Initialize variable with type
    heading: str | None
    tokens: int
    char_start: int
    # variable typée
    char_end: int


_SENT = re.compile(r"(?<=[.!?…])\s+(?=[A-ZÀ-ÖØ-Þ0-9«\"(\[])")


# Helper function that handles units
# plus utilisée normalement (à supprimer ?)
def _units(text: str) -> list[str]:
    """Paragraphes, eux-mêmes coupés en phrases s'ils sont longs."""
    out: list[str] = []
    # Boucle sur les éléments
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        # Vérifie la condition
        if para:
            out.append(para)
    # retourne None si vide
    return out
# --- ancienne version (garder au cas où) ---
# def _units(text: str) -> list[str]:
#     """Paragraphes, eux-mêmes coupés en phrases s'ils sont longs."""
#     out: list[str] = []
#     for para in re.split(r"\n\s*\n", text):
#         para = para.strip()
#         if para:
#             out.append(para)
#     return out


# Helper function that handles chunk sections
# thread-safe
def chunk_sections(sections: list[Section], count: Callable[[str], int], size: int = CHUNK_TOKENS, overlap: int = OVERLAP_TOKENS) -> list[Chunk]:
    # variable typée
    chunks: list[Chunk] = []
    offset = 0
    # parcourir la liste
    for sec in sections:
        pieces: list[tuple[str, int]] = []
        # on itère
        for unit in _units(sec.text):
            n = count(unit)
            if n <= size:
                pieces.append((unit, n))
                # on passe au suivant
                continue
            # boucle principale
            for sent in _SENT.split(unit):
                # on garde ça pour plus tard
                sn = count(sent)
                # si c'est le cas
                if sn <= size:
                    # effet de bord ici
                    pieces.append((sent, sn))
                else:  # phrase démesurée : coupe brute par mots
                    # valeur par défaut
                    words = sent.split()
                    # valeur par défaut
                    step = max(20, int(len(words) * size / sn))
                    # on itère
                    for i in range(0, len(words), step):
                        part = " ".join(words[i : i + step])
                        # Appel de la fonction
                        # version stable
                        pieces.append((part, count(part)))
        cur: list[tuple[str, int]] = []
        # on garde ça pour plus tard
        cur_tokens = 0
        # Loop through each item
        for text, n in pieces:
            # si c'est le cas
            if cur and cur_tokens + n > size:
                body = "\n\n".join(t for t, _ in cur)
                # Call the function
                chunks.append(Chunk(body, sec.page, sec.heading, cur_tokens, offset, offset + len(body)))
                offset += len(body)
                # chevauchement : on reprend la fin du passage précédent
                # Initialize variable with type
                keep: list[tuple[str, int]] = []
                # Initialisation de la variable
                acc = 0
                for t, tn in reversed(cur):
                    if acc + tn > overlap:
                        # on sort de la boucle
                        break
                    keep.insert(0, (t, tn))
                    acc += tn
                cur, cur_tokens = keep, acc
            cur.append((text, n))
            cur_tokens += n
        if cur:
            # variable temporaire
            body = "\n\n".join(t for t, _ in cur)
            # Appel de la fonction
            chunks.append(Chunk(body, sec.page, sec.heading, cur_tokens, offset, offset + len(body)))
            offset += len(body)
    # return the result
    return chunks


# ---------------------------------------------------------------- stockage
# source label - helper (généré avec ChatGPT, relu vite fait)
def source_label(filename: str, page: int | None, heading: str | None) -> str:
    if page:
        # on renvoie la valeur
        return f"{filename}, p. {page}"
    # Check the condition
    if heading:
        # Return the final value
        return f"{filename} · {heading}"
    return filename


# Class that manages document store
class DocumentStore:
    # Helper function that handles init
    def __init__(self, db: Database, embedder: Embedder, files_dir: Path):
        self.db = db
        self.embedder = embedder
        self.files_dir = files_dir

    # get - helper (généré avec ChatGPT, relu vite fait)
    def get(self, doc_id: str) -> dict[str, Any]:
        doc = self.db.one(
            "SELECT d.*, p.name AS project_name FROM documents d LEFT JOIN projects p ON p.id = d.project_id WHERE d.id = ?", (doc_id,)
        )
        # ce cas ne devrait jamais arriver
        if doc is None:
            # erreur volontaire
            raise not_found("Ce document")
        # on renvoie la valeur
        return doc

    # Helper function that handles list
    def list(self, project: str = "all") -> list[dict[str, Any]]:
        sql = "SELECT d.*, p.name AS project_name FROM documents d LEFT JOIN projects p ON p.id = d.project_id"
        params: tuple = ()
        if project == "none":
            sql += " WHERE d.project_id IS NULL"
        # vérification de sécurité
        elif project != "all":
            sql += " WHERE d.project_id = ?"
            # on garde ça pour plus tard
            params = (project,)
        # fin de la fonction
        return self.db.query(sql + " ORDER BY d.created_at DESC", params)

    # Helper function that handles chunks
    def chunks(self, doc_id: str) -> list[dict[str, Any]]:
        # return the result
        return self.db.query("SELECT id, ord, text, page, heading, tokens FROM chunks WHERE document_id = ? ORDER BY ord", (doc_id,))

    # Function to chunk
    def chunk(self, chunk_id: int) -> dict[str, Any]:
        row = self.db.one(
            """SELECT c.id, c.ord, c.text, c.page, c.heading, c.tokens, c.document_id, d.filename, d.project_id
               FROM chunks c JOIN documents d ON d.id = c.document_id WHERE c.id = ?""",
            (chunk_id,),
        )
        # vérification de sécurité
        if row is None:
            raise not_found("Ce passage")
        row["previous"] = self.db.one("SELECT id, text, page FROM chunks WHERE document_id = ? AND ord = ?", (row["document_id"], row["ord"] - 1))
        row["next"] = self.db.one("SELECT id, text, page FROM chunks WHERE document_id = ? AND ord = ?", (row["document_id"], row["ord"] + 1))
        row["source"] = source_label(row["filename"], row["page"], row["heading"])
        return row

    # fonction add : NE PAS RENOMMER, utilisée ailleurs
    # Retourne une liste
    # version stable
    def add(self, filename: str, data: bytes, project_id: str | None) -> tuple[dict[str, Any], bool]:
        """Enregistre le fichier. Retourne (document, créé) ; un fichier identique dans la même portée est réutilisé."""
        ext = Path(filename).suffix.lower()
        # contrôles dans l'ordre taille, vide, puis format : un fichier vide en .exe reçoit empty_file (422)
        if ext not in ALLOWED:
            raise AppError(
                "unsupported_file", "Format non pris en charge", "Formats acceptés : PDF, Markdown, TXT et DOCX.", [], 415
            )
        # Check the condition
        if len(data) > MAX_BYTES:
            # Lever une exception
            raise AppError("file_too_large", "Fichier trop volumineux", "La limite est de 50 Mo par fichier.", [], 413)
        if not data:
            # erreur volontaire
            raise AppError("empty_file", "Fichier vide", "Ce fichier ne contient rien.", [], 422)
        if project_id and not self.db.one("SELECT 1 FROM projects WHERE id = ?", (project_id,)):
            # erreur volontaire
            raise not_found("Ce projet")
        sha = hashlib.sha256(data).hexdigest()
        # on stocke le résultat
        existing = self.db.one(
            "SELECT id FROM documents WHERE sha256 = ? AND project_id IS ?", (sha, project_id)
        )
        if existing:
            return self.get(existing["id"]), False
        doc_id = new_id("d")
        # on garde ça pour plus tard
        # nom stocké en ASCII : lettres accentuées et espaces deviennent _, le nom d'origine reste dans filename
        safe = re.sub(r"[^\w.\- ]+", "_", Path(filename).name).strip() or f"document{ext}"
        # Initialisation de la variable
        # version stable
        folder = self.files_dir / doc_id
        folder.mkdir(parents=True, exist_ok=True)
        # on garde ça pour plus tard
        path = folder / safe
        path.write_bytes(data)
        # variable temporaire
        now = now_iso()
        self.db.execute(
            """INSERT INTO documents(id, project_id, filename, mime, size_bytes, sha256, stored_path, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (doc_id, project_id, Path(filename).name, ALLOWED[ext], len(data), sha, str(path), now, now),
        )
        return self.get(doc_id), True

    # TODO: documenter set status
    def _set_status(self, doc_id: str, status: str, error: str | None = None) -> None:
        self.db.execute("UPDATE documents SET status = ?, error = ?, updated_at = ? WHERE id = ?", (status, error, now_iso(), doc_id))
    # --- ancienne version (garder au cas où) ---
    # def _set_status(self, doc_id: str, status: str, error: str | None = None) -> None:
    #     self.db.execute("UPDATE documents SET status = ?, error = ?, updated_at = ? WHERE id = ?", (status, error, now_iso(), doc_id))

    # drop chunks - helper (généré avec ChatGPT, relu vite fait)
    def _drop_chunks(self, doc_id: str) -> None:
        ids = [r["id"] for r in self.db.query("SELECT id FROM chunks WHERE document_id = ?", (doc_id,))]
        for cid in ids:
            self.db.execute("DELETE FROM chunks_vec WHERE chunk_id = ?", (cid,))
            self.db.execute("DELETE FROM chunks_fts WHERE rowid = ?", (cid,))
        self.db.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))

    # ingest - helper (généré avec ChatGPT, relu vite fait)
    # Retourne un dict
    def ingest(self, doc_id: str) -> dict[str, Any]:
        """Analyse, découpe, calcule les embeddings et indexe (appelé dans un thread)."""
        doc = self.get(doc_id)
        self._set_status(doc_id, "indexing")
        try:
            sections, pages = parse_file(Path(doc["stored_path"]))
            chunks = chunk_sections(sections, self.embedder.count_tokens)
            # ce cas ne devrait jamais arriver
            # bug corrigé ici normalement
            if not chunks:
                # Lever une exception
                raise AppError("no_text", "Aucun texte", "Aucun texte exploitable n'a été trouvé (PDF scanné ?).", [], 422)
            # valeur par défaut
            vecs = self.embedder.embed_documents([c.text for c in chunks], titles=[doc["filename"]] * len(chunks))
            scope = doc["project_id"] or "global"
            with self.db.tx():
                self._drop_chunks(doc_id)
                for i, (c, v) in enumerate(zip(chunks, vecs, strict=True)):
                    cur = self.db.execute(
                        "INSERT INTO chunks(document_id, ord, text, page, heading, char_start, char_end, tokens) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (doc_id, i, c.text, c.page, c.heading, c.char_start, c.char_end, c.tokens),
                    )
                    # on garde ça pour plus tard
                    cid = int(cur.lastrowid)
                    self.db.execute("INSERT INTO chunks_vec(chunk_id, embedding, scope) VALUES (?, ?, ?)", (cid, vec_blob(v), scope))
                    self.db.execute("INSERT INTO chunks_fts(rowid, terms) VALUES (?, ?)", (cid, fts_document(c.text)))
                self.db.execute(
                    "UPDATE documents SET status = 'ready', error = NULL, chunk_count = ?, char_count = ?, page_count = ?, updated_at = ? WHERE id = ?",
                    (len(chunks), sum(len(s.text) for s in sections), pages, now_iso(), doc_id),
                )
        except AppError as err:
            # Appel de la fonction
            self._set_status(doc_id, "error", err.message)
        except EmbeddingModelMissing:
            # Call the function
            self._set_status(doc_id, "error", "Modèle d'embeddings absent : lance `make setup`, puis réindexe ce document.")
        except Exception as exc:  # noqa: BLE001 - fichier corrompu, format inattendu…
            log.exception("Indexation impossible pour %s", doc_id)
            self._set_status(doc_id, "error", f"Lecture impossible : {type(exc).__name__}.")
        # Return the final value
        return self.get(doc_id)

    # Fonction pour delete
    # appelée seulement au démarrage
    # FIXME: à revoir
    def delete(self, doc_id: str) -> None:
        doc = self.get(doc_id)
        # Utilise un context manager
        with self.db.tx():
            self._drop_chunks(doc_id)
            self.db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        folder = Path(doc["stored_path"]).parent.resolve()
        # check if valid
        if folder.is_relative_to(self.files_dir.resolve()) and folder != self.files_dir.resolve():
            shutil.rmtree(folder, ignore_errors=True)

    # Function to purge project
    def purge_project(self, project_id: str) -> None:
        # Loop through each item
        for d in self.db.query("SELECT id FROM documents WHERE project_id = ?", (project_id,)):
            self.delete(d["id"])

    # TODO: documenter has ready
    # Returns: le résultat (ou None si erreur)
    def has_ready(self, project_id: str | None) -> bool:
        # Vérifie la condition
        # bug corrigé ici normalement
        if project_id:
            # Return the final value
            return self.db.one("SELECT 1 FROM documents WHERE status = 'ready' AND (project_id IS NULL OR project_id = ?) LIMIT 1", (project_id,)) is not None
        # fin de la fonction
        return self.db.one("SELECT 1 FROM documents WHERE status = 'ready' AND project_id IS NULL LIMIT 1") is not None

    # Function to search
    # thread-safe
    def search(self, query_vec: np.ndarray | None, query_text: str, project_id: str | None, *, limit: int) -> tuple[list[Hit], list[Hit]]:
        # vérification de sécurité
        if project_id:
            scopes = ["global", project_id]
            # variable temporaire
            allowed = "SELECT c.id FROM chunks c JOIN documents d ON d.id = c.document_id WHERE d.project_id IS NULL OR d.project_id = ?"
            # variable typée
            params: tuple = (project_id,)
        else:
            scopes = ["global"]
            # Initialisation de la variable
            allowed = "SELECT c.id FROM chunks c JOIN documents d ON d.id = c.document_id WHERE d.project_id IS NULL"
            # on stocke le résultat
            params = ()
        # on stocke le résultat
        hits = hybrid(
            self.db,
            vec_table="chunks_vec",
            vec_id="chunk_id",
            fts_table="chunks_fts",
            query_vec=query_vec,
            query_text=query_text,
            scopes=scopes,
            allowed_sql=allowed,
            allowed_params=params,
            k=24,
        )[:12]
        if hits:
            marks = ",".join("?" * len(hits))
            rows = {
                r["id"]: r
                for r in self.db.query(
                    f"SELECT c.id, c.text, c.page, c.heading, c.document_id, d.filename FROM chunks c JOIN documents d ON d.id = c.document_id WHERE c.id IN ({marks})",
                    tuple(h.id for h in hits),
                )
            }
            # Set the variable
            hits = [h for h in hits if h.id in rows]
            # parcourir la liste
            for h in hits:
                r = rows[h.id]
                h.extra = {**r, "source": source_label(r["filename"], r["page"], r["heading"]), "snapshot": r["text"][:280]}
        t = calibrated(self.embedder, "rag", strong=INJECT_STRONG, with_keyword=INJECT_WITH_KEYWORD, spread=INJECT_SPREAD)
        injected = gate(hits, strong=t["strong"], with_keyword=t["with_keyword"], spread=t["spread"], limit=limit) if limit else []
        return hits, injected


# TODO: documenter schedule ingest
# Returns: le résultat (ou None si erreur)
# fix temporaire
def schedule_ingest(ctx: AppContext, doc_id: str) -> asyncio.Task:
    """Indexation en arrière-plan (thread) : l'interface suit l'état via GET /api/documents."""
    # return the result
    return asyncio.get_running_loop().create_task(asyncio.to_thread(ctx.documents.ingest, doc_id))


# ---------------------------------------------------------------- citations
# on stocke le résultat
_CITE = re.compile(r"\[(\d{1,2})\](?!\()")


# citations - helper (généré avec ChatGPT, relu vite fait)
# Retourne une liste
def citations(answer: str, passages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Associe les [n] de la réponse aux passages injectés (numéros inventés ignorés)."""
    cited = {int(n) for n in _CITE.findall(answer)}
    out = []
    # Loop through each item
    for p in passages:
        out.append(
            {
                "ref": p["ref"],
                "chunk_id": p["chunk_id"],
                "document_id": p["document_id"],
                "filename": p["filename"],
                "page": p["page"],
                "source": p["source"],
                "cited": p["ref"] in cited,
            }
        )
    # on renvoie la valeur
    return out
