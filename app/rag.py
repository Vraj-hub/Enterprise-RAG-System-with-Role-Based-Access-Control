import json
import re
import time

from fastapi import HTTPException

from . import audit, llm, rbac, retrieval, vectorstore
from .config import HISTORY_TURNS
from .db import db

NO_ACCESS_MSG = "I don't have enough information in the documents you can access."
INJECTION = re.compile(
    r"ignore (all |any |the |your )*(previous |prior |above )*(instructions|rules)|reveal .{0,30}system prompt|"
    r"disregard .{0,30}(rules|instructions)|you are now|act as (an? )?(admin|root)", re.I)


def _snippet(text: str, n: int = 260) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + "…"


def _conversation(user: dict, conversation_id: int | None, question: str) -> tuple[int, list[str]]:
    with db() as conn:
        if conversation_id is None:
            cur = conn.execute("INSERT INTO conversations (user_id, title) VALUES (?,?)", (user["id"], question[:70]))
            return cur.lastrowid, []
        row = conn.execute("SELECT id FROM conversations WHERE id=? AND user_id=?", (conversation_id, user["id"])).fetchone()
        if row is None:  # same answer for "missing" and "someone else's": no ID probing
            raise HTTPException(404, "Conversation not found")
        prior = conn.execute(
            "SELECT content FROM messages WHERE conversation_id=? AND role='user' ORDER BY id DESC LIMIT ?",
            (conversation_id, HISTORY_TURNS)).fetchall()
    return conversation_id, [r["content"] for r in reversed(prior)]


def answer_query(question: str, user: dict, conversation_id: int | None = None) -> dict:
    t0 = time.perf_counter()
    conv_id, prior = _conversation(user, conversation_id, question)
    # Short follow-ups ("and for managers?") borrow the previous question for retrieval only.
    search_q = f"{prior[-1]} {question}" if prior and len(question.split()) < 6 else question
    injection_q = bool(INJECTION.search(question))

    hits = retrieval.hybrid_search(search_q, user)
    blocked = vectorstore.count_blocked_candidates(search_q, user)
    injected_chunks = sum(1 for h in hits if INJECTION.search(h["text"]))

    if not hits:
        answer, engine, sources, status = NO_ACCESS_MSG, "none", [], "no_evidence"
    else:
        answer, engine = llm.generate(question, hits, prior)
        valid = set(range(1, len(hits) + 1))
        used = sorted({int(n) for n in re.findall(r"\[(\d{1,2})\]", answer)} & valid)
        answer = re.sub(r"\[(\d{1,2})\]", lambda m: m.group(0) if int(m.group(1)) in valid else "", answer)  # drop fake citations
        if engine == "ollama-unavailable":
            status, shown = "model_unavailable", range(1, len(hits) + 1)
        elif answer.startswith(NO_ACCESS_MSG[:30]):
            status, shown = "no_evidence", []
        elif used:
            status, shown = "verified", used
        else:
            status, shown = "uncited", range(1, len(hits) + 1)
        sources = [{
            "n": n, "doc_id": hits[n - 1]["doc_id"], "chunk_index": hits[n - 1]["chunk_index"],
            "filename": hits[n - 1]["filename"], "sensitivity": hits[n - 1]["sensitivity"],
            "page": hits[n - 1].get("page") or None, "snippet": _snippet(hits[n - 1]["text"]),
            "match": "+".join(hits[n - 1]["via"]),
        } for n in shown]

    latency = int((time.perf_counter() - t0) * 1000)
    with db() as conn:
        conn.execute("INSERT INTO messages (conversation_id, role, content) VALUES (?,?,?)", (conv_id, "user", question))
        cur = conn.execute(
            "INSERT INTO messages (conversation_id, role, content, sources, citation_status, latency_ms) VALUES (?,?,?,?,?,?)",
            (conv_id, "assistant", answer, json.dumps(sources), status, latency))
        msg_id = cur.lastrowid
        conn.execute("UPDATE conversations SET updated_at=datetime('now') WHERE id=?", (conv_id,))
    flags = [f for f, on in (("injection_in_question", injection_q), (f"injection_in_{injected_chunks}_chunks", injected_chunks)) if on]
    audit.log(
        action="query", decision="allowed" if hits else "no_context", user=user, query=question,
        sources=[{"doc_id": s["doc_id"], "filename": s["filename"]} for s in sources],
        blocked_candidates=blocked, detail=";".join([engine, status, *flags]), latency_ms=latency)
    return {"conversation_id": conv_id, "message_id": msg_id, "answer": answer, "sources": sources,
            "citation_status": status, "engine": engine, "latency_ms": latency}
