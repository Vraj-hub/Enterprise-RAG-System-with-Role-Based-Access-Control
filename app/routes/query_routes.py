import traceback

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, rag
from app.auth import get_current_user

router = APIRouter(prefix="/query", tags=["Query"])

NOT_FOUND = "I could not find this information in the documents available to you."


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)

    @field_validator("question")
    @classmethod
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("Question cannot be empty")
        return v.strip()


@router.post("/")
def ask(data: QueryRequest, db: Session = Depends(get_db),
        user: models.User = Depends(get_current_user)):
    try:
        role = user.role.role_name
        chunks = rag.search(data.question, role)

        if not chunks:
            answer = NOT_FOUND
        else:
            answer = rag.ask_llm(data.question, chunks)

        db.add(models.QueryLog(user_id=user.user_id,
                               query_text=data.question,
                               response_text=answer))
        db.commit()

        sources = sorted({m["source"] for _, m in chunks})
        return {"question": data.question, "role": role,
                "answer": answer, "sources": sources}
    except Exception as e:
        db.rollback()
        last_lines = traceback.format_exc().strip().splitlines()[-6:]
        error_info = {"error": f"{type(e).__name__}: {e}", "where": last_lines}
        raise HTTPException(status_code=500, detail=error_info)


@router.get("/history")
def history(db: Session = Depends(get_db),
            user: models.User = Depends(get_current_user)):
    logs = (db.query(models.QueryLog)
            .filter(models.QueryLog.user_id == user.user_id)
            .order_by(models.QueryLog.log_id.desc()).limit(20).all())
    return [{"question": l.query_text, "answer": l.response_text,
             "time": str(l.timestamp)} for l in logs]