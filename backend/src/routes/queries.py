"""Query log router. Write endpoints require admin/engineer (viewer gets a real 403)."""
from fastapi import APIRouter, Depends

from src.controllers import query_controller
from src.middlewares.rbac import require_roles
from src.schemas.common import Page
from src.schemas.query import QueryDetail, QueryImportResult, QueryListItem

router = APIRouter(prefix="/queries", tags=["queries"])

router.add_api_route("", query_controller.list_queries, methods=["GET"], response_model=Page[QueryListItem])
router.add_api_route("/ranking", query_controller.ranking, methods=["GET"], response_model=list[QueryListItem])
router.add_api_route("/stats", query_controller.stats, methods=["GET"])
router.add_api_route("/import", query_controller.import_pack, methods=["POST"], response_model=QueryImportResult,
                     dependencies=[Depends(require_roles("admin", "engineer"))])
router.add_api_route("/{query_id}", query_controller.detail, methods=["GET"], response_model=QueryDetail)
router.add_api_route("/{query_id}/analyze", query_controller.analyse, methods=["POST"], response_model=QueryDetail,
                     dependencies=[Depends(require_roles("admin", "engineer"))])
