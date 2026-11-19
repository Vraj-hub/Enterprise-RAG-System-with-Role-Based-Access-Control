"""Hybrid retrieval: vector search + BM25 keyword search, fused with Reciprocal Rank Fusion.

SECURITY: both retrievers see only documents the user may read. Vector search filters inside
Chroma; keyword search is restricted to the authorized document-id list computed by rbac.can_access.
"""
import re

from . import rbac, vectorstore
from .config import CANDIDATES, MIN_RELEVANCE, TOP_K
from .db import db, row_to_doc

STOP = set("the and for are but not you all can had her was one our out has have how what when where who why "
           "which does did this that with from they will would there their about into than then them these "
           "those been being your more some any may our its".split())
RRF_K = 60


def terms(query: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2 and t not in STOP]


def authorized_doc_ids(user: dict) -> list[int]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM documents").fetchall()
    return [d["id"] for d in map(row_to_doc, rows) if rbac.can_access(user, d)]


def keyword_search(query: str, user: dict, k: int) -> list[dict]:
    ts, ids = terms(query), authorized_doc_ids(user)
    if not ts or not ids:
        return []
    match = " OR ".join(f'"{t}"' for t in ts)  # quoted tokens: no FTS operator injection
    marks = ",".join("?" * len(ids))
    with db() as conn:
        rows = conn.execute(
            f"""SELECT chunks_fts.doc_id, chunks_fts.chunk_index, chunks_fts.page, chunks_fts.text,
                       d.filename, d.sensitivity, d.department
                FROM chunks_fts JOIN documents d ON d.id = chunks_fts.doc_id
                WHERE chunks_fts MATCH ? AND chunks_fts.doc_id IN ({marks})
                ORDER BY bm25(chunks_fts) LIMIT ?""",
            (match, *ids, k),
        ).fetchall()
    return [dict(r) for r in rows]


def hybrid_search(query: str, user: dict, k: int = TOP_K) -> list[dict]:
    vec = vectorstore.search(query, user, k=CANDIDATES)
    kw = keyword_search(query, user, CANDIDATES)
    fused: dict[tuple, dict] = {}
    for rank, h in enumerate(vec):
        e = fused.setdefault((h["doc_id"], h["chunk_index"]), {**h, "via": [], "rrf": 0.0})
        e["via"].append("vector"); e["rrf"] += 1 / (RRF_K + rank)
    for rank, h in enumerate(kw):
        key = (h["doc_id"], h["chunk_index"])
        e = fused.setdefault(key, {**h, "score": None, "via": [], "rrf": 0.0})
        e["via"].append("keyword"); e["rrf"] += 1 / (RRF_K + rank)
    # Relevance gate: a chunk needs a keyword match OR a vector similarity above the threshold.
    kept = [e for e in fused.values() if "keyword" in e["via"] or (e["score"] or 0) >= MIN_RELEVANCE]
    kept.sort(key=lambda e: e["rrf"], reverse=True)
    # De-duplicate near-identical chunks (same document, same opening text)
    seen, out = set(), []
    for e in kept:
        sig = (e["doc_id"], e["text"][:80])
        if sig not in seen:
            seen.add(sig); out.append(e)
    return out[:k]
