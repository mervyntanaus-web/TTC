import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.folder import Folder, FolderPermission
from app.models.user import User, UserRole
from app.security import get_current_user


def _permission_for(db: Session, folder: Folder, user: User) -> FolderPermission | None:
    return (
        db.query(FolderPermission)
        .filter(
            FolderPermission.folder_id == folder.id,
            (FolderPermission.user_id == user.id) | (FolderPermission.role == user.role.value),
        )
        .order_by(FolderPermission.user_id.is_(None))  # user-specific grant wins over role grant
        .first()
    )


def get_folder_or_404(folder_id: uuid.UUID, db: Session = Depends(get_db)) -> Folder:
    folder = db.get(Folder, folder_id)
    if folder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    return folder


def require_folder_access(action: str = "view"):
    """FastAPI dependency factory enforcing folder-level ACLs. Admins and
    staff always pass (staff are TTC's internal baseline role); everyone
    else needs an explicit FolderPermission granting the requested action.
    No matching permission row defaults to view-only access denied, i.e.
    fail closed."""

    def _dependency(
        folder: Folder = Depends(get_folder_or_404),
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> Folder:
        if user.role in (UserRole.ADMIN, UserRole.STAFF):
            return folder

        perm = _permission_for(db, folder, user)
        allowed = bool(perm) and getattr(perm, f"can_{action}", False)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing '{action}' permission on this folder",
            )
        return folder

    return _dependency
