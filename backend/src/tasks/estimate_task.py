"""Celery task: run one EstimateRun inside the worker container."""
from src.config.celery_app import celery_app
from src.config.database import SessionLocal
from src.utils.logger import log_event


@celery_app.task(name="partfit.run_estimate", bind=True, max_retries=2, default_retry_delay=3)
def run_estimate_task(self, run_id: int) -> dict:
    from src.services import estimate_service

    log_event("ESTIMATE_TASK_START", run_id=run_id)
    with SessionLocal() as db:
        try:
            run = estimate_service.execute_run(db, run_id)
        except Exception as exc:  # let Celery retry a couple of times before failing the run
            log_event("ESTIMATE_TASK_ERROR", run_id=run_id, error=f"{type(exc).__name__}: {exc}")
            if self.request.retries < self.max_retries:
                raise self.retry(exc=exc)
            with SessionLocal() as fail_db:
                estimate_service.mark_failed(fail_db, run_id, f"{type(exc).__name__}: {exc}")
            return {"run_id": run_id, "status": "failed"}
    return {
        "run_id": run.id,
        "status": run.status,
        "query_count": run.query_count,
        "blocked_count": run.blocked_count,
        "total_scan_bytes": run.total_scan_bytes,
    }
