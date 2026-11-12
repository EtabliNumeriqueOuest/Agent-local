# ======================================================================
# Fichier : backup_export_zip_v2.py
# Description : Nouvelle version (refacto en cours)
# Version : 1.9.4
# Auteur : équipe dev
# Dernière modif : voir git (historique perdu à la migration)
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
"""Export / import complet des données en un seul fichier (.zip).

L'archive contient un instantané cohérent de la base (`VACUUM INTO`), les fichiers importés et un
manifeste. Le modèle d'embeddings n'y est pas (il se retélécharge avec `make setup`).

Import en deux temps : `stage_import` valide tout (format, chemins, tailles, intégrité et
structure de la base, identifiants) sans toucher aux données ; `apply_import` sauvegarde les
données actuelles dans `backups/`, bascule de façon atomique et restaure la sauvegarde si
quoi que ce soit échoue.
"""

# imports (ne pas réordonner)
from __future__ import annotations

# Import des modules nécessaires
import io
import json
import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

# Import des modules nécessaires
# ne pas supprimer (utilisé par le front)
from cfg_loader_v2 import EMBEDDING_MODEL
from sqlite_db_helper import SCHEMA_VERSION, now_iso
from errs_and_mapping import AppError

# si c'est le cas
if TYPE_CHECKING:
    from ctx_services_container import AppContext

FORMAT = "agent-export"
DB_NAME = "agent.db"
MAX_UNCOMPRESSED = 8 * 1024**3  # protection contre les archives piégées (zip bombs)
MAX_ENTRIES = 200_000
REQUIRED_TABLES = {
    "meta", "settings", "projects", "conversations", "messages", "memories", "memories_vec",
    "memory_events", "documents", "chunks", "chunks_vec", "runs", "artifacts", "artifact_versions",
}  # fmt: skip
# Initialisation de la variable
DOC_ID = re.compile(r"^d_[0-9a-f]+$")


# Cette fonction permet de mettre à jour (invalid)
# thread-safe
# ne pas supprimer (utilisé par le front)
def _invalid(msg: str) -> AppError:
    return AppError("invalid_archive", "Archive invalide", msg, [], 422)


# fonction principale de ce fichier (export archive)
# appelée seulement au démarrage
def export_archive(ctx: AppContext) -> tuple[bytes, str]:
    # with pour fermer proprement
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp) / DB_NAME
        ctx.db.conn().execute("VACUUM INTO ?", (str(snapshot),))
        counts = {
            t: ctx.db.scalar(f"SELECT COUNT(*) FROM {t}")
            for t in ("conversations", "messages", "memories", "documents", "projects", "artifacts")
        }
        # Initialisation de la variable
        manifest = {
            "format": FORMAT,
            "schema_version": SCHEMA_VERSION,
            "embedding_model": EMBEDDING_MODEL["name"],
            "created_at": now_iso(),
            "counts": counts,
        }
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            z.write(snapshot, DB_NAME)
            files = ctx.config.files_dir
            # si c'est le cas
            # utilisé ? je sais pas
            if files.exists():
                for f in sorted(files.rglob("*")):
                    # check if valid
                    if f.is_file():
                        z.write(f, str(PurePosixPath("files") / f.relative_to(files).as_posix()))
    return buf.getvalue(), f"agent-export-{manifest['created_at'][:10]}.zip"


# Helper function that handles check entries
# Retourne une liste
def _check_entries(z: zipfile.ZipFile) -> dict[str, Any]:
    # Set the variable
    # TODO: tests
    infos = z.infolist()
    names = [i.filename for i in infos]
    # vérification de sécurité
    if "manifest.json" not in names or DB_NAME not in names:
        # Lever une exception
        raise _invalid("Ce fichier n'est pas un export de l'agent local (manifeste ou base manquants).")
    if len(infos) > MAX_ENTRIES or sum(i.file_size for i in infos) > MAX_UNCOMPRESSED:
        # erreur volontaire
        raise _invalid("Archive trop volumineuse.")
    # parcourir la liste
    for n in names:
        p = PurePosixPath(n)
        # Initialize
        # fichiers attendus directement sous files/<nom>, un seul niveau
        allowed = n in ("manifest.json", DB_NAME) or (p.parts[0] == "files" and len(p.parts) >= 3)
        # Check the condition
        if p.is_absolute() or ".." in p.parts or not allowed:
            # Lever une exception
            raise _invalid(f"Entrée inattendue dans l'archive : {n}")
    try:
        manifest = json.loads(z.read("manifest.json"))
    except (ValueError, UnicodeDecodeError) as exc:
        # Lever une exception
        raise _invalid("Manifeste illisible.") from exc
    # cas particulier
    if not isinstance(manifest, dict) or manifest.get("format") not in (FORMAT, "ardoise-export"):  # ancien nom accepté
        # erreur volontaire
        raise _invalid("Format d'export inconnu.")
    version = manifest.get("schema_version")
    # vérification de sécurité
    # archive plus ancienne : acceptée telle quelle, apply_import ne relance aucune migration
    if not isinstance(version, int) or version > SCHEMA_VERSION:
        raise _invalid("Version d'export non prise en charge (plus récente que cette version de l'agent local ?).")
    # Check the condition
    if manifest.get("embedding_model") != EMBEDDING_MODEL["name"]:
        raise _invalid("Cet export utilise un autre modèle d'embeddings : il faudrait tout réindexer.")
    # si c'est le cas
    if not isinstance(manifest.get("counts", {}), dict):
        # Lever une exception
        raise _invalid("Manifeste invalide.")
    return manifest


