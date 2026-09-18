import shutil
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.video import StorageTier, Video, VideoStatus, VideoVersion, VideoVersionKind
from app.services import video_pipeline


class UnsupportedVideoFormatError(Exception):
    def __init__(self, fmt: str):
        self.fmt = fmt
        super().__init__(
            f"Format '{fmt}' is not one of TTC's supported formats "
            f"({sorted(video_pipeline.ALL_KNOWN_FORMATS)})."
        )


def ingest_local_file(
    db: Session,
    *,
    folder_id: uuid.UUID,
    local_path: Path,
    filename: str,
    source_connector: str = "manual_upload",
    camera_id: str | None = None,
    uploaded_by: uuid.UUID | None = None,
    metadata_fields: dict | None = None,
    retention_category: str = "standard",
    captured_at: datetime | None = None,
    legal_hold: bool = False,
) -> Video:
    """Shared ingestion path for both manual/bulk upload and automated VMS
    retrieval: validates format, stores the immutable original, probes
    metadata where possible, and records the catalog row + first
    VideoVersion. Raises UnsupportedVideoFormatError for formats TTC does
    not accept at all (i.e. not in the RFP's supported-formats list)."""
    fmt = video_pipeline.format_from_filename(filename)
    if not video_pipeline.is_known_format(fmt):
        raise UnsupportedVideoFormatError(fmt)

    checksum = video_pipeline.sha256_file(local_path)
    size_bytes = local_path.stat().st_size

    video = Video(
        folder_id=folder_id,
        filename=filename,
        format=fmt,
        source_connector=source_connector,
        camera_id=camera_id,
        status=VideoStatus.PROCESSING,
        storage_tier=StorageTier.HOT,
        checksum_sha256=checksum,
        size_bytes=size_bytes,
        captured_at=captured_at,
        uploaded_by=uploaded_by,
        metadata_fields=metadata_fields or {},
        retention_category=retention_category,
        legal_hold=legal_hold,
    )
    db.add(video)
    db.flush()  # assigns video.id without committing yet

    storage_key = video_pipeline.store_original(str(video.id), local_path, fmt)
    version = VideoVersion(
        video_id=video.id,
        parent_version_id=None,
        kind=VideoVersionKind.ORIGINAL,
        storage_key=storage_key,
        storage_tier=StorageTier.HOT,
        created_by=uploaded_by,
        notes="Original ingested file, byte-for-byte as received.",
    )
    db.add(version)

    if video_pipeline.is_native_format(fmt):
        try:
            probe_result = video_pipeline.probe(local_path, fmt)
            video.duration_seconds = probe_result.duration_seconds
            video.status = VideoStatus.READY
        except Exception:  # noqa: BLE001 - probing best-effort, ingestion still succeeds
            video.status = VideoStatus.READY
    else:
        video.status = VideoStatus.NEEDS_VENDOR_DECODER

    db.commit()
    db.refresh(video)
    return video


def stage_upload_to_tmp(upload_bytes_iter, filename: str, tmp_dir: Path) -> Path:
    dest = tmp_dir / filename
    with open(dest, "wb") as fh:
        shutil.copyfileobj(upload_bytes_iter, fh)
    return dest
