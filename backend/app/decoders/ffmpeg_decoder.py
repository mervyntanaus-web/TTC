import json
import subprocess
from pathlib import Path

from app.config import get_settings
from app.decoders.base import ProbeResult, VideoDecoder

settings = get_settings()


class FfmpegDecoder(VideoDecoder):
    """Handles TTC's mainstream formats (MP4, AVI, MKV, MPEG-4/MPG) via the
    ffmpeg/ffprobe CLI. Requires the `ffmpeg` package to be installed on the
    host/container (see backend/Dockerfile)."""

    def can_handle(self, extension: str) -> bool:
        return extension.lower().lstrip(".") in settings.supported_native_formats

    def probe(self, source_path: Path) -> ProbeResult:
        cmd = [
            settings.ffprobe_bin,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(source_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(proc.stdout)

        video_stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "video"), None
        )
        has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
        duration = None
        fmt = data.get("format", {})
        if fmt.get("duration"):
            duration = float(fmt["duration"])

        return ProbeResult(
            format=fmt.get("format_name", source_path.suffix.lstrip(".")),
            duration_seconds=duration,
            width=video_stream.get("width") if video_stream else None,
            height=video_stream.get("height") if video_stream else None,
            has_audio=has_audio,
            codec=video_stream.get("codec_name") if video_stream else None,
        )

    def transcode_to_mp4(self, source_path: Path, dest_path: Path) -> None:
        cmd = [
            settings.ffmpeg_bin,
            "-y",
            "-i",
            str(source_path),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(dest_path),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
