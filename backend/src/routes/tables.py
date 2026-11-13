"""Table metadata router."""
from fastapi import APIRouter, Depends

from src.controllers import table_controller
from src.middlewares.rbac import require_roles
from src.schemas.table import TableDetail, TableListItem, TableUpdateRequest

router = APIRouter(prefix="/tables", tags=["tables"])

router.add_api_route("", table_controller.list_tables, methods=["GET"], response_model=list[TableListItem])
router.add_api_route("/{table_id}", table_controller.detail, methods=["GET"], response_model=TableDetail)
router.add_api_route("/{table_id}", table_controller.update, methods=["PATCH"], response_model=TableDetail,
                     dependencies=[Depends(require_roles("admin"))])
