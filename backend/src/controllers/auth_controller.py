"""Auth endpoints."""
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.config.settings import settings
from src.middlewares.auth import get_current_user
from src.models import User
from src.schemas.auth import LoginRequest, TokenResponse
from src.schemas.user import UserOut
from src.services import auth_service
from src.utils.jwt import create_access_token


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        team=user.team,
    )


def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    user = auth_service.authenticate(db, payload.email, payload.password)
    request.state.user_claims = {"sub": str(user.id), "email": user.email, "role": user.role}
    request.state.audit_detail = {"role": user.role}
    return TokenResponse(
        access_token=create_access_token(user),
        expires_in=settings.JWT_EXPIRE_HOURS * 3600,
        user=_user_out(user),
    )


def me(user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(user)
