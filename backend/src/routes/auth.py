"""Auth router."""
from fastapi import APIRouter

from src.controllers import auth_controller
from src.schemas.auth import LoginRequest, TokenResponse
from src.schemas.user import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

router.add_api_route("/login", auth_controller.login, methods=["POST"], response_model=TokenResponse)
router.add_api_route("/me", auth_controller.me, methods=["GET"], response_model=UserOut)
