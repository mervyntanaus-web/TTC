from app.models.video import VideoStatus


def test_upload_native_format_ingests_and_probes(client, auth_headers, demo_folder, sample_mp4):
    with open(sample_mp4, "rb") as fh:
        resp = client.post(
            "/videos/upload",
            headers=auth_headers,
            data={"folder_id": str(demo_folder.id), "metadata_fields": '{"note":"test"}'},
            files={"file": ("clip.mp4", fh, "video/mp4")},
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == VideoStatus.READY.value
    assert body["format"] == "mp4"
    assert body["duration_seconds"] and body["duration_seconds"] > 0
    assert body["checksum_sha256"] and len(body["checksum_sha256"]) == 64
    assert body["metadata_fields"] == {"note": "test"}


def test_upload_proprietary_format_flags_needs_vendor_decoder(client, auth_headers, demo_folder, sample_mp4):
    # Same bytes, but named with a proprietary extension TTC's legacy VMS
    # systems export (Genetec G64x) - should still be accepted/stored, not
    # rejected, per the RFP's "preserve footage" requirement.
    with open(sample_mp4, "rb") as fh:
        resp = client.post(
            "/videos/upload",
            headers=auth_headers,
            data={"folder_id": str(demo_folder.id)},
            files={"file": ("export.g64x", fh, "application/octet-stream")},
        )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == VideoStatus.NEEDS_VENDOR_DECODER.value


def test_upload_unknown_format_rejected(client, auth_headers, demo_folder, sample_mp4):
    with open(sample_mp4, "rb") as fh:
        resp = client.post(
            "/videos/upload",
            headers=auth_headers,
            data={"folder_id": str(demo_folder.id)},
            files={"file": ("clip.xyz", fh, "application/octet-stream")},
        )
    assert resp.status_code == 400


def test_bulk_upload_multiple_files(client, auth_headers, demo_folder, sample_mp4):
    with open(sample_mp4, "rb") as fh1, open(sample_mp4, "rb") as fh2:
        resp = client.post(
            "/videos/bulk-upload",
            headers=auth_headers,
            data={"folder_id": str(demo_folder.id)},
            files=[
                ("files", ("a.mp4", fh1, "video/mp4")),
                ("files", ("b.mp4", fh2, "video/mp4")),
            ],
        )
    assert resp.status_code == 201, resp.text
    assert len(resp.json()) == 2


def test_upload_requires_folder_edit_permission(client, db_session, tmp_path, monkeypatch):
    from app.models.case import Case
    from app.models.folder import Folder
    from app.models.user import User, UserRole
    from app.security import hash_password

    case = Case(name="Restricted Case")
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    folder = Folder(case_id=case.id, parent_id=None, name="Locked")
    db_session.add(folder)
    external = User(
        name="Outside Party",
        email="outside@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.EXTERNAL,
    )
    db_session.add(external)
    db_session.commit()
    db_session.refresh(folder)

    login = client.post("/auth/login", json={"email": "outside@example.com", "password": "password123"})
    token = login.json()["access_token"]

    resp = client.post(
        "/videos/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"folder_id": str(folder.id)},
        files={"file": ("clip.mp4", b"not-a-real-file", "video/mp4")},
    )
    assert resp.status_code == 403
