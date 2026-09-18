from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import User, UserRole
from app.models.watermark import Watermark, WatermarkScope
from app.schemas.watermark import WatermarkOut, WatermarkUpsert
from app.security import require_roles
from app.services.audit_service import log_action

router = APIRouter(prefix="/watermarks", tags=["watermark"])


@router.get("/global", response_model=WatermarkOut | None)
def get_global_watermark(db: Session = Depends(get_db)) -> Watermark | None:
    return db.query(Watermark).filter(Watermark.scope == WatermarkScope.GLOBAL).first()


@router.put("/global", response_model=WatermarkOut)
def set_global_watermark(
    payload: WatermarkUpsert,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
) -> Watermark:
    """Administrator-controlled default watermark applied to every viewer
    unless they have their own user-specific override."""
    wm = db.query(Watermark).filter(Watermark.scope == WatermarkScope.GLOBAL).first()
    if wm:
        wm.template = payload.template
        wm.enabled_for_playback = payload.enabled_for_playback
        wm.enabled_for_export = payload.enabled_for_export
    else:
        wm = Watermark(scope=WatermarkScope.GLOBAL, **payload.model_dump())
        db.add(wm)
    db.commit()
    db.refresh(wm)
    log_action(db, user, "watermark.global.update", "watermark", wm.id, payload.model_dump())
    return wm


@router.get("/me", response_model=WatermarkOut | None)
def get_my_watermark(db: Session = Depends(get_db), user: User = Depends(require_roles())) -> Watermark | None:
    return (
        db.query(Watermark)
        .filter(Watermark.scope == WatermarkScope.USER, Watermark.user_id == user.id)
        .first()
    )


@router.put("/me", response_model=WatermarkOut)
def set_my_watermark(
    payload: WatermarkUpsert, db: Session = Depends(get_db), user: User = Depends(require_roles())
) -> Watermark:
    wm = (
        db.query(Watermark)
        .filter(Watermark.scope == WatermarkScope.USER, Watermark.user_id == user.id)
        .first()
    )
    if wm:
        wm.template = payload.template
        wm.enabled_for_playback = payload.enabled_for_playback
        wm.enabled_for_export = payload.enabled_for_export
    else:
        wm = Watermark(scope=WatermarkScope.USER, user_id=user.id, **payload.model_dump())
        db.add(wm)
    db.commit()
    db.refresh(wm)
    log_action(db, user, "watermark.user.update", "watermark", wm.id, payload.model_dump())
    return wm
