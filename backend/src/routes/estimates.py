"""Estimate run router."""
from fastapi import APIRouter, Depends

from src.controllers import estimate_controller
from src.middlewares.rbac import require_roles
from src.schemas.common import Page
from src.schemas.estimate import EstimateCreateRequest, EstimateRunOut

router = APIRouter(prefix="/estimates", tags=["estimates"])

router.add_api_route("", estimate_controller.list_runs, methods=["GET"], response_model=Page[EstimateRunOut])
router.add_api_route("", estimate_controller.create, methods=["POST"], response_model=EstimateRunOut,
                     dependencies=[Depends(require_roles("admin", "engineer"))])
router.add_api_route("/{run_id}", estimate_controller.detail, methods=["GET"], response_model=EstimateRunOut)
