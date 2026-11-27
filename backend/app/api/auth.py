
from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.database.mongodb import get_database
from app.models.user import create_user
from app.schemas.auth import (
    ManagedUserResponse,
    UserRegister,
    UserLogin,
    TokenResponse,
    UserResponse,
    UserActivationUpdate,
)
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
)
from app.services.auth_dependencies import get_current_user
from app.services.permissions import require_role
from app.services.audit_service import log_audit_event


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _managed_user_response(user: dict) -> ManagedUserResponse:
    return ManagedUserResponse(
        id=str(user["_id"]),
        name=user["name"],
        email=user["email"],
        role=user.get("role", "USER"),
        is_active=user.get("is_active", False),
        created_at=user.get("created_at"),
    )



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


@router.get("/users", response_model=list[ManagedUserResponse])
def list_users(admin: dict = Depends(require_role("ADMIN"))):
    users = get_database()["users"].find(
        {},
        {"hashed_password": 0},
    ).sort("created_at", -1)
    return [_managed_user_response(user) for user in users]


@router.get("/users/{user_id}", response_model=ManagedUserResponse)
def get_user(
    user_id: str,
    admin: dict = Depends(require_role("ADMIN")),
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID.")

    user = get_database()["users"].find_one(
        {"_id": ObjectId(user_id)},
        {"hashed_password": 0},
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return _managed_user_response(user)


@router.patch("/users/{user_id}/activation", response_model=ManagedUserResponse)
def update_user_activation(
    user_id: str,
    payload: UserActivationUpdate,
    admin: dict = Depends(require_role("ADMIN")),
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID.")
    target_user_id = ObjectId(user_id)
    if ObjectId(str(admin["_id"])) == target_user_id and not payload.is_active:
        raise HTTPException(
            status_code=400,
            detail="Administrators cannot deactivate their own account.",
        )

    users = get_database()["users"]
    user = users.find_one({"_id": target_user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if user.get("is_active", False) != payload.is_active:
        users.update_one(
            {"_id": target_user_id},
            {"$set": {"is_active": payload.is_active}},
        )
        user["is_active"] = payload.is_active
        log_audit_event(
            action="USER_ACTIVATION_UPDATED",
            user_id=str(admin["_id"]),
            resource_type="user",
            resource_id=user_id,
            details={"is_active": payload.is_active},
        )
    return _managed_user_response(user)
