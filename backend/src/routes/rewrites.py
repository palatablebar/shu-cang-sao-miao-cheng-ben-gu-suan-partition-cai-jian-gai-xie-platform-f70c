"""Rewrite suggestion router."""
from fastapi import APIRouter, Depends

from src.controllers import rewrite_controller
from src.middlewares.rbac import require_roles
from src.schemas.common import Page
from src.schemas.rewrite import (
    RewriteDetail,
    RewriteGenerateRequest,
    RewriteOut,
    RewriteReevaluateOut,
)

router = APIRouter(prefix="/rewrites", tags=["rewrites"])

router.add_api_route("", rewrite_controller.list_suggestions, methods=["GET"], response_model=Page[RewriteOut])
router.add_api_route("/export.csv", rewrite_controller.export_csv, methods=["GET"])
router.add_api_route("/generate", rewrite_controller.generate, methods=["POST"], response_model=RewriteDetail,
                     dependencies=[Depends(require_roles("admin", "engineer"))])
router.add_api_route("/{suggestion_id}", rewrite_controller.detail, methods=["GET"], response_model=RewriteDetail)
router.add_api_route("/{suggestion_id}/reevaluate", rewrite_controller.reevaluate, methods=["POST"],
                     response_model=RewriteReevaluateOut,
                     dependencies=[Depends(require_roles("admin", "engineer"))])
router.add_api_route("/{suggestion_id}/adopt", rewrite_controller.adopt, methods=["POST"], response_model=RewriteOut,
                     dependencies=[Depends(require_roles("admin", "engineer"))])