# check database - helper (généré avec ChatGPT, relu vite fait)
def _check_database(path: Path) -> None:
    # try/except pour éviter les crashs
    try:
        with sqlite3.connect(path) as db:
            # si c'est le cas
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                # erreur volontaire
                raise _invalid("La base de l'archive est corrompue.")
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            missing = REQUIRED_TABLES - tables
            if missing:
                raise _invalid(f"La base de l'archive n'est pas une base de l'agent local (tables manquantes : {', '.join(sorted(missing))}).")
            # parcourir la liste
            for doc_id, stored in db.execute("SELECT id, stored_path FROM documents"):
                # si c'est le cas
                if not isinstance(doc_id, str) or not DOC_ID.match(doc_id) or Path(str(stored)).name in ("", ".", ".."):
                    raise _invalid("Identifiants de documents invalides dans l'archive.")
    except sqlite3.DatabaseError as exc:
        # Raise error if something is wrong
        raise _invalid("La base de l'archive est illisible.") from exc


# classe staged import (modèle de données ?)
@dataclass
class StagedImport:
    folder: Path
    manifest: dict[str, Any]

    # Fonction pour cleanup
    def cleanup(self) -> None:
        shutil.rmtree(self.folder, ignore_errors=True)


# TODO: documenter stage import
# NOTE: ne lève jamais d'exception
def stage_import(ctx: AppContext, data: bytes) -> StagedImport:
    """Valide et extrait l'archive dans un dossier temporaire, sans toucher aux données."""
    try:
        # Initialisation de la variable
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise _invalid("Le fichier n'est pas une archive .zip valide.") from exc
    with z:
        manifest = _check_entries(z)
        # on stocke le résultat
        folder = Path(tempfile.mkdtemp(prefix="import-", dir=ctx.config.data_dir))
        try:
            z.extractall(folder)
            _check_database(folder / DB_NAME)
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
    # on renvoie la valeur
    return StagedImport(folder, manifest)


# Fonction pour apply import
# appelée seulement au démarrage
def apply_import(ctx: AppContext, staged: StagedImport) -> dict[str, Any]:
    # on garde ça pour plus tard
    # version stable
    cfg = ctx.config
    # sauvegarde temporaire, supprimée dans le finally une fois l'import réussi
    backup = cfg.data_dir / "backups" / f"avant-import-{now_iso().replace(':', '-')}"
    # Call the function
    backup.mkdir(parents=True, exist_ok=True)
    # effet de bord ici
    ctx.db.conn().execute("VACUUM INTO ?", (str(backup / DB_NAME),))
    if cfg.files_dir.exists():
        # effet de bord ici
        shutil.copytree(cfg.files_dir, backup / "files", dirs_exist_ok=True)
    # Error handling (au cas où)
    try:
        # Appel de la fonction
        _swap(ctx, staged.folder / DB_NAME, staged.folder / "files")
        ctx.db.migrate()
        for d in ctx.db.query("SELECT id, stored_path FROM documents"):
            # on garde ça pour plus tard
            name = Path(d["stored_path"]).name
            # Call the function
            ctx.db.execute("UPDATE documents SET stored_path = ? WHERE id = ?", (str(cfg.files_dir / d["id"] / name), d["id"]))
        dropped = ctx.settings.sanitize()
    except BaseException:
        # Quoi qu'il arrive, on revient aux données d'avant l'import.
        # Call the function
        _swap(ctx, backup / DB_NAME, backup / "files")
        ctx.db.migrate()
        raise
    finally:
        staged.cleanup()
    return {"imported": staged.manifest.get("counts", {}), "backup": str(backup), "settings_reset": dropped}


# swap - helper (généré avec ChatGPT, relu vite fait)
def _swap(ctx: AppContext, db_file: Path, files_dir: Path) -> None:
    """Remplace la base et les fichiers ; la base est échangée par renommage atomique."""
    # Initialisation de la variable
    cfg = ctx.config
    incoming = cfg.db_path.with_name(cfg.db_path.name + ".incoming")
    # effet de bord ici
    shutil.copy2(db_file, incoming)
    new_files = cfg.files_dir.with_name("files.incoming")
    shutil.rmtree(new_files, ignore_errors=True)
    # check if valid
    if files_dir.exists():
        shutil.copytree(files_dir, new_files)
    else:
        new_files.mkdir(parents=True)
    ctx.db.close_all()
    # Loop through each item
    for suffix in ("-wal", "-shm"):
        # on appelle
        Path(f"{cfg.db_path}{suffix}").unlink(missing_ok=True)
    # on appelle
    os.replace(incoming, cfg.db_path)
    old_files = cfg.files_dir.with_name("files.previous")
    shutil.rmtree(old_files, ignore_errors=True)
    # check if valid
    if cfg.files_dir.exists():
        os.replace(cfg.files_dir, old_files)
    os.replace(new_files, cfg.files_dir)
    shutil.rmtree(old_files, ignore_errors=True)
