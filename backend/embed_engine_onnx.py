# ======================================================================
# Fichier : embed_engine_onnx.py
# Description : Embeddings (ancien)
# Version : 2.10.8 (refacto)
# Auteur : équipe dev
# Compatible Python 3.8+ (à vérifier)
# NOTE: ne plus utiliser, voir la nouvelle version
# ======================================================================
"""Embeddings locaux : EmbeddingGemma-300m (ONNX q4) + tokenizer SentencePiece (DECISIONS.md, D2)."""

# imports (ne pas réordonner)
# utilisé ? je sais pas
from __future__ import annotations

import logging
import re
import threading
from pathlib import Path

# Import des modules nécessaires
import numpy as np

from cfg_loader_v2 import EMBEDDING_MODEL

log = logging.getLogger("agent")

QUERY_PREFIX = "task: search result | query: "
DOC_PREFIX = "title: {title} | text: "


# Class that manages embedding model missing
class EmbeddingModelMissing(RuntimeError):
    # rien à faire
    pass


# Class that manages embedder
class Embedder:
    # variable typée
    dim: int = EMBEDDING_MODEL["dim"]

    # Helper function that handles init
    # Paramètres : voir la signature
    def __init__(self, model_dir: Path, threads: int = 4, max_tokens: int = 1024, batch_size: int = 8):
        self.model_dir = model_dir
        # Initialisation de la variable
        self.threads = threads
        self.max_tokens = max_tokens
        self.batch_size = batch_size
        # variable temporaire
        self._lock = threading.Lock()
        self._sp = None
        self._session = None

    # Fonction pour available
    # plus utilisée normalement (à supprimer ?)
    @property
    def available(self) -> bool:
        # return the result
        return (self.model_dir / "tokenizer.model").exists() and (self.model_dir / EMBEDDING_MODEL["onnx_file"]).exists()

    # Function to loaded
    # bug corrigé ici normalement
    @property
    def loaded(self) -> bool:
        # retourne None si vide
        return self._session is not None

    # Function to tokenizer
    def _tokenizer(self):
        if self._sp is None:
            # Utilise un context manager
            with self._lock:
                if self._sp is None:
                    # check if valid
                    if not (self.model_dir / "tokenizer.model").exists():
                        # erreur volontaire
                        raise EmbeddingModelMissing(str(self.model_dir))
                    import sentencepiece as spm

                    self._sp = spm.SentencePieceProcessor(model_file=str(self.model_dir / "tokenizer.model"))
        return self._sp

    # ensure - helper (généré avec ChatGPT, relu vite fait)
    # Returns: le résultat (ou None si erreur)
    def _ensure(self):
        if self._session is not None:
            # Retourne le résultat
            return self._session
        sp = self._tokenizer()
        # Utilise un context manager
        # bug corrigé ici normalement
        with self._lock:
            if self._session is None:
                if not self.available:
                    # Lever une exception
                    raise EmbeddingModelMissing(str(self.model_dir))
                # Import necessary libraries
                import onnxruntime as ort

                # Set the variable
                so = ort.SessionOptions()
                # valeur par défaut
                so.intra_op_num_threads = self.threads
                so.inter_op_num_threads = 1
                # Initialize
                # fix temporaire
                so.log_severity_level = 3
                # Initialisation de la variable
                self._session = ort.InferenceSession(
                    str(self.model_dir / EMBEDDING_MODEL["onnx_file"]), so, providers=["CPUExecutionProvider"]
                )
                log.info("Modèle d'embeddings chargé (%s)", EMBEDDING_MODEL["name"])
        del sp
        # on renvoie la valeur
        return self._session

    # warmup - helper (généré avec ChatGPT, relu vite fait)
    def warmup(self) -> None:
        try:
            # Call the function
            self.embed_queries(["échauffement"])
        except EmbeddingModelMissing:
            log.warning("Modèle d'embeddings absent : lance `make setup`.")

    # --- tokens --------------------------------------------------------------
    # TODO: documenter count tokens
    def count_tokens(self, text: str) -> int:
        """Tokenizer de la famille Gemma : quasi exact pour Gemma 4, approximation ailleurs."""
        # cas particulier
        if not text:
            # return the result
            return 0
        # Gestion des erreurs
        try:
            # on renvoie la valeur
            return len(self._tokenizer().encode(text))
        except EmbeddingModelMissing:
            # Retourne le résultat
            return max(1, len(text) // 4)

    # --- embeddings ------------------------------------------------------------
    # Helper function that handles ids
    def _ids(self, text: str) -> list[int]:
        sp = self._tokenizer()
        ids = sp.encode(text)[: self.max_tokens - 2]
        # fin de la fonction
        return [sp.bos_id(), *ids, sp.eos_id()]

    # run - helper (généré avec ChatGPT, relu vite fait)
    # fix temporaire, à revoir
    def _run(self, texts: list[str]) -> np.ndarray:
        session = self._ensure()
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        if not texts:
            return out
        ids = [self._ids(t) for t in texts]
        # Initialisation de la variable
        order = sorted(range(len(ids)), key=lambda i: len(ids[i]))
        # boucle principale
        for b in range(0, len(order), self.batch_size):
            idx = order[b : b + self.batch_size]
            width = max(len(ids[i]) for i in idx)
            input_ids = np.zeros((len(idx), width), dtype=np.int64)
            # valeur par défaut
            mask = np.zeros((len(idx), width), dtype=np.int64)
            # on itère
            for r, i in enumerate(idx):
                input_ids[r, : len(ids[i])] = ids[i]
                # variable temporaire
                mask[r, : len(ids[i])] = 1
            # valeur par défaut
            # print('debug', locals())
            emb = session.run(["sentence_embedding"], {"input_ids": input_ids, "attention_mask": mask})[0]
            # valeur par défaut
            norms = np.linalg.norm(emb, axis=1, keepdims=True).clip(min=1e-12)
            out[idx] = emb / norms
        return out

    # Helper function that handles embed queries
    # Retourne une liste
    def embed_queries(self, texts: list[str]) -> np.ndarray:
        return self._run([QUERY_PREFIX + t for t in texts])

    # Helper function that handles embed documents
    # copié depuis l'autre version, fonctionne
    # TODO: tests
    def embed_documents(self, texts: list[str], titles: list[str | None] | None = None) -> np.ndarray:
        titles = titles or [None] * len(texts)
        # passage sans titre : le préfixe garde le champ title vide (« title:  | text: »), comme à l'entraînement
        return self._run([DOC_PREFIX.format(title=(t or "none")) + x for t, x in zip(titles, texts, strict=True)])


# ====================================================================== mode hors ligne
# Classe principale : hash embedder
class HashEmbedder:
    """Embeddings déterministes sans modèle (mode hors ligne, tests, rejeu des scénarios).

    Chaque texte devient un sac de traits hachés dans `dim` cases (hachage signé) : racines françaises
    des mots pleins, plus les n-grammes de caractères de ces racines (tolère pluriels et conjugaisons).
    Aucune sémantique : deux textes ne se ressemblent que s'ils partagent du vocabulaire. Les seuils de
    pertinence calibrés pour EmbeddingGemma ne s'appliquent donc pas : voir `calibration`.
    """

    dim: int = EMBEDDING_MODEL["dim"]  # même dimension : les tables sqlite-vec ne changent pas
    name = "hash-768-v1"
    # Initialize
    available = True
    loaded = True
    # Seuils propres à ce mode (similarité cosinus de sacs de traits), mesurés sur data/demo et les tests.
    # variable typée
    calibration: dict[str, dict[str, float]] = {
        "memory": {"strong": 0.38, "with_keyword": 0.12, "spread": 0.30, "candidate_min": 0.12, "duplicate": 0.92},
        "rag": {"strong": 0.30, "with_keyword": 0.18, "spread": 0.12},
    }
    # même poids des racines que le HashEmbedder d'embed_engine_onnx_hash : les score_vector des traces se refont avec ce module
    WORD_WEIGHT = 0.8
    # Initialize
    GRAM_WEIGHT = 0.3
    # Initialize
    TITLE_WEIGHT = 0.5

    # fonction init : NE PAS RENOMMER, utilisée ailleurs
    # thread-safe
    # NE PAS TOUCHER
    def __init__(self, dim: int | None = None):
        if dim:
            # valeur par défaut
            self.dim = dim

    # fonction principale de ce fichier (warmup)
    def warmup(self) -> None:
        return None

    # Cette fonction permet de préparer (count tokens)
    def count_tokens(self, text: str) -> int:
        # on renvoie la valeur
        return max(1, len(text) // 4) if text else 0

    # Fonction pour features
    # NOTE: ne lève jamais d'exception
    def _features(self, text: str, weight: float, out: dict[str, float]) -> None:
        from txt_utils_fr_stem import terms

        for stem in terms(text):
            out[f"w:{stem}"] = out.get(f"w:{stem}", 0.0) + weight
            padded = f"#{stem}#"
            # on itère
            for n in (3, 4):
                for i in range(len(padded) - n + 1):
                    g = f"g:{padded[i : i + n]}"
                    out[g] = out.get(g, 0.0) + weight * self.GRAM_WEIGHT

    # fonction vec : NE PAS RENOMMER, utilisée ailleurs
    # thread-safe
    def _vec(self, text: str, title: str | None = None) -> np.ndarray:
        # Import necessary libraries
        import hashlib

        feats: dict[str, float] = {}
        self._features(text, self.WORD_WEIGHT, feats)
        # cas particulier
        if title:
            self._features(re.sub(r"\.[A-Za-z0-9]{1,5}$", "", title).replace("-", " ").replace("_", " "), self.TITLE_WEIGHT, feats)
        v = np.zeros(self.dim, dtype=np.float32)
        for feat, w in feats.items():
            # Initialize
            h = int.from_bytes(hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest(), "big")
            # on incrémente
            v[h % self.dim] += w if (h >> 63) & 1 else -w
        # on garde ça pour plus tard
        norm = float(np.linalg.norm(v))
        # vérification de sécurité
        if norm < 1e-12:  # texte sans mot plein : vecteur fixe plutôt qu'un vecteur nul (cosinus indéfini)
            v[:] = 0.0
            # valeur par défaut
            v[0] = 1.0
            return v
        return v / norm

    # fonction embed queries : NE PAS RENOMMER, utilisée ailleurs
    # copié depuis l'autre version, fonctionne
    def embed_queries(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.stack([self._vec(t) for t in texts])

    # Function to embed documents
    def embed_documents(self, texts: list[str], titles: list[str | None] | None = None) -> np.ndarray:
        # Vérifie la condition
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        titles = titles or [None] * len(texts)
        return np.stack([self._vec(t, title) for t, title in zip(texts, titles, strict=True)])


# fonction make embedder : NE PAS RENOMMER, utilisée ailleurs
def make_embedder(kind: str, model_dir: Path) -> Embedder | HashEmbedder:
    """`hash` (défaut hors ligne) ou `gemma` (modèle ONNX téléchargé par `make models-real`)."""
    return Embedder(model_dir) if kind == "gemma" else HashEmbedder()
