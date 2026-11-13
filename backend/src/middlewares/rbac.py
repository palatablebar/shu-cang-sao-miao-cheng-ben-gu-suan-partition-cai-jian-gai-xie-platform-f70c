"""Role checks as FastAPI dependencies.

``require_roles("admin")`` answers a real 403 (not a hidden frontend button) and
names the roles that would have been accepted in the error detail.
"""
from fastapi import Depends

from src.constants.enums import Role
from src.constants.error_codes import AppError, ErrorCode
from src.constants.messages import MSG_FORBIDDEN
from src.middlewares.auth import get_current_user
from src.models import User

ADMIN = Role.ADMIN.value
ENGINEER = Role.ENGINEER.value
VIEWER = Role.VIEWER.value

WRITE_ROLES = (ADMIN, ENGINEER)
ALL_ROLES = (ADMIN, ENGINEER, VIEWER)


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise AppError(
                ErrorCode.FORBIDDEN,
                message=f"{MSG_FORBIDDEN}（当前角色 {user.role}，需要 {'/'.join(roles)}）",
                detail={"required_roles": list(roles), "role": user.role},
            )
        return user

    return dependency


def can_write(user: User) -> bool:
    return user.role in WRITE_ROLES
