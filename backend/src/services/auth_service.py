"""Login + demo account bootstrap."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import Role
from src.constants.error_codes import AppError, ErrorCode
from src.constants.messages import MSG_LOGIN_FAILED
from src.models import User
from src.utils.password import verify_password


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None or not verify_password(password, user.password_hash):
        raise AppError(ErrorCode.UNAUTHORIZED, MSG_LOGIN_FAILED)
    if not user.is_active:
        raise AppError(ErrorCode.FORBIDDEN, "该账号已停用")
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)))


def ensure_demo_users(db: Session) -> int:
    """Idempotent bootstrap of the three demo accounts (natural key = email)."""
    from src.utils.password import hash_password

    created = 0
    seeds = [
        ("admin@partfit.io", "沈知远 · 平台负责人", Role.ADMIN.value, "澜图零售 · 数据平台组"),
        ("engineer@partfit.io", "陈肃 · 数据开发", Role.ENGINEER.value, "澜图零售 · 数据平台组"),
        ("viewer@partfit.io", "周娅 · 财务 BP", Role.VIEWER.value, "澜图零售 · 财务共享中心"),
    ]
    for email, name, role, team in seeds:
        existing = db.scalar(select(User).where(User.email == email))
        if existing is not None:
            continue
        db.add(
            User(
                email=email,
                display_name=name,
                role=role,
                team=team,
                password_hash=hash_password("Demo@2026"),
            )
        )
        created += 1
    if created:
        db.commit()
    return created
