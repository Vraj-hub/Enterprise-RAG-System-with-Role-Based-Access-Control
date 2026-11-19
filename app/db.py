import json
import sqlite3
from contextlib import contextmanager

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin','manager','employee')),
    department TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    email TEXT,
    email_verified INTEGER NOT NULL DEFAULT 0,
    google_sub TEXT
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    owner_id INTEGER NOT NULL REFERENCES users(id),
    department TEXT NOT NULL,
    sensitivity TEXT NOT NULL CHECK (sensitivity IN ('public','internal','confidential','restricted')),
    allowed_roles TEXT NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL DEFAULT (datetime('now')),
    user_id INTEGER,
    username TEXT,
    role TEXT,
    action TEXT NOT NULL,
    query TEXT,
    sources TEXT,
    blocked_candidates INTEGER DEFAULT 0,
    decision TEXT NOT NULL,
    detail TEXT,
    latency_ms INTEGER
);
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user','assistant')),
    content TEXT NOT NULL,
    sources TEXT,
    citation_status TEXT,
    latency_ms INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS feedback (
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL,
    rating INTEGER NOT NULL CHECK (rating IN (-1,1)),
    PRIMARY KEY (message_id, user_id)
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, doc_id UNINDEXED, chunk_index UNINDEXED, page UNINDEXED, tokenize='porter unicode61'
);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript(SCHEMA)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(audit_logs)")}
        if "latency_ms" not in cols:  # migrate databases created by the first version
            conn.execute("ALTER TABLE audit_logs ADD COLUMN latency_ms INTEGER")
        ucols = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
        for col, ddl in (("email", "TEXT"), ("email_verified", "INTEGER NOT NULL DEFAULT 0"), ("google_sub", "TEXT")):
            if col not in ucols:  # migrate databases created before sign-up existed
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(lower(email)) WHERE email IS NOT NULL")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google ON users(google_sub) WHERE google_sub IS NOT NULL")


def row_to_doc(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["allowed_roles"] = json.loads(d["allowed_roles"])
    return d


def fts_add(doc_id: int, items: list[tuple[str, int]]) -> None:
    with db() as conn:
        conn.executemany(
            "INSERT INTO chunks_fts (text, doc_id, chunk_index, page) VALUES (?,?,?,?)",
            [(text, doc_id, i, page) for i, (text, page) in enumerate(items)],
        )


def fts_delete(doc_id: int) -> None:
    with db() as conn:
        conn.execute("DELETE FROM chunks_fts WHERE doc_id = ?", (doc_id,))
