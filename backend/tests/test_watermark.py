import cv2
import numpy as np


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


def test_set_and_get_global_watermark_requires_admin(client, db_session, demo_folder):
    from app.models.user import User, UserRole
    from app.security import hash_password

    admin = User(name="Admin", email="admin@example.com", hashed_password=hash_password("pw"), role=UserRole.ADMIN)
    db_session.add(admin)
    db_session.commit()
    token = client.post("/auth/login", json={"email": "admin@example.com", "password": "pw"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.put(
        "/watermarks/global",
        headers=headers,
        json={"template": "{viewer_name} - {timestamp}", "enabled_for_playback": True, "enabled_for_export": True},
    )
    assert resp.status_code == 200, resp.text

    got = client.get("/watermarks/global", headers=headers)
    assert got.json()["template"] == "{viewer_name} - {timestamp}"


def test_non_admin_cannot_set_global_watermark(client, auth_headers):
    resp = client.put(
        "/watermarks/global",
        headers=auth_headers,
        json={"template": "x", "enabled_for_playback": True, "enabled_for_export": True},
    )
    assert resp.status_code == 403


def test_publish_disclosure_burns_in_watermark_when_configured(
    client, auth_headers, demo_folder, sample_mp4, tmp_path, db_session
):
    from app.models.user import User, UserRole
    from app.security import hash_password

    admin = User(name="Admin", email="admin2@example.com", hashed_password=hash_password("pw"), role=UserRole.ADMIN)
    db_session.add(admin)
    db_session.commit()
    admin_token = client.post(
        "/auth/login", json={"email": "admin2@example.com", "password": "pw"}
    ).json()["access_token"]
    client.put(
        "/watermarks/global",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"template": "{viewer_name}", "enabled_for_playback": True, "enabled_for_export": True},
    )

    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    versions = client.get(f"/videos/{video['id']}/versions", headers=auth_headers).json()
    original_version_id = versions[0]["id"]

    resp = client.post(
        f"/videos/{video['id']}/versions/{original_version_id}/publish-disclosure",
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text

    versions = client.get(f"/videos/{video['id']}/versions", headers=auth_headers).json()
    disclosure = next(v for v in versions if v["kind"] == "disclosure")
    assert disclosure["watermark_applied"] is True

    # Bottom-right corner (where the watermark is drawn) should visibly
    # differ from the original; the rest of the frame should look similar.
    orig_resp = client.get(
        f"/videos/{video['id']}/stream", headers=auth_headers, params={"version_id": original_version_id}
    )
    (tmp_path / "orig.mp4").write_bytes(orig_resp.content)
    disc_resp = client.get(
        f"/videos/{video['id']}/stream", headers=auth_headers, params={"version_id": disclosure["id"]}
    )
    (tmp_path / "disc.mp4").write_bytes(disc_resp.content)

    def read_frame(path):
        cap = cv2.VideoCapture(str(path))
        ok, frame = cap.read()
        cap.release()
        assert ok
        return frame

    orig_frame = read_frame(tmp_path / "orig.mp4")
    disc_frame = read_frame(tmp_path / "disc.mp4")
    h, w = orig_frame.shape[:2]
    corner_diff = np.abs(
        orig_frame[h - 30 : h, w - 120 : w].astype(int) - disc_frame[h - 30 : h, w - 120 : w].astype(int)
    ).mean()
    assert corner_diff > 5.0, f"expected visible watermark in bottom-right corner, diff={corner_diff}"


def test_publish_disclosure_without_watermark_configured_just_copies(client, auth_headers, demo_folder, sample_mp4):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    versions = client.get(f"/videos/{video['id']}/versions", headers=auth_headers).json()
    original_version_id = versions[0]["id"]

    resp = client.post(
        f"/videos/{video['id']}/versions/{original_version_id}/publish-disclosure",
        headers=auth_headers,
        params={"apply_watermark": False},
    )
    assert resp.status_code == 201

    versions = client.get(f"/videos/{video['id']}/versions", headers=auth_headers).json()
    disclosure = next(v for v in versions if v["kind"] == "disclosure")
    assert disclosure["watermark_applied"] is False
