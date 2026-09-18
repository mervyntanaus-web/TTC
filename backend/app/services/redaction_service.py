"""Video/audio redaction rendering. cv2 is imported lazily inside functions
so the rest of the app (and tests that don't exercise actual rendering) can
run without the (large) opencv-contrib-python-headless dependency present."""
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from app.config import get_settings
from app.services.redaction_geometry import (
    active_boxes_at,
    build_mute_audio_filter,
    clip_box_to_frame,
    merge_overlapping_segments,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models.redaction import RedactionJob
    from app.models.video import Video, VideoVersion

settings = get_settings()


class RedactionRenderError(Exception):
    """Raised when a redaction job's ffmpeg/OpenCV rendering step fails."""

DEFAULT_RESERVED_ZONE = {"x": 0, "y": 0, "w": 320, "h": 44}
DEFAULT_BLUR_KSIZE = 51
DEFAULT_SAMPLE_STEP_SECONDS = 0.2


def _cv2():
    import cv2  # noqa: PLC0415

    return cv2


def detect_faces_in_video(video_path: Path, sample_every_seconds: float = 1.0) -> list[dict]:
    """Samples the video every `sample_every_seconds` and runs a Haar-cascade
    face detector on each sampled frame. Returns raw per-frame detections
    (not yet grouped into tracks) for the redaction UI to offer as
    one-click auto-tracking starting points."""
    cv2 = _cv2()
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_step = max(1, round(fps * sample_every_seconds))

    detections: list[dict] = []
    frame_idx = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_idx % frame_step == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
                t = frame_idx / fps
                for x, y, w, h in faces:
                    detections.append({"t": t, "x": float(x), "y": float(y), "w": float(w), "h": float(h)})
            frame_idx += 1
    finally:
        cap.release()
    return detections


def _make_tracker():
    cv2 = _cv2()
    if hasattr(cv2, "legacy") and hasattr(cv2.legacy, "TrackerCSRT_create"):
        return cv2.legacy.TrackerCSRT_create()
    return cv2.TrackerCSRT_create()


def auto_track(
    video_path: Path,
    start_t: float,
    x: float,
    y: float,
    w: float,
    h: float,
    max_seconds: float | None = None,
) -> list[dict]:
    """Runs a CSRT visual tracker forward from a single user-clicked box at
    `start_t`, producing the keyframe track (sampled every
    DEFAULT_SAMPLE_STEP_SECONDS) that redaction rendering later interpolates
    between. This is the "select individual -> system follows person"
    auto-tracking capability."""
    cv2 = _cv2()
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if total_frames else None

    start_frame = int(start_t * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    ok, frame = cap.read()
    if not ok:
        cap.release()
        raise ValueError(f"Could not read frame at t={start_t}s")

    tracker = _make_tracker()
    tracker.init(frame, (x, y, w, h))

    end_t = start_t + max_seconds if max_seconds else (duration or start_t + 3600)
    sample_step_frames = max(1, round(fps * DEFAULT_SAMPLE_STEP_SECONDS))

    track: list[dict] = [{"t": start_t, "x": x, "y": y, "w": w, "h": h}]
    frame_idx = start_frame

    try:
        while True:
            ok, frame = cap.read()
            frame_idx += 1
            if not ok:
                break
            t = frame_idx / fps
            if t > end_t:
                break
            success, bbox = tracker.update(frame)
            if not success:
                break
            if (frame_idx - start_frame) % sample_step_frames == 0:
                bx, by, bw, bh = bbox
                track.append({"t": t, "x": bx, "y": by, "w": bw, "h": bh})
    finally:
        cap.release()

    return track


def render_video_blur(
    source_path: Path,
    dest_video_only_path: Path,
    tracks: list[dict],
    reserved_zone: dict | None = None,
    blur_ksize: int = DEFAULT_BLUR_KSIZE,
) -> None:
    """Renders a silent (video-only) MP4 with the given tracks' regions
    Gaussian-blurred on every frame, except inside `reserved_zone` (default:
    the top-left timestamp overlay area), which is always left untouched so
    burned-in timestamps stay legible after redaction."""
    cv2 = _cv2()
    reserved = reserved_zone or DEFAULT_RESERVED_ZONE
    ksize = blur_ksize if blur_ksize % 2 == 1 else blur_ksize + 1

    cap = cv2.VideoCapture(str(source_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(dest_video_only_path), fourcc, fps, (width, height))

    import numpy as np  # noqa: PLC0415

    rx, ry, rw, rh = reserved["x"], reserved["y"], reserved["w"], reserved["h"]

    frame_idx = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            t = frame_idx / fps
            boxes = active_boxes_at(tracks, t)
            if boxes:
                blurred = cv2.GaussianBlur(frame, (ksize, ksize), 0)
                mask = np.zeros((height, width), dtype=bool)
                for box in boxes:
                    x, y, w, h = clip_box_to_frame(box, width, height)
                    mask[y : y + h, x : x + w] = True
                mask[ry : ry + rh, rx : rx + rw] = False
                frame = np.where(mask[:, :, None], blurred, frame)
            writer.write(frame)
            frame_idx += 1
    finally:
        cap.release()
        writer.release()


def mux_with_audio_redaction(
    video_only_path: Path,
    source_with_audio_path: Path,
    dest_path: Path,
    mute_segments: list[dict] | None = None,
) -> None:
    """Combines a (possibly blurred) video-only stream with the original
    audio, optionally silencing `mute_segments` [{start,end}] ranges."""
    audio_filter = build_mute_audio_filter(merge_overlapping_segments(mute_segments or []))

    cmd = [
        settings.ffmpeg_bin,
        "-y",
        "-i",
        str(video_only_path),
        "-i",
        str(source_with_audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0?",
    ]
    if audio_filter:
        cmd += ["-af", audio_filter]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-shortest", str(dest_path)]
    subprocess.run(cmd, capture_output=True, check=True)


def mute_audio_only(source_path: Path, dest_path: Path, mute_segments: list[dict]) -> None:
    """Fast path for transcript-based / audio-only redaction jobs with no
    visual regions to blur: re-encodes only the audio, copying video as-is."""
    audio_filter = build_mute_audio_filter(merge_overlapping_segments(mute_segments))
    cmd = [settings.ffmpeg_bin, "-y", "-i", str(source_path), "-c:v", "copy"]
    if audio_filter:
        cmd += ["-af", audio_filter, "-c:a", "aac"]
    else:
        cmd += ["-c:a", "copy"]
    cmd += [str(dest_path)]
    subprocess.run(cmd, capture_output=True, check=True)


def new_storage_key(video_id: uuid.UUID, job_id: uuid.UUID, kind: str) -> str:
    return f"videos/{video_id}/{kind}/{job_id}.mp4"


def run_redaction_job(
    db: "Session", job: "RedactionJob", video: "Video", source_version: "VideoVersion"
) -> "VideoVersion":
    """Orchestrates one redaction job end-to-end: downloads the source
    version, renders video-region blurring (if any regions are attached)
    and/or audio muting (if any segments are attached), uploads the result,
    and records it as a new immutable VideoVersion linked back to the job.
    The source version is only ever read, never modified, which is what
    lets a job be re-run against the same source to correct a prior
    redaction without losing history."""
    from app.models.redaction import RedactionJobStatus
    from app.models.video import StorageTier, VideoVersion, VideoVersionKind
    from app.services import storage_service

    job.status = RedactionJobStatus.RUNNING
    db.commit()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ext = Path(source_version.storage_key).suffix or ".mp4"
        source_local = tmp_path / f"source{ext}"
        storage_service.download_to_path(
            source_version.storage_tier, source_version.storage_key, str(source_local)
        )
        output_local = tmp_path / "output.mp4"

        try:
            if job.regions:
                video_only = tmp_path / "video_only.mp4"
                reserved_zone = video.metadata_fields.get("timestamp_overlay_region")
                render_video_blur(source_local, video_only, job.regions, reserved_zone)
                mux_with_audio_redaction(video_only, source_local, output_local, job.audio_segments)
            else:
                mute_audio_only(source_local, output_local, job.audio_segments)
        except Exception as exc:  # noqa: BLE001
            job.status = RedactionJobStatus.FAILED
            job.error_message = str(exc)
            db.commit()
            raise RedactionRenderError(str(exc)) from exc

        dest_key = new_storage_key(video.id, job.id, "redacted")
        storage_service.put_file(StorageTier.HOT, dest_key, str(output_local))

    version = VideoVersion(
        video_id=video.id,
        parent_version_id=source_version.id,
        kind=VideoVersionKind.REDACTED,
        storage_key=dest_key,
        storage_tier=StorageTier.HOT,
        redaction_job_id=job.id,
        created_by=job.created_by,
        notes=f"Redaction job {job.id} ({job.type.value})",
    )
    db.add(version)
    job.status = RedactionJobStatus.COMPLETE
    db.commit()
    db.refresh(version)

    job.result_version_id = version.id
    db.commit()
    return version
