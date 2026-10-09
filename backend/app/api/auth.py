
from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.database.mongodb import get_database
from app.models.user import create_user
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
)
from app.services.auth_dependencies import get_current_user
from app.services.permissions import require_role


router = APIRouter(prefix="/api/auth", tags=["Authentication"])



@router.post("/register", response_model=UserResponse, status_code=201)
def register(payload: UserRegister):
    database = get_database()
    users = database["users"]

    email = str(payload.email).strip().lower()
    if users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Email already registered")

    user = create_user(
        name=payload.name,
        email=email,
        hashed_password=hash_password(payload.password),
    )

    try:
        result = users.insert_one(user)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Email already registered")

    return UserResponse(
        id=str(result.inserted_id),
        name=user["name"],
        email=user["email"],
        role=user["role"],
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin):
    database = get_database()
    user = database["users"].find_one(
        {"email": str(payload.email).strip().lower()}
    )

    if not user or not verify_password(
        payload.password, user["hashed_password"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("is_active", False):
        raise HTTPException(status_code=403, detail="Account is inactive")

    token = create_access_token(str(user["_id"]))
    return TokenResponse(access_token=token)

@router.get("/me", response_model=UserResponse)
def get_me(user=Depends(get_current_user)):
    return UserResponse(
        id=str(user["_id"]),
        name=user["name"],
        email=user["email"],
        role=user.get("role", "USER"),
    )

@router.get("/admin-check")
def admin_check(user=Depends(require_role("ADMIN"))):
    return {"message": "Admin access granted"}
