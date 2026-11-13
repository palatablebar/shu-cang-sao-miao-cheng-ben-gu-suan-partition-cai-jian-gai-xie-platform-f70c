"""Budget policy router (write = admin only)."""
from fastapi import APIRouter, Depends

from src.controllers import budget_controller
from src.middlewares.rbac import require_roles
from src.schemas.budget import BudgetOverview, PolicyCreateRequest, PolicyOut, PolicyUpdateRequest

router = APIRouter(prefix="/budget", tags=["budget"])

router.add_api_route("/overview", budget_controller.overview, methods=["GET"], response_model=BudgetOverview)
router.add_api_route("/policies", budget_controller.list_policies, methods=["GET"], response_model=list[PolicyOut])
router.add_api_route("/policies", budget_controller.create_policy, methods=["POST"], response_model=PolicyOut,
                     dependencies=[Depends(require_roles("admin"))])
router.add_api_route("/policies/{policy_id}", budget_controller.update_policy, methods=["PUT"],
                     response_model=PolicyOut, dependencies=[Depends(require_roles("admin"))])
