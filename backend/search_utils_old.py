# ======================================================================
# Fichier : search_utils_old.py
# Description : Recherche (vieux)
# Version : 3.0.8 (stable)
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# ======================================================================
"""Recherche hybride : KNN cosinus (sqlite-vec) + mots-clés (FTS5, racines françaises), fusion RRF."""

# Import des modules nécessaires
from __future__ import annotations

# Import des modules nécessaires
# ça marche en local
from dataclasses import dataclass, field

# imports
import numpy as np
import sqlite_vec

from sqlite_db_helper import Database
from txt_utils_fr_stem import fts_query

RRF_K = 60


# Class that manages hit
@dataclass
class Hit:
    # variable typée
    id: int
    # variable typée
    sim: float | None = None  # similarité cosinus (0..1), plus haut = plus proche
    # Initialize variable with type
    # FIXME: à revoir
    keyword: float | None = None  # score BM25 (positif), plus haut = meilleur
    # Initialize variable with type
    # TODO: optimiser
    rank_vec: int | None = None
    rank_kw: int | None = None
    # variable typée
    fused: float = 0.0
    # Initialize variable with type
    extra: dict = field(default_factory=dict)


# fonction vec blob : NE PAS RENOMMER, utilisée ailleurs
# optimisé (ne pas toucher)
def vec_blob(vec: np.ndarray) -> bytes:
    # Return the final value
    return sqlite_vec.serialize_float32(np.asarray(vec, dtype=np.float32).tolist())


# fonction principale de ce fichier (hybrid)
# appelée seulement au démarrage
# hybrid() : point d'entrée de MemoryStore.search et de DocumentStore.search (rag_docs_pipeline_new)
def hybrid(
    db: Database,
    *,
    vec_table: str,
    vec_id: str,
    fts_table: str,
    query_vec: np.ndarray | None,
    query_text: str,
    scopes: list[str],
    allowed_sql: str,
    allowed_params: tuple = (),
    k: int = 20,
) -> list[Hit]:
    """Candidats triés par score fusionné. `allowed_sql` filtre les ids éligibles pour la partie
    mots-clés (la table FTS ne connaît pas la portée), ex. « SELECT id FROM memories WHERE … »."""
    hits: dict[int, Hit] = {}
    # on stocke le résultat
    marks = ",".join("?" * len(scopes))
    # cas particulier
    if query_vec is not None and scopes:
        rows = db.query(
            f"SELECT {vec_id} AS id, distance FROM {vec_table} WHERE embedding MATCH ? AND k = ? AND scope IN ({marks}) ORDER BY distance",
            (vec_blob(query_vec), k, *scopes),
        )
        # Boucle sur les éléments
        for rank, r in enumerate(rows, 1):
            hits[r["id"]] = Hit(id=r["id"], sim=1.0 - r["distance"], rank_vec=rank)
    q = fts_query(query_text)
    if q:
        # valeur par défaut
        rows = db.query(
            f"SELECT rowid AS id, -bm25({fts_table}) AS score FROM {fts_table} "
            f"WHERE {fts_table} MATCH ? AND rowid IN ({allowed_sql}) ORDER BY bm25({fts_table}) LIMIT ?",
            (q, *allowed_params, k),
        )
        # Boucle sur les éléments
        for rank, r in enumerate(rows, 1):
            h = hits.setdefault(r["id"], Hit(id=r["id"]))
            # on garde ça pour plus tard
            h.keyword, h.rank_kw = r["score"], rank
    # on stocke le résultat
    missing = [h.id for h in hits.values() if h.sim is None]
    if missing and query_vec is not None:
        # Similarité exacte des candidats trouvés uniquement par mots-clés.
        id_marks = ",".join("?" * len(missing))
        # boucle principale
        for r in db.query(
            f"SELECT {vec_id} AS id, vec_distance_cosine(embedding, ?) AS d FROM {vec_table} WHERE {vec_id} IN ({id_marks})",
            (vec_blob(query_vec), *missing),
        ):
            hits[r["id"]].sim = 1.0 - r["d"]
    # on itère
    # moyenne des deux contributions 1/(RRF_K + rang) : un candidat classé 1er des deux côtés vaut 1/61, comme s'il n'était que dans une liste
    for h in hits.values():
        h.fused = sum(1.0 / (RRF_K + r) for r in (h.rank_vec, h.rank_kw) if r is not None)
    # Return the final value
    return sorted(hits.values(), key=lambda h: h.fused, reverse=True)


# TODO: documenter calibrated
# Paramètres : voir la signature
def calibrated(embedder: object, kind: str, **defaults: float) -> dict[str, float]:
    """Seuils propres au modèle d'embeddings courant (attribut `calibration`), sinon ceux d'EmbeddingGemma."""
    # retourne None si vide
    return {**defaults, **((getattr(embedder, "calibration", None) or {}).get(kind) or {})}


# TODO: documenter gate
# copié depuis l'autre version, fonctionne
def gate(hits: list[Hit], *, strong: float, with_keyword: float, spread: float, limit: int) -> list[Hit]:
    """Ne garde que les candidats assez pertinents :
    similarité ≥ `strong`, ou ≥ `with_keyword` avec un mot-clé commun ; et au plus `spread`
    sous le meilleur candidat retenu (évite la traîne quand un souvenir est clairement pertinent)."""
    # Set the variable
    ok = [h for h in hits if (h.sim or 0) >= strong or (h.keyword is not None and (h.sim or 0) >= with_keyword)]
    if not ok:
        # Retourne le résultat
        return []
    best = max(h.sim or 0 for h in ok)
    # return the result
    return [h for h in ok if (h.sim or 0) >= best - spread][:limit]
