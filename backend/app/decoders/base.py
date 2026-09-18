from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProbeResult:
    format: str
    duration_seconds: float | None
    width: int | None
    height: int | None
    has_audio: bool
    codec: str | None = None


class VideoDecoder(ABC):
    """Common interface for turning a source video file into a browser- and
    OpenCV-friendly MP4 (h264/aac), and for probing its metadata. Real
    formats (mp4/avi/mkv/mpeg) are handled by FfmpegDecoder; TTC's
    proprietary VMS export formats (CME, G64x) need vendor SDKs and are
    represented by ProprietaryFormatStub until one is integrated."""

    @abstractmethod
    def probe(self, source_path: Path) -> ProbeResult: ...

    @abstractmethod
    def transcode_to_mp4(self, source_path: Path, dest_path: Path) -> None: ...

    @abstractmethod
    def can_handle(self, extension: str) -> bool: ...


class UnsupportedFormatError(Exception):
    """Raised when a decoder cannot process a given format, e.g. a
    proprietary VMS export format without an integrated vendor SDK."""
