import uuid
from datetime import datetime, timedelta

from app.models.retention import RetentionPolicy
from app.models.user import User, UserRole
from app.security import hash_password
from app.services import retention_service


def _upload(client, auth_headers, demo_folder, sample_mp4):
    with open(sample_mp4, "rb") as fh:
        resp = client.post(
            "/videos/upload",
            headers=auth_headers,
            data={"folder_id": str(demo_folder.id)},
            files={"file": ("clip.mp4", fh, "video/mp4")},
        )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _admin_headers(client, db_session, email="admin@example.com"):
    admin = User(name="Admin", email=email, hashed_password=hash_password("pw"), role=UserRole.ADMIN)
    db_session.add(admin)
    db_session.commit()
    token = client.post("/auth/login", json={"email": email, "password": "pw"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_archive_and_restore_round_trip(client, auth_headers, demo_folder, sample_mp4):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)

    archived = client.post(f"/videos/{video['id']}/archive", headers=auth_headers)
    assert archived.status_code == 200, archived.text
    assert archived.json()["tier"] == "cold"

    # File should still be streamable after archival (fake storage backend
    # actually relocates bytes, same as a real hot/cold tier move).
    stream = client.get(f"/videos/{video['id']}/stream", headers=auth_headers)
    assert stream.status_code == 200

    restored = client.post(f"/videos/{video['id']}/restore", headers=auth_headers)
    assert restored.status_code == 200
    assert restored.json()["tier"] == "hot"
    assert restored.json()["restore_eta"] is not None

    events = client.get(f"/videos/{video['id']}/storage-tier-events", headers=auth_headers).json()
    assert len(events) == 2


def test_cannot_archive_already_archived_video(client, auth_headers, demo_folder, sample_mp4):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    client.post(f"/videos/{video['id']}/archive", headers=auth_headers)
    resp = client.post(f"/videos/{video['id']}/archive", headers=auth_headers)
    assert resp.status_code == 400


def test_legal_hold_blocks_retention_sweep_deletion(client, auth_headers, demo_folder, sample_mp4, db_session):
    from app.models.case import Case

    case = db_session.query(Case).filter(Case.id == demo_folder.case_id).first()
    case.retention_category = "short_lived"
    db_session.add(RetentionPolicy(category="short_lived", retention_days=1, auto_delete=True))
    db_session.commit()

    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    from app.models.video import Video

    video_row = db_session.query(Video).filter(Video.id == uuid.UUID(video["id"])).first()
    video_row.retention_category = "short_lived"
    video_row.uploaded_at = datetime.utcnow() - timedelta(days=5)
    video_row.legal_hold = True
    db_session.commit()

    result = retention_service.run_sweep(db_session, now=datetime.utcnow())
    assert video_row.id not in result.deleted

    db_session.refresh(video_row)
    assert video_row.status.value != "deleted"


def test_retention_sweep_deletes_expired_video_and_preserves_metadata(
    client, auth_headers, demo_folder, sample_mp4, db_session
):
    db_session.add(RetentionPolicy(category="short_lived2", retention_days=1, auto_delete=True))
    db_session.commit()

    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    from app.models.video import Video

    video_row = db_session.query(Video).filter(Video.id == uuid.UUID(video["id"])).first()
    video_row.retention_category = "short_lived2"
    video_row.uploaded_at = datetime.utcnow() - timedelta(days=5)
    original_metadata = {"note": "keep me"}
    video_row.metadata_fields = original_metadata
    db_session.commit()

    result = retention_service.run_sweep(db_session, now=datetime.utcnow())
    assert video_row.id in result.deleted

    db_session.refresh(video_row)
    assert video_row.status.value == "deleted"
    assert video_row.deleted_at is not None
    assert video_row.metadata_fields == original_metadata  # tombstone keeps metadata

    # Underlying bytes are gone; streaming should now fail cleanly.
    resp = client.get(f"/videos/{video['id']}/stream", headers=auth_headers)
    assert resp.status_code == 404


def test_retention_sweep_archives_after_threshold(client, auth_headers, demo_folder, sample_mp4, db_session):
    db_session.add(
        RetentionPolicy(category="archive_soon", retention_days=3650, auto_delete=False, auto_archive_after_days=2)
    )
    db_session.commit()

    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    from app.models.video import Video

    video_row = db_session.query(Video).filter(Video.id == uuid.UUID(video["id"])).first()
    video_row.retention_category = "archive_soon"
    video_row.uploaded_at = datetime.utcnow() - timedelta(days=5)
    db_session.commit()

    result = retention_service.run_sweep(db_session, now=datetime.utcnow())
    assert video_row.id in result.archived

    db_session.refresh(video_row)
    assert video_row.storage_tier.value == "cold"


def test_run_sweep_endpoint_requires_admin(client, auth_headers):
    resp = client.post("/retention/run-sweep", headers=auth_headers)
    assert resp.status_code == 403


def test_run_sweep_endpoint_succeeds_for_admin(client, db_session):
    headers = _admin_headers(client, db_session)
    resp = client.post("/retention/run-sweep", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"archived": [], "deleted": []}


def test_legal_hold_endpoint(client, auth_headers, demo_folder, sample_mp4):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    resp = client.post(f"/videos/{video['id']}/legal-hold", headers=auth_headers, json={"legal_hold": True})
    assert resp.status_code == 200
    assert resp.json()["legal_hold"] is True
    assert resp.json()["eligible_for_deletion"] is False
