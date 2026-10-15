from fastapi import FastAPI

from app.database import engine, Base
from app import models
from app.routes import auth_routes, admin_routes, document_routes, query_routes

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Enterprise RAG System with RBAC")
app.include_router(auth_routes.router)
app.include_router(admin_routes.router)
app.include_router(document_routes.router)
app.include_router(query_routes.router)


@app.get("/")
def home():
    return {"message": "Enterprise RAG System is running"}