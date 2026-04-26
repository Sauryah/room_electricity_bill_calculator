"""Authentication routes: /login (POST)."""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.security import (
    create_access_token,
    verify_password,
)
from app.db.client import get_user_by_username

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    username = payload.username.strip().lower()

    user = get_user_by_username(username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(user_id=user["id"], username=user["username"])
    return LoginResponse(
        access_token=token,
        user_id=user["id"],
        username=user["username"],
    )
