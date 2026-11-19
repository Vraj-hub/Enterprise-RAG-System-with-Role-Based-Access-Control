"""Embedding backends: Ollama semantic embeddings, Sentence Transformers, or test hashing."""

import hashlib
import re
from functools import lru_cache

import httpx
import numpy as np

from .config import EMBEDDER, OLLAMA_EMBED_CPU_ONLY, OLLAMA_EMBED_MODEL, OLLAMA_URL, ST_MODEL

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

        response = None
        payload = {"model": OLLAMA_EMBED_MODEL, "input": texts}
        if OLLAMA_EMBED_CPU_ONLY:
            payload["options"] = {"num_gpu": 0}  # keep the embedding runner off the GPU
        try:
            response = httpx.post(
                f"{OLLAMA_URL}/api/embed",
                json=payload,
                timeout=120.0,
            )
            response.raise_for_status()
            vectors = response.json()["embeddings"]
        except Exception as exc:
            detail = str(exc)
            if response is not None:
                try:
                    body = response.json()
                    if isinstance(body, dict):
                        detail = str(body.get("error") or body.get("message") or body)
                except Exception:
                    pass
                if not detail or detail == str(exc):
                    detail = response.text.strip() or str(exc)
            detail = detail.strip() if isinstance(detail, str) else str(detail)
            hint = ""
            detail_lower = detail.lower()
            if "terminated" in detail_lower or "0xc0000005" in detail_lower:
                hint = (" Ollama's model runner crashed (not an app bug): update Ollama, re-pull the model, "
                        "or set OLLAMA_EMBED_CPU_ONLY=1 in .env and restart the app.")
            raise RuntimeError(
                f"Ollama embeddings failed for model {OLLAMA_EMBED_MODEL!r}. "
                f"Check that Ollama is running and the model is installed.{hint} Details: {detail}"
            ) from exc

        if len(vectors) != len(texts):
            raise RuntimeError("Ollama returned an unexpected number of embeddings.")
        normalized = []
        for vec in vectors:
            if not isinstance(vec, (list, tuple)) or not vec:
                raise RuntimeError("Ollama returned invalid or inconsistent embedding dimensions.")
            converted = []
            for x in vec:
                try:
                    num = float(x)
                except (TypeError, ValueError) as exc:
                    raise RuntimeError("Ollama returned a non-finite embedding value.") from exc
                if not np.isfinite(num):
                    raise RuntimeError("Ollama returned a non-finite embedding value.")
                converted.append(num)
            normalized.append(converted)
        first_len = len(normalized[0])
        if any(len(v) != first_len for v in normalized[1:]):
            raise RuntimeError("Ollama returned invalid or inconsistent embedding dimensions.")
        return normalized


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