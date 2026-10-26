import io
import json
import re
import uuid
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

from . import vectorstore
from .config import ALLOWED_EXTENSIONS, CHUNK_OVERLAP, CHUNK_SIZE, UPLOAD_DIR
from .db import db, row_to_doc

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    _splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

    def split_text(text: str) -> list[str]:
        return [c.strip() for c in _splitter.split_text(text) if c.strip()]

except ImportError:  # minimal fallback

    def split_text(text: str) -> list[str]:
        step = CHUNK_SIZE - CHUNK_OVERLAP
        return [text[i : i + CHUNK_SIZE].strip() for i in range(0, len(text), step) if text[i : i + CHUNK_SIZE].strip()]


class IngestError(ValueError):
    pass


def safe_filename(name: str) -> str:
    base = Path(name).name  # strip any path components
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", base)
    return base[:120] or "document"


def extract_text(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise IngestError(f"File type '{ext}' is not allowed. Use: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    try:
        if ext == ".pdf":
            reader = PdfReader(io.BytesIO(data))
            return "\n".join((p.extract_text() or "") for p in reader.pages)
        if ext == ".docx":
            doc = DocxDocument(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)
        return data.decode("utf-8", errors="ignore")
    except Exception as exc:  # corrupt files
        raise IngestError(f"Could not read the file: {exc}") from exc


def ingest_document(
    *, filename: str, data: bytes, owner: dict, department: str, sensitivity: str, allowed_roles: list[str]
) -> dict:
    filename = safe_filename(filename)
    text = extract_text(filename, data)
    chunks = split_text(text)
    if not chunks:
        raise IngestError("The file has no readable text.")

    roles = sorted(set(allowed_roles) | {"admin"})  # admin can always read
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO documents (filename, owner_id, department, sensitivity, allowed_roles)
               VALUES (?,?,?,?,?)""",
            (filename, owner["id"], department, sensitivity, json.dumps(roles)),
        )
        doc_id = cur.lastrowid
        row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    doc = row_to_doc(row)

    stored_path = UPLOAD_DIR / f"{doc_id}_{uuid.uuid4().hex[:8]}_{filename}"
    stored_path.write_bytes(data)
    try:
        count = vectorstore.add_chunks(doc, chunks)
    except Exception:
        # Keep database, vector index, and uploaded files consistent on failed indexing.
        try:
            vectorstore.delete_document(doc_id)
        except Exception:
            pass
        with db() as conn:
            conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        try:
            stored_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    with db() as conn:
        conn.execute("UPDATE documents SET chunk_count=? WHERE id=?", (count, doc_id))
    doc["chunk_count"] = count
    return doc
