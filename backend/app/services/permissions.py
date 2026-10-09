
from fastapi import Depends, HTTPException, status

from app.api.auth import get_current_user


ROLE_PERMISSIONS = {
    "USER": {
        "documents:upload",
        "documents:read_own",
        "documents:delete_own",
        "reconciliation:run_own",
        "reports:read_own",
    },
    "ADMIN": {
        "documents:read_all",
        "documents:delete_all",
        "users:read",
        "users:manage",
        "reports:read_all",
    },
}


def require_role(*allowed_roles: str):
    def role_checker(user=Depends(get_current_user)):
        role = user.get("role", "USER")

        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )

        return user

    return role_checker


def require_permission(permission: str):
    def permission_checker(user=Depends(get_current_user)):
        role = user.get("role", "USER")
        permissions = ROLE_PERMISSIONS.get(role, set())

        if permission not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )

        return user

    return permission_checker
