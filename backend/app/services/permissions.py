"""
app/services/permissions.py

Role-based access control helpers.

Two roles are currently defined:
  USER  — a regular account that owns and manages their own documents.
  ADMIN — has all USER permissions plus administrative capabilities.

Why does ADMIN inherit USER permissions?
  Without explicit inheritance the ADMIN role had no "documents:upload"
  permission, meaning an admin account could not even upload a file.
  The safest fix is to make ADMIN a superset of USER.

Usage in route handlers
-----------------------
  # Allow only ADMINs:
  user = Depends(require_role("ADMIN"))

  # Allow either role:
  user = Depends(require_role("USER", "ADMIN"))

  # Check a specific capability:
  user = Depends(require_permission("documents:upload"))
"""

from fastapi import Depends, HTTPException, status

from app.services.auth_dependencies import get_current_user

# Base permissions for regular users
_USER_PERMISSIONS = {
    "documents:upload",
    "documents:read_own",
    "documents:delete_own",
    "reconciliation:run_own",
    "reports:read_own",
}

# ADMIN has all USER permissions plus administrative ones
_ADMIN_PERMISSIONS = _USER_PERMISSIONS | {
    "documents:read_all",
    "documents:delete_all",
    "users:read",
    "users:manage",
    "reports:read_all",
}

ROLE_PERMISSIONS: dict[str, set] = {
    "USER": _USER_PERMISSIONS,
    "ADMIN": _ADMIN_PERMISSIONS,
}


def require_role(*allowed_roles: str):
    """
    Dependency factory: raises 403 unless the authenticated user's role
    is one of allowed_roles.

    Example:
        @router.get("/admin-only")
        def admin_only(user = Depends(require_role("ADMIN"))):
            ...
    """
    def role_checker(user: dict = Depends(get_current_user)):
        if user.get("role", "USER") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return user

    return role_checker


def require_permission(permission: str):
    """
    Dependency factory: raises 403 unless the authenticated user's role
    grants the specified permission string.

    Example:
        @router.post("/upload")
        def upload(user = Depends(require_permission("documents:upload"))):
            ...
    """
    def permission_checker(user: dict = Depends(get_current_user)):
        role = user.get("role", "USER")
        if permission not in ROLE_PERMISSIONS.get(role, set()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return user

    return permission_checker
