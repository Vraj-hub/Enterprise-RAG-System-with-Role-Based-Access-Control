import re
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.auth import (hash_password, verify_password,
                      create_access_token, get_current_user)

router = APIRouter(prefix="/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(max_length=100)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("email")
    @classmethod
    def check_email(cls, v):
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email format")
        return v

    @field_validator("password")
    @classmethod
    def check_password(cls, v):
        if not (re.search(r"[A-Z]", v) and re.search(r"[a-z]", v)
                and re.search(r"\d", v) and re.search(r"[^A-Za-z0-9]", v)):
            raise ValueError("Password needs uppercase, lowercase, number and special character")
        return v


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    exists = db.query(models.User).filter(
        (models.User.username == data.username) | (models.User.email == data.email)
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="Username or email already registered")

    employee_role = db.query(models.Role).filter(models.Role.role_name == "Employee").first()
    user = models.User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        role_id=employee_role.role_id,
    )
    db.add(user)
    db.commit()
    return {"message": "User registered successfully"}


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token({"sub": str(user.user_id), "role": user.role.role_name})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def me(current_user: models.User = Depends(get_current_user)):
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role.role_name,
    }
    