from . import audit, llm, vectorstore

NO_ACCESS_MSG = "I don't have enough information in the documents you can access."


def answer_query(question: str, user: dict) -> dict:
    hits = vectorstore.search(question, user)
    blocked = vectorstore.count_blocked_candidates(question, user)

    if not hits:
        audit.log(
            action="query", decision="no_context", user=user, query=question,
            blocked_candidates=blocked,
        )
        return {"answer": NO_ACCESS_MSG, "sources": [], "engine": "none"}

    answer, engine = llm.generate(question, hits)
    sources = sorted({(h["doc_id"], h["filename"], h["sensitivity"]) for h in hits})
    audit.log(
        action="query", decision="allowed", user=user, query=question,
        sources=[{"doc_id": s[0], "filename": s[1]} for s in sources],
        blocked_candidates=blocked, detail=engine,
    )
    return {
        "answer": answer,
        "sources": [{"doc_id": s[0], "filename": s[1], "sensitivity": s[2]} for s in sources],
        "engine": engine,
    }
