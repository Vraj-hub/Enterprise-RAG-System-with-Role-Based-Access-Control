import io
import os
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, rag
from app.auth import get_current_user
from app.rbac import require_roles

router = APIRouter(prefix="/documents", tags=["Documents"])

MAX_SIZE = 10 * 1024 * 1024
UPLOAD_DIR = "uploads"


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    allowed_roles: str = Form("Admin,Manager,Employee"),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("Admin", "Manager")),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".pdf", ".txt"):
        raise HTTPException(status_code=400, detail="Only PDF and TXT files are allowed")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")

    roles = [r.strip() for r in allowed_roles.split(",") if r.strip()]
    if not roles or any(r not in rag.ALL_ROLES for r in roles):
        raise HTTPException(status_code=400, detail="allowed_roles must use: Admin, Manager, Employee")

    pages = []
    if ext == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(content))
        except Exception:
            raise HTTPException(status_code=400, detail="Could not read PDF")
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append((i, text))
    else:
        text = content.decode("utf-8", errors="ignore")
        if text.strip():
            pages.append((1, text))

    if not pages:
        raise HTTPException(status_code=400, detail="No readable text found in file")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    doc = models.Document(
        title=file.filename,
        file_path="",
        file_type=ext[1:].upper(),
        uploaded_by=user.user_id,
        access_level=",".join(roles),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    path = os.path.join(UPLOAD_DIR, f"{doc.doc_id}_{os.path.basename(file.filename)}")
    with open(path, "wb") as f:
        f.write(content)
    doc.file_path = path
    db.commit()

    chunk_count = rag.add_document(doc.doc_id, doc.title, pages, roles)
    return {
        "message": "Document uploaded and indexed",
        "doc_id": doc.doc_id,
        "chunks": chunk_count,
        "allowed_roles": roles,
    }


@router.get("/")
def list_documents(db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    docs = db.query(models.Document).all()
    role = user.role.role_name
    return [
        {"doc_id": d.doc_id, "title": d.title, "type": d.file_type,
         "allowed_roles": d.access_level}
        for d in docs if role in d.access_level.split(",")
    ]