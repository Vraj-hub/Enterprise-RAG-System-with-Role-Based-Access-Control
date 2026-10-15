from fastapi import Depends, HTTPException, status
from app.auth import get_current_user
from app import models


def require_roles(*allowed_roles: str):
    def checker(current_user: models.User = Depends(get_current_user)):
        if current_user.role.role_name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )
        return current_user
    return checker