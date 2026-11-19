import json
import time
from collections import defaultdict
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import audit, ingest, rag, rbac, vectorstore
from .db import fts_delete
from .routes_extra import router as extra_router
from .auth_routes import router as auth_router
from .config import MAX_UPLOAD_BYTES
from .db import db, init_db, row_to_doc
from .security import create_token, get_current_user, hash_password, require_roles, verify_password

app = FastAPI(title="Enterprise RAG with RBAC")
init_db()
app.include_router(extra_router)
app.include_router(auth_router)

_CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    if not request.url.path.startswith(("/docs", "/redoc", "/openapi")):
        resp.headers["Content-Security-Policy"] = _CSP
    return resp

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ---- tiny in-memory login throttle: 5 failures / 5 minutes per username
_failures: dict[str, list[float]] = defaultdict(list)
WINDOW, MAX_FAILS = 300, 5


def _throttled(username: str) -> bool:
    now = time.time()
    _failures[username] = [t for t in _failures[username] if now - t < WINDOW]
    return len(_failures[username]) >= MAX_FAILS


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class QueryIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    conversation_id: int | None = None


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    role: str
    department: str = Field(min_length=2, max_length=64)


class UserUpdate(BaseModel):
    role: str | None = None
    department: str | None = Field(default=None, min_length=2, max_length=64)
    is_active: bool | None = None


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


# ------------------------------------------------------------------ auth
@app.post("/api/login")
def login(body: LoginIn):
    if _throttled(body.username):
        audit.log(action="login_failed", decision="denied", username=body.username, detail="throttled")
        raise HTTPException(429, "Too many failed attempts. Try again in a few minutes.")
    with db() as conn:
        # usernames cannot contain "@" (enforced at creation), so a username and an email never collide
        row = conn.execute("SELECT * FROM users WHERE username=? OR lower(email)=lower(?)", (body.username, body.username)).fetchone()
    if row is None or not row["is_active"] or not verify_password(body.password, row["password_hash"]):
        _failures[body.username].append(time.time())
        audit.log(action="login_failed", decision="denied", username=body.username)
        raise HTTPException(401, "Wrong username or password")
    user = dict(row)
    audit.log(action="login", decision="allowed", user=user)
    return {"access_token": create_token(user["id"]), "token_type": "bearer"}


@app.get("/api/me")
def me(user: dict = Depends(get_current_user)):
    return {
        **{k: user[k] for k in ("id", "username", "role", "department")},
        "clearance": rbac.CLEARANCE[user["role"]],
        "can_upload": user["role"] in ("admin", "manager"),
    }


# ------------------------------------------------------------------ query
@app.post("/api/query")
def query(body: QueryIn, user: dict = Depends(get_current_user)):
    return rag.answer_query(body.question.strip(), user, body.conversation_id)


# ------------------------------------------------------------------ documents
@app.get("/api/documents")
def list_documents(user: dict = Depends(get_current_user)):
    with db() as conn:
        rows = conn.execute("SELECT d.*, u.username AS owner FROM documents d JOIN users u ON u.id=d.owner_id ORDER BY d.id DESC").fetchall()
    docs = [row_to_doc(r) for r in rows]
    return [d for d in docs if rbac.can_access(user, d)]


@app.post("/api/documents", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    department: str = Form(...),
    sensitivity: str = Form(...),
    allowed_roles: str = Form("employee,manager,admin"),
    user: dict = Depends(require_roles("admin", "manager")),
):
    if sensitivity not in rbac.SENSITIVITY:
        raise HTTPException(422, f"sensitivity must be one of {list(rbac.SENSITIVITY)}")
    roles = [r.strip() for r in allowed_roles.split(",") if r.strip()]
    if not roles or any(r not in rbac.ROLES for r in roles):
        raise HTTPException(422, f"allowed_roles must be a subset of {list(rbac.ROLES)}")
    department = department.strip().lower() or rbac.COMPANY_WIDE
    if not rbac.can_upload(user, department, sensitivity):
        audit.log(action="upload", decision="denied", user=user, detail=f"{department}/{sensitivity}")
        raise HTTPException(403, "Managers can upload only to their own department, up to 'confidential'.")

    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 10 MB")
    try:
        doc = ingest.ingest_document(
            filename=file.filename or "document", data=data, owner=user,
            department=department, sensitivity=sensitivity, allowed_roles=roles,
        )
    except ingest.IngestError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        raise HTTPException(503, f"Document indexing is unavailable: {exc}") from exc
    audit.log(action="upload", decision="allowed", user=user, sources=[{"doc_id": doc["id"], "filename": doc["filename"]}])
    return doc


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: int, user: dict = Depends(require_roles("admin"))):
    with db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Document not found")
        conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    vectorstore.delete_document(doc_id)
    fts_delete(doc_id)
    audit.log(action="delete", decision="allowed", user=user, sources=[{"doc_id": doc_id, "filename": row["filename"]}])
    return {"deleted": doc_id}


# ------------------------------------------------------------------ admin
@app.get("/api/admin/users")
def admin_list_users(user: dict = Depends(require_roles("admin"))):
    with db() as conn:
        rows = conn.execute("SELECT id, username, email, role, department, is_active, created_at FROM users ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/admin/users", status_code=201)
def admin_create_user(body: UserCreate, admin: dict = Depends(require_roles("admin"))):
    if body.role not in rbac.ROLES:
        raise HTTPException(422, f"role must be one of {list(rbac.ROLES)}")
    with db() as conn:
        if conn.execute("SELECT 1 FROM users WHERE username=?", (body.username,)).fetchone():
            raise HTTPException(409, "Username already exists")
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, role, department) VALUES (?,?,?,?)",
            (body.username, hash_password(body.password), body.role, body.department.lower()),
        )
    audit.log(action="admin_change", decision="allowed", user=admin, detail=f"created {body.username} as {body.role}")
    return {"id": cur.lastrowid, "username": body.username, "role": body.role, "department": body.department.lower()}


@app.patch("/api/admin/users/{user_id}")
def admin_update_user(user_id: int, body: UserUpdate, admin: dict = Depends(require_roles("admin"))):
    if body.role and body.role not in rbac.ROLES:
        raise HTTPException(422, f"role must be one of {list(rbac.ROLES)}")
    if user_id == admin["id"] and (body.role not in (None, "admin") or body.is_active is False):
        raise HTTPException(400, "You cannot demote or disable your own admin account")
    fields, values = [], []
    if body.role:
        fields.append("role=?"); values.append(body.role)
    if body.department:
        fields.append("department=?"); values.append(body.department.lower())
    if body.is_active is not None:
        fields.append("is_active=?"); values.append(int(body.is_active))
    if not fields:
        raise HTTPException(422, "Nothing to update")
    with db() as conn:
        cur = conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id=?", (*values, user_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "User not found")
    audit.log(action="admin_change", decision="allowed", user=admin, detail=f"updated user {user_id}: {body.model_dump(exclude_none=True)}")
    return {"updated": user_id}


@app.get("/api/admin/audit")
def admin_audit(limit: int = 100, user: dict = Depends(require_roles("admin"))):
    limit = max(1, min(limit, 500))
    with db() as conn:
        rows = conn.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["sources"] = json.loads(d["sources"] or "[]")
        out.append(d)
    return out
