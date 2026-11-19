import chromadb

from . import rbac
from .config import CHROMA_PATH, TOP_K
from .embeddings import get_embedder

_client = chromadb.PersistentClient(path=CHROMA_PATH)
_collection = _client.get_or_create_collection("enterprise_docs", metadata={"hnsw:space": "cosine"})


def add_chunks(doc: dict, chunks: list[tuple[str, int]]) -> int:
    """Each chunk carries the full access metadata. Chroma metadata must be scalar,
    so allowed_roles is stored as one boolean flag per role."""
    if not chunks:
        return 0
    meta_base = {
        "doc_id": doc["id"],
        "filename": doc["filename"],
        "owner_id": doc["owner_id"],
        "department": doc["department"],
        "sensitivity": doc["sensitivity"],
        "sensitivity_rank": rbac.sensitivity_rank(doc["sensitivity"]),
        **{f"role_{r}": (r in doc["allowed_roles"]) for r in rbac.ROLES},
    }
    _collection.add(
        ids=[f"{doc['id']}-{i}" for i in range(len(chunks))],
        documents=[c[0] for c in chunks],
        embeddings=get_embedder().embed([c[0] for c in chunks]),
        metadatas=[{**meta_base, "chunk_index": i, "page": c[1]} for i, c in enumerate(chunks)],
    )
    return len(chunks)


def delete_document(doc_id: int) -> None:
    _collection.delete(where={"doc_id": doc_id})


def search(question: str, user: dict, k: int = TOP_K) -> list[dict]:
    """Authorized search: the RBAC filter is part of the query itself."""
    res = _collection.query(
        query_embeddings=get_embedder().embed([question]),
        n_results=k,
        where=rbac.chroma_filter(user),
    )
    return _unpack(res)


def count_blocked_candidates(question: str, user: dict, k: int = TOP_K) -> int:
    """Audit only: of the top-k matches over ALL data, how many is this user NOT allowed to see?
    The result is logged, never returned to the user or sent to the LLM."""
    res = _collection.query(
        query_embeddings=get_embedder().embed([question]),
        n_results=k,
        include=["metadatas", "distances"],
    )
    blocked = 0
    for m in res["metadatas"][0]:
        doc = {
            "allowed_roles": [r for r in rbac.ROLES if m.get(f"role_{r}")],
            "sensitivity": m["sensitivity"],
            "department": m["department"],
        }
        if not rbac.can_access(user, doc):
            blocked += 1
    return blocked


def _unpack(res) -> list[dict]:
    hits = []
    for text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        hits.append(
            {
                "text": text,
                "doc_id": meta["doc_id"],
                "chunk_index": meta.get("chunk_index", 0),
                "page": meta.get("page", 0),
                "filename": meta["filename"],
                "sensitivity": meta["sensitivity"],
                "department": meta["department"],
                "score": round(1 - dist, 3),
            }
        )
    return hits
