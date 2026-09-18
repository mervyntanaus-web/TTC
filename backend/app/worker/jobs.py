import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.db import SessionLocal
from app.services import retention_service

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _run_sweep_job() -> None:
    db = SessionLocal()
    try:
        result = retention_service.run_sweep(db)
        if result.archived or result.deleted:
            logger.info(
                "Retention sweep: archived=%s deleted=%s", len(result.archived), len(result.deleted)
            )
    finally:
        db.close()


def start_scheduler(interval_hours: int = 6) -> BackgroundScheduler:
    """Starts the background retention/archive sweep on a fixed interval.
    Also exposed manually via POST /retention/run-sweep for demos where
    waiting hours for the schedule isn't practical."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(_run_sweep_job, "interval", hours=interval_hours, id="retention_sweep")
    _scheduler.start()
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
