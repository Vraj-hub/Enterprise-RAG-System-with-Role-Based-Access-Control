from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.rbac import require_roles

router = APIRouter(prefix="/admin", tags=["Admin"])


class RoleUpdate(BaseModel):
    role_name: str


@router.get("/users")
def list_users(db: Session = Depends(get_db),
               admin: models.User = Depends(require_roles("Admin"))):
    users = db.query(models.User).all()
    return [
        {"user_id": u.user_id, "username": u.username,
         "email": u.email, "role": u.role.role_name}
        for u in users
    ]


@router.put("/users/{user_id}/role")
def change_role(user_id: int, data: RoleUpdate,
                db: Session = Depends(get_db),
                admin: models.User = Depends(require_roles("Admin"))):
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    role = db.query(models.Role).filter(models.Role.role_name == data.role_name).first()
    if not role:
        raise HTTPException(status_code=400, detail="Invalid role name")
    user.role_id = role.role_id
    db.commit()
    return {"message": f"{user.username} is now {role.role_name}"}


@router.get("/manager-area")
def manager_area(user: models.User = Depends(require_roles("Admin", "Manager"))):
    return {"message": f"Welcome {user.username}, you can manage documents"}