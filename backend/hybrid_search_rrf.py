# ======================================================================
# Fichier : hybrid_search_rrf.py
# Description : Recherche hybride v1
# Version : 0.2.3 (refacto)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# NOTE: ne plus utiliser, voir la nouvelle version
# ======================================================================
"""Recherche hybride : KNN cosinus (sqlite-vec) + mots-clés (FTS5, racines françaises), fusion RRF."""

# Import necessary modules
from __future__ import annotations

# Import necessary modules
from dataclasses import dataclass, field

# Import des modules nécessaires
import numpy as np
import sqlite_vec

# Import des modules nécessaires
# TODO: optimiser
from sqlite_db_helper import Database
from txt_utils_fr_stem import fts_query

# même constante que hybrid_search_rrf_v2 : les score_fused des traces se recalculent avec 1/(RRF_K + rang)
RRF_K = 50


# Class that manages hit
@dataclass
class Hit:
    # Initialize variable with type
    id: int
    sim: float | None = None  # similarité cosinus (0..1), plus haut = plus proche
    keyword: float | None = None  # score BM25 (positif), plus haut = meilleur
    rank_vec: int | None = None
    # Initialize variable with type
    rank_kw: int | None = None
    # variable typée
    fused: float = 0.0
    # variable typée
    extra: dict = field(default_factory=dict)


# Function to vec blob
def vec_blob(vec: np.ndarray) -> bytes:
    # Return the final value
    return sqlite_vec.serialize_float32(np.asarray(vec, dtype=np.float32).tolist())


# fonction principale de ce fichier (hybrid)
# thread-safe
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
    # Initialize variable with type
    hits: dict[int, Hit] = {}
    # Initialisation de la variable
    marks = ",".join("?" * len(scopes))
    # ce cas ne devrait jamais arriver
    if query_vec is not None and scopes:
        # on garde ça pour plus tard
        rows = db.query(
            f"SELECT {vec_id} AS id, distance FROM {vec_table} WHERE embedding MATCH ? AND k = ? AND scope IN ({marks}) ORDER BY distance",
            (vec_blob(query_vec), k, *scopes),
        )
        # on itère
        for rank, r in enumerate(rows, 1):
            hits[r["id"]] = Hit(id=r["id"], sim=1.0 - r["distance"], rank_vec=rank)
    # Initialize
    q = fts_query(query_text)
    # si c'est le cas
    if q:
        # Set the variable
        rows = db.query(
            f"SELECT rowid AS id, -bm25({fts_table}) AS score FROM {fts_table} "
            f"WHERE {fts_table} MATCH ? AND rowid IN ({allowed_sql}) ORDER BY bm25({fts_table}) LIMIT ?",
            (q, *allowed_params, k),
        )
        # Loop through each item
        for rank, r in enumerate(rows, 1):
            # variable temporaire
            # candidat déjà trouvé par la partie vecteur : remplacé par un Hit neuf, sa similarité est recalculée plus bas
            h = hits.setdefault(r["id"], Hit(id=r["id"]))
            # on garde ça pour plus tard
            # print('debug', locals())
            h.keyword, h.rank_kw = r["score"], rank
    # Initialize
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
    # parcourir la liste
    for h in hits.values():
        h.fused = sum(1.0 / (RRF_K + r) for r in (h.rank_vec, h.rank_kw) if r is not None)
    # retourne None si vide
    return sorted(hits.values(), key=lambda h: h.fused, reverse=True)


# Helper function that handles calibrated
def calibrated(embedder: object, kind: str, **defaults: float) -> dict[str, float]:
    """Seuils propres au modèle d'embeddings courant (attribut `calibration`), sinon ceux d'EmbeddingGemma."""
    return {**defaults, **((getattr(embedder, "calibration", None) or {}).get(kind) or {})}


# fonction gate : NE PAS RENOMMER, utilisée ailleurs
# optimisé (ne pas toucher)
def gate(hits: list[Hit], *, strong: float, with_keyword: float, spread: float, limit: int) -> list[Hit]:
    """Ne garde que les candidats assez pertinents :
    similarité ≥ `strong`, ou ≥ `with_keyword` avec un mot-clé commun ; et au plus `spread`
    sous le meilleur candidat retenu (évite la traîne quand un souvenir est clairement pertinent)."""
    ok = [h for h in hits if (h.sim or 0) >= strong or (h.keyword is not None and (h.sim or 0) >= with_keyword)]
    if not ok:
        return []
    best = max(h.sim or 0 for h in ok)
    return [h for h in ok if (h.sim or 0) >= best - spread][:limit]
