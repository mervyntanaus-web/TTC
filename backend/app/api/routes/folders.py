import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_folder_or_404, require_folder_access
from app.db import get_db
from app.models.case import Case
from app.models.folder import Folder, FolderPermission
from app.models.user import User
from app.schemas.folder import (
    CaseCreate,
    CaseOut,
    FolderCreate,
    FolderOut,
    FolderPermissionSet,
    FolderUpdate,
)
from app.security import get_current_user
from app.services.audit_service import log_action

router = APIRouter(tags=["folders"])


@router.post("/cases", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Case:
    case = Case(**payload.model_dump(), created_by=user.id)
    db.add(case)
    db.commit()
    db.refresh(case)
    log_action(db, user, "case.create", "case", case.id, {"name": case.name})
    return case


@router.get("/cases", response_model=list[CaseOut])
def list_cases(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Case]:
    return db.query(Case).order_by(Case.created_at.desc()).all()


@router.get("/cases/{case_id}", response_model=CaseOut)
def get_case(case_id: uuid.UUID, db: Session = Depends(get_db)) -> Case:
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post("/folders", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
def create_folder(
    payload: FolderCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Folder:
    if not db.get(Case, payload.case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    if payload.parent_id and not db.get(Folder, payload.parent_id):
        raise HTTPException(status_code=404, detail="Parent folder not found")

    folder = Folder(
        case_id=payload.case_id,
        parent_id=payload.parent_id,
        name=payload.name,
        metadata_fields=payload.metadata_fields,
        linked_folder_ids=[str(i) for i in payload.linked_folder_ids],
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    log_action(db, user, "folder.create", "folder", folder.id, {"name": folder.name})
    return folder


@router.get("/cases/{case_id}/folders", response_model=list[FolderOut])
def list_case_folders(case_id: uuid.UUID, db: Session = Depends(get_db)) -> list[Folder]:
    return db.query(Folder).filter(Folder.case_id == case_id).order_by(Folder.name).all()


@router.get("/folders/{folder_id}", response_model=FolderOut)
def get_folder(folder: Folder = Depends(require_folder_access("view"))) -> Folder:
    return folder


@router.get("/folders/{folder_id}/children", response_model=list[FolderOut])
def list_children(
    folder: Folder = Depends(require_folder_access("view")), db: Session = Depends(get_db)
) -> list[Folder]:
    return db.query(Folder).filter(Folder.parent_id == folder.id).order_by(Folder.name).all()


@router.patch("/folders/{folder_id}", response_model=FolderOut)
def update_folder(
    payload: FolderUpdate,
    folder: Folder = Depends(require_folder_access("edit")),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Folder:
    updates = payload.model_dump(exclude_unset=True)
    if "linked_folder_ids" in updates and updates["linked_folder_ids"] is not None:
        updates["linked_folder_ids"] = [str(i) for i in updates["linked_folder_ids"]]
    for field, value in updates.items():
        setattr(folder, field, value)
    db.commit()
    db.refresh(folder)
    log_action(db, user, "folder.update", "folder", folder.id, updates)
    return folder


@router.post("/folders/{folder_id}/permissions", status_code=status.HTTP_201_CREATED)
def set_folder_permission(
    payload: FolderPermissionSet,
    folder: Folder = Depends(require_folder_access("edit")),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    perm = FolderPermission(folder_id=folder.id, **payload.model_dump())
    db.add(perm)
    db.commit()
    log_action(
        db, user, "folder.permission.grant", "folder", folder.id, payload.model_dump(mode="json")
    )
    return {"id": str(perm.id)}


@router.get("/folders/{folder_id}/permissions")
def list_folder_permissions(
    folder: Folder = Depends(require_folder_access("view")), db: Session = Depends(get_db)
) -> list[dict]:
    perms = db.query(FolderPermission).filter(FolderPermission.folder_id == folder.id).all()
    return [
        {
            "id": str(p.id),
            "user_id": str(p.user_id) if p.user_id else None,
            "role": p.role,
            "can_view": p.can_view,
            "can_edit": p.can_edit,
            "can_download": p.can_download,
            "can_share": p.can_share,
        }
        for p in perms
    ]
