import re
import subprocess
from pathlib import Path

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


def _original_version_id(client, auth_headers, video_id) -> str:
    versions = client.get(f"/videos/{video_id}/versions", headers=auth_headers).json()
    return versions[0]["id"]


def _download_stream(client, auth_headers, video_id, version_id, dest: Path) -> Path:
    resp = client.get(
        f"/videos/{video_id}/stream", headers=auth_headers, params={"version_id": version_id}
    )
    assert resp.status_code == 200, resp.text
    dest.write_bytes(resp.content)
    return dest


def _read_frame(path: Path, at_second: float):
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(at_second * fps))
    ok, frame = cap.read()
    cap.release()
    assert ok, f"could not read frame at t={at_second}"
    return frame


def test_detect_faces_returns_list(client, auth_headers, demo_folder, sample_mp4):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    version_id = _original_version_id(client, auth_headers, video["id"])
    resp = client.post(
        f"/videos/{video['id']}/detect-faces",
        headers=auth_headers,
        json={"version_id": version_id, "sample_every_seconds": 1.0},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_auto_track_produces_a_track(client, auth_headers, demo_folder, sample_mp4):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    version_id = _original_version_id(client, auth_headers, video["id"])
    resp = client.post(
        f"/videos/{video['id']}/auto-track",
        headers=auth_headers,
        json={
            "version_id": version_id,
            "start_t": 0.0,
            "x": 40,
            "y": 40,
            "w": 80,
            "h": 80,
            "label": "person-1",
            "max_seconds": 1.0,
        },
    )
    assert resp.status_code == 200, resp.text
    track = resp.json()
    assert track["track_id"]
    assert len(track["frames"]) >= 1
    assert track["frames"][0]["t"] == 0.0


def test_manual_region_redaction_blurs_video_but_preserves_timestamp_zone(
    client, auth_headers, demo_folder, sample_mp4, tmp_path
):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    original_version_id = _original_version_id(client, auth_headers, video["id"])

    # Cover the whole frame so we can unambiguously check: (a) the body of
    # the frame changed (blurred), and (b) the reserved timestamp zone in
    # the top-left corner did NOT change, per "preserve visible timestamps
    # during redaction".
    resp = client.post(
        f"/videos/{video['id']}/redaction-jobs",
        headers=auth_headers,
        json={
            "video_id": video["id"],
            "source_version_id": original_version_id,
            "type": "manual_region",
            "regions": [
                {
                    "track_id": "t1",
                    "label": "whole-frame",
                    "frames": [
                        {"t": 0.0, "x": 0, "y": 0, "w": 320, "h": 240},
                        {"t": 3.0, "x": 0, "y": 0, "w": 320, "h": 240},
                    ],
                }
            ],
            "audio_segments": [],
        },
    )
    assert resp.status_code == 201, resp.text
    job = resp.json()
    assert job["status"] == "complete"
    assert job["result_version_id"]

    original_path = _download_stream(
        client, auth_headers, video["id"], original_version_id, tmp_path / "orig.mp4"
    )
    redacted_path = _download_stream(
        client, auth_headers, video["id"], job["result_version_id"], tmp_path / "redacted.mp4"
    )

    orig_frame = _read_frame(original_path, 1.0)
    redacted_frame = _read_frame(redacted_path, 1.0)

    # Body of the frame should differ substantially (blurred vs. sharp bars).
    body_diff = np.abs(
        orig_frame[100:200, 100:300].astype(int) - redacted_frame[100:200, 100:300].astype(int)
    ).mean()
    assert body_diff > 5.0, f"expected visible blur difference, got {body_diff}"

    # Reserved timestamp zone (top-left) should be essentially untouched: the
    # mask forces those source pixels through unblurred, so the only
    # difference left is ordinary lossy re-encoding noise, far smaller than
    # the deliberate blur applied to the rest of the frame.
    reserved_diff = np.abs(
        orig_frame[0:40, 0:300].astype(int) - redacted_frame[0:40, 0:300].astype(int)
    ).mean()
    assert reserved_diff < 5.0, f"timestamp zone should stay legible, diff={reserved_diff}"
    assert reserved_diff < body_diff / 3, "timestamp zone changed almost as much as the blurred body"

    versions = client.get(f"/videos/{video['id']}/versions", headers=auth_headers).json()
    assert any(v["kind"] == "redacted" for v in versions)


def _silence_ranges(path: Path, noise_db: str = "-50dB", min_duration: float = 0.1) -> list[tuple[float, float]]:
    """Uses ffmpeg's silencedetect filter to find silent ranges. This is the
    reliable way to verify muting: unlike volumedetect, it isn't fooled by
    output-side -ss/-to trimming (which discards frames after filtering, not
    before) and reports exact silence boundaries directly."""
    cmd = [
        "ffmpeg",
        "-i",
        str(path),
        "-af",
        f"silencedetect=noise={noise_db}:d={min_duration}",
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    starts = [float(m) for m in re.findall(r"silence_start:\s*(-?[\d.]+)", proc.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", proc.stderr)]
    return list(zip(starts, ends))


def test_audio_mute_redaction_silences_segment(client, auth_headers, demo_folder, sample_mp4, tmp_path):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    original_version_id = _original_version_id(client, auth_headers, video["id"])

    assert _silence_ranges(sample_mp4) == [], "fixture's audio should be audible throughout"

    resp = client.post(
        f"/videos/{video['id']}/redaction-jobs",
        headers=auth_headers,
        json={
            "video_id": video["id"],
            "source_version_id": original_version_id,
            "type": "audio_mute",
            "regions": [],
            "audio_segments": [{"start": 0.5, "end": 1.5, "reason": "test"}],
        },
    )
    assert resp.status_code == 201, resp.text
    job = resp.json()
    assert job["status"] == "complete"

    redacted_path = _download_stream(
        client, auth_headers, video["id"], job["result_version_id"], tmp_path / "muted.mp4"
    )
    silences = _silence_ranges(redacted_path)
    assert len(silences) == 1, f"expected exactly one silent range, got {silences}"
    start, end = silences[0]
    assert abs(start - 0.5) < 0.1, f"silence should start ~0.5s, got {start}"
    assert abs(end - 1.5) < 0.1, f"silence should end ~1.5s, got {end}"


def test_publish_disclosure_copy_creates_new_version(client, auth_headers, demo_folder, sample_mp4):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    original_version_id = _original_version_id(client, auth_headers, video["id"])

    resp = client.post(
        f"/videos/{video['id']}/versions/{original_version_id}/publish-disclosure",
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text

    versions = client.get(f"/videos/{video['id']}/versions", headers=auth_headers).json()
    assert any(v["kind"] == "disclosure" for v in versions)
