import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.routes.playback import get_video_or_404
from app.db import get_db
from app.models.retention import RetentionPolicy
from app.models.user import User, UserRole
from app.schemas.retention import (
    LegalHoldUpdate,
    RetentionPolicyOut,
    RetentionPolicyUpsert,
    RetentionStatusOut,
    SweepResultOut,
)
from app.security import require_roles
from app.services import retention_service
from app.services.audit_service import log_action

router = APIRouter(tags=["retention"])


@router.get("/retention-policies", response_model=list[RetentionPolicyOut])
def list_policies(db: Session = Depends(get_db)) -> list[RetentionPolicy]:
    return db.query(RetentionPolicy).order_by(RetentionPolicy.category).all()


@router.put("/retention-policies", response_model=RetentionPolicyOut)
def upsert_policy(
    payload: RetentionPolicyUpsert,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
) -> RetentionPolicy:
    policy = db.query(RetentionPolicy).filter(RetentionPolicy.category == payload.category).first()
    if policy:
        for field, value in payload.model_dump().items():
            setattr(policy, field, value)
    else:
        policy = RetentionPolicy(**payload.model_dump())
        db.add(policy)
    db.commit()
    db.refresh(policy)
    log_action(db, user, "retention.policy.upsert", "retention_policy", policy.id, payload.model_dump())
    return policy


@router.get("/videos/{video_id}/retention-status", response_model=RetentionStatusOut)
def get_retention_status(video_id: uuid.UUID, db: Session = Depends(get_db)) -> RetentionStatusOut:
    video = get_video_or_404(db, video_id)
    return retention_service.retention_status(db, video)


@router.post("/videos/{video_id}/legal-hold", response_model=RetentionStatusOut)
def set_legal_hold(
    video_id: uuid.UUID,
    payload: LegalHoldUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.LEGAL, UserRole.STAFF)),
) -> RetentionStatusOut:
    """Places or lifts a legal hold, which overrides every other retention
    rule — a video under legal hold is never auto-archived or auto-deleted
    regardless of its category's policy."""
    video = get_video_or_404(db, video_id)
    video.legal_hold = payload.legal_hold
    db.commit()
    log_action(
        db, user, "retention.legal_hold.set", "video", video.id, {"legal_hold": payload.legal_hold}
    )
    return retention_service.retention_status(db, video)


@router.post("/retention/run-sweep", response_model=SweepResultOut)
def run_sweep_now(
    db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.ADMIN))
) -> SweepResultOut:
    """Manually triggers the retention/archive sweep that otherwise runs on
    a schedule (app/worker/jobs.py) — useful for demos and admin ops."""
    result = retention_service.run_sweep(db)
    log_action(
        db, user, "retention.sweep.run", "system", None,
        {"archived": [str(i) for i in result.archived], "deleted": [str(i) for i in result.deleted]},
    )
    return SweepResultOut(archived=result.archived, deleted=result.deleted)
