"""Budget policy endpoints."""
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.middlewares.auth import get_current_user
from src.models import User
from src.schemas.budget import BudgetOverview, PolicyCreateRequest, PolicyOut, PolicyUpdateRequest
from src.services import budget_service


def list_policies(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PolicyOut]:
    return budget_service.list_policies(db)


def overview(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> BudgetOverview:
    return budget_service.overview(db)


def update_policy(
    policy_id: int,
    payload: PolicyUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PolicyOut:
    request.state.audit_resource_id = policy_id
    return budget_service.update_policy(db, policy_id, payload, user.display_name)


def create_policy(
    payload: PolicyCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PolicyOut:
    created = budget_service.create_policy(db, payload, user.display_name)
    request.state.audit_resource_id = created.policy_no
    return created
