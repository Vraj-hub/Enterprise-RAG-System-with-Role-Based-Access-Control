import json

from .db import db


def log(
    *,
    action: str,
    decision: str,
    user: dict | None = None,
    username: str | None = None,
    query: str | None = None,
    sources: list | None = None,
    blocked_candidates: int = 0,
    detail: str | None = None,
    latency_ms: int | None = None,
) -> None:
    with db() as conn:
        conn.execute(
            """INSERT INTO audit_logs
               (user_id, username, role, action, query, sources, blocked_candidates, decision, detail, latency_ms)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                user["id"] if user else None,
                user["username"] if user else username,
                user["role"] if user else None,
                action,
                query,
                json.dumps(sources or []),
                blocked_candidates,
                decision,
                detail,
                latency_ms,
            ),
        )
