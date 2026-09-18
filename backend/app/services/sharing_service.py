from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.share import ShareLink


class ShareLinkInvalid(Exception):
    """Raised when a share token is unknown, revoked, or expired."""


def resolve_share_link(db: Session, token: str) -> ShareLink:
    link = db.query(ShareLink).filter(ShareLink.token == token).first()
    if not link:
        raise ShareLinkInvalid("Unknown share link")
    if link.revoked:
        raise ShareLinkInvalid("This share link has been revoked")
    if link.expires_at and datetime.utcnow() > link.expires_at:
        raise ShareLinkInvalid("This share link has expired")
    return link


def record_access(db: Session, link: ShareLink) -> None:
    link.access_count += 1
    link.last_accessed_at = datetime.utcnow()
    db.commit()


def default_expiry(days: int = 7) -> datetime:
    return datetime.utcnow() + timedelta(days=days)
