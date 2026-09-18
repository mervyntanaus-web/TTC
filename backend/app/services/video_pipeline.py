import hashlib
import tempfile
from pathlib import Path

from app.config import get_settings
from app.decoders import ProbeResult, UnsupportedFormatError, get_decoder
from app.models.video import StorageTier
from app.services import storage_service

settings = get_settings()

ALL_KNOWN_FORMATS = set(settings.supported_native_formats) | set(settings.proprietary_formats)


def format_from_filename(filename: str) -> str:
    return Path(filename).suffix.lstrip(".").lower()


def is_known_format(fmt: str) -> bool:
    return fmt in ALL_KNOWN_FORMATS


def is_native_format(fmt: str) -> bool:
    return fmt in settings.supported_native_formats


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def probe(path: Path, fmt: str) -> ProbeResult:
    decoder = get_decoder(fmt)
    return decoder.probe(path)


def store_original(video_id: str, local_path: Path, fmt: str) -> str:
    """Uploads the untouched source bytes to hot storage and returns the
    storage key. This copy is never re-encoded — it's the evidentiary
    original that redaction/versioning always keeps alongside derived
    versions."""
    key = f"videos/{video_id}/original.{fmt}"
    storage_service.put_file(StorageTier.HOT, key, str(local_path))
    return key


def ensure_playable_mp4(video_id: str, source_key: str, fmt: str) -> str:
    """Returns a storage key for an MP4 that browsers/OpenCV can consume.
    Native formats still get container-normalized to MP4 for consistent
    streaming/seeking; proprietary formats raise UnsupportedFormatError."""
    if fmt == "mp4":
        return source_key

    decoder = get_decoder(fmt)
    with tempfile.TemporaryDirectory() as tmp:
        src_path = Path(tmp) / f"source.{fmt}"
        storage_service.download_to_path(StorageTier.HOT, source_key, str(src_path))

        dest_path = Path(tmp) / "playable.mp4"
        decoder.transcode_to_mp4(src_path, dest_path)

        playable_key = f"videos/{video_id}/playable.mp4"
        storage_service.put_file(StorageTier.HOT, playable_key, str(dest_path))
        return playable_key


__all__ = [
    "ProbeResult",
    "UnsupportedFormatError",
    "format_from_filename",
    "is_known_format",
    "is_native_format",
    "sha256_file",
    "probe",
    "store_original",
    "ensure_playable_mp4",
]
