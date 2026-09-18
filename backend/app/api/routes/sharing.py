import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.routes.playback import get_video_or_404, latest_version_or_404
from app.db import get_db
from app.models.folder import Folder
from app.models.share import ShareLink, ShareResourceType, ShareScope
from app.models.user import User
from app.schemas.share import ShareLinkCreate, ShareLinkOut
from app.security import get_current_user
from app.services.audit_service import log_action
from app.services.playback_service import build_stream_response
from app.services.sharing_service import ShareLinkInvalid, default_expiry, record_access, resolve_share_link

router = APIRouter(tags=["sharing"])


@router.post("/share-links", response_model=ShareLinkOut, status_code=201)
def create_share_link(
    payload: ShareLinkCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ShareLink:
    """Creates a scoped, expiring access grant to a video or folder for an
    internal or external recipient (TTC staff/legal, police, insurance,
    court, FOI, guest). External recipients use the resulting token against
    the public /share/{token}/* endpoints with no TTC login required."""
    if payload.resource_type == ShareResourceType.VIDEO:
        get_video_or_404(db, payload.resource_id)
    else:
        if not db.get(Folder, payload.resource_id):
            raise HTTPException(status_code=404, detail="Folder not found")

    link = ShareLink(
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        scope=payload.scope,
        recipient_type=payload.recipient_type,
        recipient_label=payload.recipient_label,
        created_by=user.id,
        expires_at=(
            default_expiry(payload.expires_in_days) if payload.expires_in_days is not None else None
        ),
    )
    db.add(link)
    db.commit()
    db.refresh(link)

    log_action(
        db, user, "share.create", payload.resource_type.value, payload.resource_id,
        {"share_link_id": str(link.id), "recipient_type": payload.recipient_type.value, "scope": payload.scope.value},
    )
    return link


@router.get("/share-links", response_model=list[ShareLinkOut])
def list_share_links(
    resource_id: uuid.UUID | None = None, db: Session = Depends(get_db)
) -> list[ShareLink]:
    query = db.query(ShareLink)
    if resource_id:
        query = query.filter(ShareLink.resource_id == resource_id)
    return query.order_by(ShareLink.created_at.desc()).all()


@router.post("/share-links/{link_id}/revoke", response_model=ShareLinkOut)
def revoke_share_link(
    link_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> ShareLink:
    link = db.get(ShareLink, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Share link not found")
    link.revoked = True
    db.commit()
    db.refresh(link)
    log_action(db, user, "share.revoke", link.resource_type.value, link.resource_id, {"share_link_id": str(link.id)})
    return link


def _get_valid_link(db: Session, token: str) -> ShareLink:
    try:
        return resolve_share_link(db, token)
    except ShareLinkInvalid as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc


@router.get("/share/{token}")
def get_shared_resource(token: str, db: Session = Depends(get_db)) -> dict:
    """Unauthenticated metadata lookup for an external recipient landing on
    a share link — confirms it's valid and tells the frontend what kind of
    resource/scope it's dealing with before it requests the stream."""
    link = _get_valid_link(db, token)
    record_access(db, link)
    log_action(
        db, None, "share.access", link.resource_type.value, link.resource_id,
        {"share_link_id": str(link.id), "recipient_type": link.recipient_type.value},
    )
    return {
        "resource_type": link.resource_type.value,
        "resource_id": str(link.resource_id),
        "scope": link.scope.value,
        "recipient_label": link.recipient_label,
    }


@router.get("/share/{token}/stream")
def stream_shared_video(token: str, request: Request, db: Session = Depends(get_db)) -> StreamingResponse:
    """Public, token-authenticated playback for external recipients — no TTC
    account required. Only valid for VIDEO-scoped share links; download is
    additionally gated by the link's scope."""
    link = _get_valid_link(db, token)
    if link.resource_type != ShareResourceType.VIDEO:
        raise HTTPException(status_code=400, detail="This share link is for a folder, not a single video")

    video = get_video_or_404(db, link.resource_id)
    version = latest_version_or_404(db, video.id)
    record_access(db, link)
    return build_stream_response(
        request, db, video, version, None, "share.view",
        {"share_link_id": str(link.id), "recipient_type": link.recipient_type.value},
    )


@router.get("/share/{token}/download")
def download_shared_video(token: str, request: Request, db: Session = Depends(get_db)) -> StreamingResponse:
    link = _get_valid_link(db, token)
    if link.scope != ShareScope.DOWNLOAD:
        raise HTTPException(status_code=403, detail="This share link is view-only")
    if link.resource_type != ShareResourceType.VIDEO:
        raise HTTPException(status_code=400, detail="This share link is for a folder, not a single video")

    video = get_video_or_404(db, link.resource_id)
    version = latest_version_or_404(db, video.id)
    record_access(db, link)
    response = build_stream_response(
        request, db, video, version, None, "share.download",
        {"share_link_id": str(link.id), "recipient_type": link.recipient_type.value},
    )
    response.headers["Content-Disposition"] = f'attachment; filename="{video.filename}"'
    return response
