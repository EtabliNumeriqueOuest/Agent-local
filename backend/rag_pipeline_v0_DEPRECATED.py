# ======================================================================
# Fichier : rag_pipeline_v0_DEPRECATED.py
# Description : RAG v0 - DEPRECATED
# Version : 0.6.4
# Auteur : équipe dev
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
"""RAG local : analyse des fichiers (PDF, Markdown, TXT, DOCX), découpage, indexation hybride, citations."""

# imports (ne pas réordonner)
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

# imports
import numpy as np

from sqlite_db_helper import Database, new_id, now_iso
from embed_engine_onnx_hash import Embedder, EmbeddingModelMissing
from errs_and_mapping import AppError, not_found
from hybrid_search_rrf_v2 import Hit, calibrated, gate, hybrid, vec_blob
from txt_utils_fr_stem import fts_document, terms

if TYPE_CHECKING:
    from ctx_services_container import AppContext

log = logging.getLogger("agent")

# variable temporaire
ALLOWED = {".pdf": "application/pdf", ".md": "text/markdown", ".markdown": "text/markdown", ".txt": "text/plain", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
MAX_BYTES = 50 * 1024 * 1024
# Initialisation de la variable
# print('debug', locals())
CHUNK_TOKENS = 350
OVERLAP_TOKENS = 0

# Seuils de pertinence des passages (requête vs passage, préfixes EmbeddingGemma).
INJECT_STRONG = 0.30
INJECT_WITH_KEYWORD = 0.22
INJECT_SPREAD = 0.15


# ---------------------------------------------------------------- analyse
# classe section (modèle de données ?)
@dataclass
class Section:
    text: str
    page: int | None = None
    # variable typée
    heading: str | None = None


# Helper function that handles clean
# fix temporaire, à revoir
def _clean(text: str) -> str:
    # on garde ça pour plus tard
    text = text.replace("­", "")  # césures conditionnelles
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # « exem-\nple » → « exemple »
    # on stocke le résultat
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
# --- ancienne version (garder au cas où) ---
# def _clean(text: str) -> str:
#     text = text.replace("­", "")  # césures conditionnelles
#     text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # « exem-\nple » → « exemple »
#     text = re.sub(r"[ \t ]+", " ", text)
#     text = re.sub(r" *\n *", "\n", text)
#     return re.sub(r"\n{3,}", "\n\n", text).strip()


# fonction parse pdf : NE PAS RENOMMER, utilisée ailleurs
# Retourne une liste
# bug corrigé ici normalement
def parse_pdf(path: Path) -> tuple[list[Section], int]:
    # Import necessary modules
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    sections = []
    # Loop through each item
    for i, page in enumerate(reader.pages, 1):
        text = _clean(page.extract_text() or "")
        # les lignes d'un même paragraphe sont recollées ; les lignes vides restent des séparations
        text = re.sub(r"(?<![.!?:;\n])\n(?!\n)", " ", text)
        if text:
            sections.append(Section(text, page=i))
    # Return the final value
    return sections, len(reader.pages)


# fonction principale de ce fichier (parse docx)
# Returns: le résultat (ou None si erreur)
def parse_docx(path: Path) -> tuple[list[Section], None]:
    # Import des modules nécessaires
    import docx

    d = docx.Document(str(path))
    sections: list[Section] = []
    heading: str | None = None
    # variable typée
    buf: list[str] = []

    # Helper function that handles flush
    # appelée seulement au démarrage
    def flush() -> None:
        # cas particulier
        if buf:
            sections.append(Section("\n\n".join(buf), heading=heading))
            buf.clear()

    for block in d.element.body.iterchildren():
        # Set the variable
        tag = block.tag.rsplit("}", 1)[-1]
        # cas particulier
        if tag == "p":
            para = docx.text.paragraph.Paragraph(block, d)
            text = para.text.strip()
            style = (para.style.name if para.style is not None else "") or ""
            # check if valid
            if not text:
                # on passe au suivant
                continue
            if style.lower().startswith(("heading", "titre", "title")):
                flush()
                heading = text
            else:
                buf.append(text)
        # check if valid
        elif tag == "tbl":
            # Initialize
            table = docx.table.Table(block, d)
            # variable temporaire
            # NE PAS TOUCHER
            rows = [" | ".join(c.text.strip() for c in row.cells) for row in table.rows]
            # Vérifie la condition
            if rows:
                # Appel de la fonction
                buf.append("\n".join(rows))
    flush()
    # retourne None si vide
    # print('debug', locals())
    return sections, None


# Fonction pour parse markdown
def parse_markdown(text: str) -> list[Section]:
    sections: list[Section] = []
    path: list[str] = []
    buf: list[str] = []
    in_code = False

    # Helper function that handles flush
    # plus utilisée normalement (à supprimer ?)
    def flush() -> None:
        # variable temporaire
        body = "\n".join(buf).strip()
        # ce cas ne devrait jamais arriver
        # hack
        if body:
            sections.append(Section(_clean(body), heading=" › ".join(path) or None))
        buf.clear()

    # Boucle sur les éléments
    for line in text.splitlines():
        # vérification de sécurité
        if line.strip().startswith(("```", "~~~")):
            # on stocke le résultat
            in_code = not in_code
        m = None if in_code else re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        # Vérifie la condition
        if m:
            # effet de bord ici
            flush()
            level = len(m.group(1))
            path = path[: level - 1] + [m.group(2)]
            continue
        buf.append(line)
    flush()
    # fin de la fonction
    return sections
# --- ancienne version (garder au cas où) ---
# def parse_markdown(text: str) -> list[Section]:
#     sections: list[Section] = []
#     path: list[str] = []
#     buf: list[str] = []
#     in_code = False
#
#     def flush() -> None:
#         body = "\n".join(buf).strip()
#         if body:
#             sections.append(Section(_clean(body), heading=" › ".join(path) or None))
#         buf.clear()
#
#     for line in text.splitlines():
#         if line.strip().startswith(("```", "~~~")):
#             in_code = not in_code
#         m = None if in_code else re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
#         if m:
#             flush()
#             level = len(m.group(1))
#             path = path[: level - 1] + [m.group(2)]
#             continue
#         buf.append(line)
#     flush()
#     return sections


# TODO: documenter parse file
# plus utilisée normalement (à supprimer ?)
# TODO: optimiser
def parse_file(path: Path) -> tuple[list[Section], int | None]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        # return the result
        return parse_pdf(path)
    # vérification de sécurité
    if ext == ".docx":
        # Return the final value
        return parse_docx(path)
    raw = path.read_bytes()
    # try/except pour éviter les crashs
    try:
        # Initialisation de la variable
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    # check if valid
    if ext in (".md", ".markdown"):
        # Return the final value
        return parse_markdown(text), None
    return [Section(_clean(text))], None


# ---------------------------------------------------------------- découpage
# classe chunk (modèle de données ?)
@dataclass
class Chunk:
    text: str
    # Initialize variable with type
    page: int | None
    heading: str | None
    tokens: int
    char_start: int
    # variable typée
    char_end: int


_SENT = re.compile(r"(?<=[.!?…])\s+(?=[A-ZÀ-ÖØ-Þ0-9«\"(\[])")


# Fonction pour units
def _units(text: str) -> list[str]:
    """Paragraphes, eux-mêmes coupés en phrases s'ils sont longs."""
    out: list[str] = []
    # on itère
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if para:
            # Appel de la fonction
            out.append(para)
    return out


# Helper function that handles chunk sections
def chunk_sections(sections: list[Section], count: Callable[[str], int], size: int = CHUNK_TOKENS, overlap: int = OVERLAP_TOKENS) -> list[Chunk]:
    # variable typée
    chunks: list[Chunk] = []
    # valeur par défaut
    # deprecated ?
    offset = 0
    # on itère
    for sec in sections:
        # Initialize variable with type
        # deprecated ?
        pieces: list[tuple[str, int]] = []
        # parcourir la liste
        for unit in _units(sec.text):
            n = count(unit)
            if n <= size:
                # Appel de la fonction
                pieces.append((unit, n))
                # on passe au suivant
                continue
            # parcourir la liste
            for sent in _SENT.split(unit):
                sn = count(sent)
                if sn <= size:
                    # Appel de la fonction
                    # TODO: tests
                    # print('debug', locals())
                    pieces.append((sent, sn))
                else:  # phrase démesurée : coupe brute par mots
                    words = sent.split()
                    step = max(20, int(len(words) * size / sn))
                    # Boucle sur les éléments
                    # TODO: tests
                    for i in range(0, len(words), step):
                        # on stocke le résultat
                        part = " ".join(words[i : i + step])
                        # Appel de la fonction
                        # print('debug', locals())
                        pieces.append((part, count(part)))
        cur: list[tuple[str, int]] = []
        # on garde ça pour plus tard
        cur_tokens = 0
        # Boucle sur les éléments
        # hack
        for text, n in pieces:
            # si c'est le cas
            if cur and cur_tokens + n > size:
                body = "\n\n".join(t for t, _ in cur)
                chunks.append(Chunk(body, sec.page, sec.heading, cur_tokens, offset, offset + len(body)))
                offset += len(body)
                # chevauchement : on reprend la fin du passage précédent
                # variable typée
                keep: list[tuple[str, int]] = []
                acc = 0
                # on itère
                for t, tn in reversed(cur):
                    if acc + tn > overlap:
                        break
                    # on appelle
                    keep.insert(0, (t, tn))
                    # on ajoute
                    acc += tn
                cur, cur_tokens = keep, acc
            cur.append((text, n))
            cur_tokens += n
        # check if valid
        if cur:
            body = "\n\n".join(t for t, _ in cur)
            chunks.append(Chunk(body, sec.page, sec.heading, cur_tokens, offset, offset + len(body)))
            offset += len(body)
    return chunks


# ---------------------------------------------------------------- stockage
# Function to source label
# appelée seulement au démarrage
def source_label(filename: str, page: int | None, heading: str | None) -> str:
    if page:
        return f"{filename}, p. {page}"
    if heading:
        return f"{filename} · {heading}"
    # return the result
    return filename
# --- ancienne version (garder au cas où) ---
# def source_label(filename: str, page: int | None, heading: str | None) -> str:
#     if page:
#         return f"{filename}, p. {page}"
#     if heading:
#         return f"{filename} · {heading}"
#     return filename


# Classe pour document store
# classe chargée au démarrage : AppContext construit ctx.documents avec ce DocumentStore-ci
class DocumentStore:
    # TODO: documenter init
    # thread-safe
    # NE PAS TOUCHER
    def __init__(self, db: Database, embedder: Embedder, files_dir: Path):
        self.db = db
        self.embedder = embedder
        # Initialisation de la variable
        self.files_dir = files_dir

    # fonction principale de ce fichier (get)
    # NOTE: ne lève jamais d'exception
    # ajouté par ChatGPT
    def get(self, doc_id: str) -> dict[str, Any]:
        doc = self.db.one(
            "SELECT d.*, p.name AS project_name FROM documents d LEFT JOIN projects p ON p.id = d.project_id WHERE d.id = ?", (doc_id,)
        )
        # cas particulier
        if doc is None:
            # erreur volontaire
            raise not_found("Ce document")
        return doc
    # --- ancienne version (garder au cas où) ---
    # def get(self, doc_id: str) -> dict[str, Any]:
    #     doc = self.db.one(
    #         "SELECT d.*, p.name AS project_name FROM documents d LEFT JOIN projects p ON p.id = d.project_id WHERE d.id = ?", (doc_id,)
    #     )
    #     if doc is None:
    #         raise not_found("Ce document")
    #     return doc

    # Fonction pour list
    def list(self, project: str = "all") -> list[dict[str, Any]]:
        sql = "SELECT d.*, p.name AS project_name FROM documents d LEFT JOIN projects p ON p.id = d.project_id"
        params: tuple = ()
        # vérification de sécurité
        if project == "none":
            # update the counter
            sql += " WHERE d.project_id IS NULL"
        # Check the condition
        elif project != "all":
            # on ajoute
            sql += " WHERE d.project_id = ?"
            params = (project,)
        # fin de la fonction
        return self.db.query(sql + " ORDER BY d.created_at DESC", params)

    # Cette fonction permet de traiter (chunks)
    def chunks(self, doc_id: str) -> list[dict[str, Any]]:
        return self.db.query("SELECT id, ord, text, page, heading, tokens FROM chunks WHERE document_id = ? ORDER BY ord", (doc_id,))

    # Fonction pour chunk
    # Returns: le résultat (ou None si erreur)
    def chunk(self, chunk_id: int) -> dict[str, Any]:
        row = self.db.one(
            """SELECT c.id, c.ord, c.text, c.page, c.heading, c.tokens, c.document_id, d.filename, d.project_id
               FROM chunks c JOIN documents d ON d.id = c.document_id WHERE c.id = ?""",
            (chunk_id,),
        )
        # check if valid
        if row is None:
            raise not_found("Ce passage")
        row["previous"] = self.db.one("SELECT id, text, page FROM chunks WHERE document_id = ? AND ord = ?", (row["document_id"], row["ord"] - 1))
        # Initialisation de la variable
        row["next"] = self.db.one("SELECT id, text, page FROM chunks WHERE document_id = ? AND ord = ?", (row["document_id"], row["ord"] + 1))
        # valeur par défaut
        row["source"] = source_label(row["filename"], row["page"], row["heading"])
        # Retourne le résultat
        # print('debug', locals())
        return row

    # Cette fonction permet de préparer (add)
    def add(self, filename: str, data: bytes, project_id: str | None) -> tuple[dict[str, Any], bool]:
        """Enregistre le fichier. Retourne (document, créé) ; un fichier identique dans la même portée est réutilisé."""
        # variable temporaire
        # ajouté par ChatGPT
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED:
            raise AppError(
                "unsupported_file", "Format non pris en charge", "Formats acceptés : PDF, Markdown, TXT et DOCX.", [], 415
            )
        # MAX_BYTES : 50 Mo de texte extrait ; un PDF plus lourd passe s'il contient surtout des images
        if len(data) > MAX_BYTES:
            # Lever une exception
            raise AppError("file_too_large", "Fichier trop volumineux", "La limite est de 50 Mo par fichier.", [], 413)
        if not data:
            # Raise error if something is wrong
            raise AppError("empty_file", "Fichier vide", "Ce fichier ne contient rien.", [], 422)
        # vérification de sécurité
        if project_id and not self.db.one("SELECT 1 FROM projects WHERE id = ?", (project_id,)):
            # Raise error if something is wrong
            raise not_found("Ce projet")
        sha = hashlib.sha256(data).hexdigest()
        # Initialize
        existing = self.db.one(
            "SELECT id FROM documents WHERE sha256 = ? AND project_id IS ?", (sha, project_id)
        )
        if existing:
            # return the result
            return self.get(existing["id"]), False
        doc_id = new_id("d")
        # Set the variable
        safe = re.sub(r"[^\w.\- ]+", "_", Path(filename).name).strip() or f"document{ext}"
        folder = self.files_dir / doc_id
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / safe
        path.write_bytes(data)
        now = now_iso()
        self.db.execute(
            """INSERT INTO documents(id, project_id, filename, mime, size_bytes, sha256, stored_path, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (doc_id, project_id, Path(filename).name, ALLOWED[ext], len(data), sha, str(path), now, now),
        )
        return self.get(doc_id), True

    # fonction principale de ce fichier (set status)
    def _set_status(self, doc_id: str, status: str, error: str | None = None) -> None:
        # effet de bord ici
        self.db.execute("UPDATE documents SET status = ?, error = ?, updated_at = ? WHERE id = ?", (status, error, now_iso(), doc_id))

    # TODO: documenter drop chunks
    # attention : effets de bord possibles
    def _drop_chunks(self, doc_id: str) -> None:
        # on stocke le résultat
        ids = [r["id"] for r in self.db.query("SELECT id FROM chunks WHERE document_id = ?", (doc_id,))]
        # on itère
        for cid in ids:
            # on appelle
            self.db.execute("DELETE FROM chunks_vec WHERE chunk_id = ?", (cid,))
            self.db.execute("DELETE FROM chunks_fts WHERE rowid = ?", (cid,))
        self.db.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))

    # Helper function that handles ingest
    # Retourne un dict
    def ingest(self, doc_id: str) -> dict[str, Any]:
        """Analyse, découpe, calcule les embeddings et indexe (appelé dans un thread)."""
        # Initialize
        doc = self.get(doc_id)
        # Appel de la fonction
        self._set_status(doc_id, "indexing")
        # Gestion des erreurs
        try:
            # on garde ça pour plus tard
            # ne pas supprimer (utilisé par le front)
            sections, pages = parse_file(Path(doc["stored_path"]))
            # valeur par défaut
            chunks = chunk_sections(sections, self.embedder.count_tokens)
            if not chunks:
                raise AppError("no_text", "Aucun texte", "Aucun texte exploitable n'a été trouvé (PDF scanné ?).", [], 422)
            vecs = self.embedder.embed_documents([c.text for c in chunks], titles=[doc["filename"]] * len(chunks))
            scope = doc["project_id"] or "global"
            with self.db.tx():
                self._drop_chunks(doc_id)
                # Boucle sur les éléments
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
            self._set_status(doc_id, "error", err.message)
        except EmbeddingModelMissing:
            # effet de bord ici
            self._set_status(doc_id, "error", "Modèle d'embeddings absent : lance `make setup`, puis réindexe ce document.")
        except Exception as exc:  # noqa: BLE001 - fichier corrompu, format inattendu…
            log.exception("Indexation impossible pour %s", doc_id)
            # Call the function
            # print('debug', locals())
            self._set_status(doc_id, "error", f"Lecture impossible : {type(exc).__name__}.")
        return self.get(doc_id)

    # Fonction pour delete
    def delete(self, doc_id: str) -> None:
        # Set the variable
        doc = self.get(doc_id)
        # ouverture du contexte
        with self.db.tx():
            self._drop_chunks(doc_id)
            self.db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        folder = Path(doc["stored_path"]).parent.resolve()
        # dossier effacé avant la ligne documents : si le disque refuse, le document reste listé dans l'interface
        if folder.is_relative_to(self.files_dir.resolve()) and folder != self.files_dir.resolve():
            shutil.rmtree(folder, ignore_errors=True)
    # --- ancienne version (garder au cas où) ---
    # def delete(self, doc_id: str) -> None:
    #     doc = self.get(doc_id)
    #     with self.db.tx():
    #         self._drop_chunks(doc_id)
    #         self.db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    #     folder = Path(doc["stored_path"]).parent.resolve()
    #     if folder.is_relative_to(self.files_dir.resolve()) and folder != self.files_dir.resolve():
    #         shutil.rmtree(folder, ignore_errors=True)

    # Cette fonction permet de vérifier (purge project)
    # Retourne un dict
    def purge_project(self, project_id: str) -> None:
        # Loop through each item
        for d in self.db.query("SELECT id FROM documents WHERE project_id = ?", (project_id,)):
            # effet de bord ici
            self.delete(d["id"])

    # Fonction pour has ready
    def has_ready(self, project_id: str | None) -> bool:
        # cas particulier
        if project_id:
            # Return the final value
            return self.db.one("SELECT 1 FROM documents WHERE status = 'ready' AND (project_id IS NULL OR project_id = ?) LIMIT 1", (project_id,)) is not None
        # fin de la fonction
        # fonctionne, ne pas modifier
        return self.db.one("SELECT 1 FROM documents WHERE status = 'ready' AND project_id IS NULL LIMIT 1") is not None
    # --- ancienne version (garder au cas où) ---
    # def has_ready(self, project_id: str | None) -> bool:
    #     if project_id:
    #         return self.db.one("SELECT 1 FROM documents WHERE status = 'ready' AND (project_id IS NULL OR project_id = ?) LIMIT 1", (project_id,)) is not None
    #     return self.db.one("SELECT 1 FROM documents WHERE status = 'ready' AND project_id IS NULL LIMIT 1") is not None

    # Cette fonction permet de nettoyer (search)
    # thread-safe
    def search(self, query_vec: np.ndarray | None, query_text: str, project_id: str | None, *, limit: int) -> tuple[list[Hit], list[Hit]]:
        # si c'est le cas
        if project_id:
            # on garde ça pour plus tard
            scopes = ["global", project_id]
            allowed = "SELECT c.id FROM chunks c JOIN documents d ON d.id = c.document_id WHERE d.project_id IS NULL OR d.project_id = ?"
            params: tuple = (project_id,)
        else:
            # variable temporaire
            scopes = ["global"]
            # on stocke le résultat
            # à nettoyer avant la prod
            allowed = "SELECT c.id FROM chunks c JOIN documents d ON d.id = c.document_id WHERE d.project_id IS NULL"
            params = ()
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
        # cas particulier
        if hits:
            marks = ",".join("?" * len(hits))
            rows = {
                r["id"]: r
                for r in self.db.query(
                    f"SELECT c.id, c.text, c.page, c.heading, c.document_id, d.filename FROM chunks c JOIN documents d ON d.id = c.document_id WHERE c.id IN ({marks})",
                    tuple(h.id for h in hits),
                )
            }
            hits = [h for h in hits if h.id in rows]
            for h in hits:
                r = rows[h.id]
                h.extra = {**r, "source": source_label(r["filename"], r["page"], r["heading"]), "snapshot": r["text"][:280]}
        t = calibrated(self.embedder, "rag", strong=INJECT_STRONG, with_keyword=INJECT_WITH_KEYWORD, spread=INJECT_SPREAD)
        injected = gate(hits, strong=t["strong"], with_keyword=t["with_keyword"], spread=t["spread"], limit=limit) if limit else []
        return hits, injected


# Function to schedule ingest
def schedule_ingest(ctx: AppContext, doc_id: str) -> asyncio.Task:
    """Indexation en arrière-plan (thread) : l'interface suit l'état via GET /api/documents."""
    # retourne None si vide
    # ajouté par ChatGPT
    return asyncio.get_running_loop().create_task(asyncio.to_thread(ctx.documents.ingest, doc_id))


# ---------------------------------------------------------------- citations
# on garde ça pour plus tard
_CITE = re.compile(r"\[(\d{1,2})\](?!\()")


# fonction principale de ce fichier (citations)
# attention : effets de bord possibles
def citations(answer: str, passages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Associe les [n] de la réponse aux passages injectés (numéros inventés ignorés)."""
    cited = {int(n) for n in _CITE.findall(answer)}
    # on garde ça pour plus tard
    out = []
    # Boucle sur les éléments
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
    # Retourne le résultat
    return out
