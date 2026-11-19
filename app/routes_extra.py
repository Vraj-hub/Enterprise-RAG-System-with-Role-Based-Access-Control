"""Conversations, citation preview, feedback, analytics and health."""
import json
from collections import Counter, defaultdict

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import rbac, vectorstore
from .config import OLLAMA_EMBED_MODEL, OLLAMA_MODEL, OLLAMA_URL
from .db import db, row_to_doc
from .security import get_current_user, require_roles

router = APIRouter(prefix="/api")


def _doc_for(user: dict, doc_id: int) -> dict:
    """Return the document only if the user may read it; otherwise 404 (never reveal existence)."""
    with db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if row is None or not rbac.can_access(user, row_to_doc(row)):
        raise HTTPException(404, "Document not found")
    return row_to_doc(row)


@router.get("/conversations")
def list_conversations(user: dict = Depends(get_current_user)):
    with db() as conn:
        rows = conn.execute("SELECT id, title, updated_at FROM conversations WHERE user_id=? ORDER BY updated_at DESC, id DESC LIMIT 50", (user["id"],)).fetchall()
    return [dict(r) for r in rows]


@router.get("/conversations/{cid}")
def get_conversation(cid: int, user: dict = Depends(get_current_user)):
    with db() as conn:
        conv = conn.execute("SELECT id, title FROM conversations WHERE id=? AND user_id=?", (cid, user["id"])).fetchone()
        if conv is None:
            raise HTTPException(404, "Conversation not found")
        msgs = conn.execute("SELECT id, role, content, sources, citation_status, latency_ms, created_at FROM messages WHERE conversation_id=? ORDER BY id", (cid,)).fetchall()
        fb = {r["message_id"]: r["rating"] for r in conn.execute("SELECT message_id, rating FROM feedback WHERE user_id=?", (user["id"],))}
    out = []
    for m in msgs:
        d = dict(m)
        sources = json.loads(d["sources"] or "[]")
        for s in sources:  # re-check access NOW: revoked/deleted documents are redacted from old chats
            try:
                _doc_for(user, s["doc_id"])
            except HTTPException:
                s.clear(); s.update({"n": s.get("n"), "redacted": True, "filename": "Source no longer available to you"})
        d["sources"], d["feedback"] = sources, fb.get(d["id"])
        out.append(d)
    return {"id": conv["id"], "title": conv["title"], "messages": out}


@router.delete("/conversations/{cid}")
def delete_conversation(cid: int, user: dict = Depends(get_current_user)):
    with db() as conn:
        cur = conn.execute("DELETE FROM conversations WHERE id=? AND user_id=?", (cid, user["id"]))
        if cur.rowcount == 0:
            raise HTTPException(404, "Conversation not found")
    return {"deleted": cid}


class FeedbackIn(BaseModel):
    rating: int


@router.post("/messages/{mid}/feedback")
def feedback(mid: int, body: FeedbackIn, user: dict = Depends(get_current_user)):
    if body.rating not in (-1, 1):
        raise HTTPException(422, "rating must be 1 or -1")
    with db() as conn:
        own = conn.execute("SELECT 1 FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE m.id=? AND c.user_id=? AND m.role='assistant'", (mid, user["id"])).fetchone()
        if own is None:
            raise HTTPException(404, "Message not found")
        conn.execute("INSERT OR REPLACE INTO feedback (message_id, user_id, rating) VALUES (?,?,?)", (mid, user["id"], body.rating))
    return {"ok": True}


@router.get("/documents/{doc_id}/chunks/{chunk_index}")
def chunk_preview(doc_id: int, chunk_index: int, user: dict = Depends(get_current_user)):
    doc = _doc_for(user, doc_id)
    with db() as conn:
        rows = conn.execute("SELECT chunk_index, page, text FROM chunks_fts WHERE doc_id=? AND chunk_index BETWEEN ? AND ? ORDER BY chunk_index", (doc_id, chunk_index - 1, chunk_index + 1)).fetchall()
    if not any(r["chunk_index"] == chunk_index for r in rows):
        raise HTTPException(404, "Passage not found")
    return {"filename": doc["filename"], "sensitivity": doc["sensitivity"], "focus": chunk_index,
            "passages": [{"chunk_index": r["chunk_index"], "page": r["page"] or None, "text": r["text"]} for r in rows]}


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/admin/health")
def admin_health(user: dict = Depends(require_roles("admin"))):
    checks = {}
    try:
        with db() as conn:
            conn.execute("SELECT 1")
        checks["database"] = {"ok": True}
    except Exception as exc:
        checks["database"] = {"ok": False, "error": str(exc)[:120]}
    try:
        checks["vector_index"] = {"ok": True, "chunks": vectorstore._collection.count()}
    except Exception as exc:
        checks["vector_index"] = {"ok": False, "error": str(exc)[:120]}
    try:
        names = {m["name"] for m in httpx.get(f"{OLLAMA_URL}/api/tags", timeout=2.5).json().get("models", [])}
        checks["ollama"] = {"ok": True, "chat_model": OLLAMA_MODEL, "chat_model_installed": OLLAMA_MODEL in names,
                            "embed_model": OLLAMA_EMBED_MODEL, "embed_model_installed": OLLAMA_EMBED_MODEL in names}
    except Exception:
        checks["ollama"] = {"ok": False, "error": "Ollama is not reachable at " + OLLAMA_URL}
    return checks


@router.get("/admin/stats")
def stats(user: dict = Depends(require_roles("admin"))):
    with db() as conn:
        logs = conn.execute("SELECT ts, action, decision, detail, sources, blocked_candidates, latency_ms FROM audit_logs ORDER BY id DESC LIMIT 5000").fetchall()
        n_docs = conn.execute("SELECT COUNT(*) c FROM documents").fetchone()["c"]
        n_users = conn.execute("SELECT COUNT(*) c FROM users WHERE is_active=1").fetchone()["c"]
        by_sens = {r["sensitivity"]: r["c"] for r in conn.execute("SELECT sensitivity, COUNT(*) c FROM documents GROUP BY sensitivity")}
        fb = {r["rating"]: r["c"] for r in conn.execute("SELECT rating, COUNT(*) c FROM feedback GROUP BY rating")}
    queries = [l for l in logs if l["action"] == "query"]
    lat = sorted(l["latency_ms"] for l in queries if l["latency_ms"])
    per_day: dict[str, Counter] = defaultdict(Counter)
    cited: Counter = Counter()
    for l in queries:
        per_day[l["ts"][:10]][l["decision"]] += 1
        for s in json.loads(l["sources"] or "[]"):
            cited[s["filename"]] += 1
    return {
        "documents": n_docs, "active_users": n_users, "docs_by_sensitivity": by_sens,
        "queries": len(queries), "unanswered": sum(1 for l in queries if l["decision"] == "no_context"),
        "blocked_candidates": sum(l["blocked_candidates"] or 0 for l in queries),
        "failed_logins": sum(1 for l in logs if l["action"] == "login_failed"),
        "injection_flags": sum(1 for l in queries if "injection" in (l["detail"] or "")),
        "latency_ms": {"p50": lat[len(lat) // 2] if lat else None, "p95": lat[int(len(lat) * 0.95) - 1] if len(lat) >= 2 else (lat[0] if lat else None)},
        "per_day": [{"day": d, "answered": c["allowed"], "unanswered": c["no_context"]} for d, c in sorted(per_day.items())[-14:]],
        "top_sources": cited.most_common(5),
        "feedback": {"up": fb.get(1, 0), "down": fb.get(-1, 0)},
    }
