from pathlib import Path

import pytest

from app.services import transcription_service


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


def _original_version_id(client, auth_headers, video_id) -> str:
    versions = client.get(f"/videos/{video_id}/versions", headers=auth_headers).json()
    return versions[0]["id"]


@pytest.fixture()
def fake_transcribe(monkeypatch):
    """Stubs the ASR model call itself (heavy to download/run in CI/sandbox)
    while exercising the real generate/edit/apply-redaction request flow and
    the real ffmpeg audio muting underneath it."""

    def _fake(path: Path):
        return (
            [
                {"id": "s1", "start": 0.2, "end": 0.9, "text": "hello there", "speaker": None, "redacted": False},
                {"id": "s2", "start": 1.2, "end": 1.9, "text": "my name is Alex", "speaker": None, "redacted": False},
                {"id": "s3", "start": 2.2, "end": 2.8, "text": "goodbye", "speaker": None, "redacted": False},
            ],
            "en",
        )

    monkeypatch.setattr(transcription_service, "transcribe", _fake)


def test_generate_transcript(client, auth_headers, demo_folder, sample_mp4, fake_transcribe):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    version_id = _original_version_id(client, auth_headers, video["id"])

    resp = client.post(
        f"/videos/{video['id']}/transcript/generate",
        headers=auth_headers,
        json={"version_id": version_id},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body["segments"]) == 3
    assert body["language"] == "en"


def test_edit_and_redact_segment(client, auth_headers, demo_folder, sample_mp4, fake_transcribe):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    version_id = _original_version_id(client, auth_headers, video["id"])
    client.post(
        f"/videos/{video['id']}/transcript/generate",
        headers=auth_headers,
        json={"version_id": version_id},
    )

    resp = client.patch(
        f"/videos/{video['id']}/transcript/segments/s2",
        headers=auth_headers,
        json={"redacted": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["edited"] is True
    segment = next(s for s in body["segments"] if s["id"] == "s2")
    assert segment["redacted"] is True


def test_apply_transcript_redactions_mutes_marked_segments(
    client, auth_headers, demo_folder, sample_mp4, fake_transcribe
):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    version_id = _original_version_id(client, auth_headers, video["id"])
    client.post(
        f"/videos/{video['id']}/transcript/generate",
        headers=auth_headers,
        json={"version_id": version_id},
    )
    client.patch(
        f"/videos/{video['id']}/transcript/segments/s2",
        headers=auth_headers,
        json={"redacted": True},
    )

    resp = client.post(
        f"/videos/{video['id']}/transcript/apply-redactions",
        headers=auth_headers,
        params={"source_version_id": version_id},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["job_id"]
    assert body["result_version_id"]

    job_resp = client.get(f"/redaction-jobs/{body['job_id']}", headers=auth_headers)
    assert job_resp.json()["type"] == "transcript_based_audio"
    assert job_resp.json()["status"] == "complete"


def test_apply_transcript_redactions_requires_a_redacted_segment(
    client, auth_headers, demo_folder, sample_mp4, fake_transcribe
):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    version_id = _original_version_id(client, auth_headers, video["id"])
    client.post(
        f"/videos/{video['id']}/transcript/generate",
        headers=auth_headers,
        json={"version_id": version_id},
    )

    resp = client.post(
        f"/videos/{video['id']}/transcript/apply-redactions",
        headers=auth_headers,
        params={"source_version_id": version_id},
    )
    assert resp.status_code == 400
