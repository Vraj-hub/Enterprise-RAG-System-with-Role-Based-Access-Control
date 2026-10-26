"""Embedding backends: Ollama semantic embeddings, Sentence Transformers, or test hashing."""

import hashlib
import re
from functools import lru_cache

import httpx
import numpy as np

from .config import EMBEDDER, OLLAMA_EMBED_MODEL, OLLAMA_URL, ST_MODEL

DIM = 384
_TOKEN = re.compile(r"[a-z0-9]+")


class HashEmbedder:
    """Lightweight test fallback; not recommended for semantic search."""

    dim = DIM

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vec = np.zeros(DIM, dtype=np.float32)
            for token in _TOKEN.findall(text.lower()):
                h = int(hashlib.md5(token.encode()).hexdigest(), 16)
                vec[h % DIM] += 1.0
            norm = np.linalg.norm(vec)
            out.append((vec / norm if norm else vec).tolist())
        return out


class OllamaEmbedder:
    """Create semantic vectors through Ollama's /api/embed endpoint."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        try:
            response = httpx.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": OLLAMA_EMBED_MODEL, "input": texts},
                timeout=120.0,
            )
            response.raise_for_status()
            vectors = response.json()["embeddings"]
        except Exception as exc:
            raise RuntimeError(
                f"Ollama embeddings failed for model {OLLAMA_EMBED_MODEL!r}. "
                f"Check that Ollama is running and the model is installed. Details: {exc}"
            ) from exc

        if len(vectors) != len(texts):
            raise RuntimeError("Ollama returned an unexpected number of embeddings.")
        if vectors and (not vectors[0] or any(len(v) != len(vectors[0]) for v in vectors)):
            raise RuntimeError("Ollama returned invalid or inconsistent embedding dimensions.")
        if any(not all(np.isfinite(x) for x in v) for v in vectors):
            raise RuntimeError("Ollama returned a non-finite embedding value.")
        return vectors


class STEmbedder:
    """Optional Sentence Transformers backend."""

    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(ST_MODEL)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()


@lru_cache(maxsize=1)
def get_embedder():
    if EMBEDDER == "ollama":
        return OllamaEmbedder()
    if EMBEDDER == "st":
        return STEmbedder()
    if EMBEDDER == "hash":
        return HashEmbedder()
    raise ValueError(f"Unknown EMBEDDER={EMBEDDER!r}. Use ollama, st, or hash.")
