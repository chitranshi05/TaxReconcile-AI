
from bson import ObjectId
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.database.mongodb import get_database
from app.services.auth_service import decode_access_token

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
):
    token = credentials.credentials

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")

        if not user_id or not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=401, detail="Invalid token")

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_database()["users"].find_one({"_id": ObjectId(user_id)})

    if not user or not user.get("is_active", False):
        raise HTTPException(
            status_code=401,
            detail="User not found or inactive"
        )

    return user
