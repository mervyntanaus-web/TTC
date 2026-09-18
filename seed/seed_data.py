"""Idempotent demo data seeder for TTC.

Creates demo users (one per role), a demo case with nested folders, and
registers the mock VMS connector's simulated cameras. Safe to re-run.

Usage: python -m seed.seed_data   (run from the backend's environment, with
PYTHONPATH including backend/ so `app.*` imports resolve)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models.case import Case  # noqa: E402
from app.models.folder import Folder  # noqa: E402
from app.models.retention import RetentionPolicy  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.security import hash_password  # noqa: E402

DEMO_USERS = [
    ("Alice Admin", "admin@ttc.demo", UserRole.ADMIN),
    ("Sam Staff", "staff@ttc.demo", UserRole.STAFF),
    ("Lee Legal", "legal@ttc.demo", UserRole.LEGAL),
    ("Ivy Investigator", "investigator@ttc.demo", UserRole.INVESTIGATOR),
    ("Gary Guest", "guest@ttc.demo", UserRole.EXTERNAL),
]
DEMO_PASSWORD = "demo-password-123"

RETENTION_POLICIES = [
    ("standard", 365, False, 90),
    ("major_incident", 365 * 7, False, 30),
    ("litigation_hold", 365 * 10, False, None),
    ("routine_cctv", 30, True, 7),
]


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for name, email, role in DEMO_USERS:
            if not db.query(User).filter(User.email == email).first():
                db.add(
                    User(
                        name=name,
                        email=email,
                        hashed_password=hash_password(DEMO_PASSWORD),
                        role=role,
                    )
                )
        db.commit()

        for category, days, auto_delete, archive_after in RETENTION_POLICIES:
            if not db.query(RetentionPolicy).filter(RetentionPolicy.category == category).first():
                db.add(
                    RetentionPolicy(
                        category=category,
                        retention_days=days,
                        auto_delete=auto_delete,
                        auto_archive_after_days=archive_after,
                    )
                )
        db.commit()

        case = db.query(Case).filter(Case.name == "Demo Case 2026-001").first()
        if not case:
            case = Case(
                name="Demo Case 2026-001",
                description="Seeded demo case for the TTC DEMS video workflow walkthrough.",
                retention_category="major_incident",
                metadata_fields={"incident_type": "assault", "station": "Union"},
            )
            db.add(case)
            db.commit()
            db.refresh(case)

        root = db.query(Folder).filter(Folder.case_id == case.id, Folder.parent_id.is_(None)).first()
        if not root:
            root = Folder(case_id=case.id, parent_id=None, name="Evidence", metadata_fields={})
            db.add(root)
            db.commit()
            db.refresh(root)
            db.add(
                Folder(
                    case_id=case.id,
                    parent_id=root.id,
                    name="Platform CCTV",
                    metadata_fields={"location": "Platform 2"},
                )
            )
            db.add(
                Folder(
                    case_id=case.id,
                    parent_id=root.id,
                    name="Bus Camera Footage",
                    metadata_fields={"vehicle": "Bus 4021"},
                )
            )
            db.commit()

        print("Seed complete.")
        print(f"  Demo users (password: {DEMO_PASSWORD}):")
        for name, email, role in DEMO_USERS:
            print(f"    {email}  ({role.value})")
        print(f"  Demo case: {case.name} ({case.id})")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
