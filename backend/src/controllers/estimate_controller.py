"""Estimate run endpoints."""
from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.middlewares.auth import get_current_user
from src.models import User
from src.schemas.common import Page
from src.schemas.estimate import EstimateCreateRequest, EstimateRunOut
from src.services import estimate_service
from src.utils.pagination import page_params


def create(
    payload: EstimateCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EstimateRunOut:
    run = estimate_service.create_run(db, user.display_name, payload)
    request.state.audit_resource_id = run.run_no
    request.state.audit_detail = {"scope": run.scope, "scope_value": run.scope_value}
    return estimate_service.run_detail(db, run.id)


def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Page[EstimateRunOut]:
    params = page_params(page, page_size)
    items, total = estimate_service.list_runs(db, params)
    return Page[EstimateRunOut](items=items, total=total, page=params.page, page_size=params.page_size)


def detail(
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EstimateRunOut:
    return estimate_service.run_detail(db, run_id)
