import hashlib
import subprocess
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from app.config import get_settings
from app.connectors.base import CameraInfo, RetrievedFootage, VMSConnector

settings = get_settings()

MOCK_CAMERAS = [
    CameraInfo("MOCK-CAM-01", "Platform 2 - North", "Union Station"),
    CameraInfo("MOCK-CAM-02", "Platform 2 - South", "Union Station"),
    CameraInfo("MOCK-CAM-BUS-4021", "Onboard Camera", "Bus 4021"),
]


class MockVMSConnector(VMSConnector):
    """Simulated VMS used for demos/tests when no real Genetec/March
    Networks/Axon/Teleste/Sekurflo system is reachable. `retrieve_footage`
    synthesizes a short MP4 clip (via ffmpeg's testsrc) with a burned-in
    timestamp so the rest of the ingestion/playback/redaction pipeline has
    something real to operate on."""

    name = "mock_vms"

    def list_cameras(self) -> list[CameraInfo]:
        return list(MOCK_CAMERAS)

    def retrieve_footage(
        self, camera_id: str, start: datetime, end: datetime, dest_dir: str
    ) -> RetrievedFootage:
        duration = max(1.0, (end - start).total_seconds())
        filename = f"{camera_id}_{start:%Y%m%dT%H%M%S}_{uuid.uuid4().hex[:8]}.mp4"
        dest_path = Path(dest_dir) / filename
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        timestamp_text = start.strftime("%Y-%m-%d %H\\:%M\\:%S")
        cmd = [
            settings.ffmpeg_bin,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size=640x360:rate=15:duration={duration}",
            "-vf",
            f"drawtext=text='{camera_id}  {timestamp_text}':x=10:y=10:fontsize=18:"
            "fontcolor=white:box=1:boxcolor=black@0.5",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(dest_path),
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        checksum = hashlib.sha256(dest_path.read_bytes()).hexdigest()
        return RetrievedFootage(
            camera_id=camera_id,
            local_path=str(dest_path),
            filename=filename,
            format="mp4",
            captured_at=start,
            checksum_sha256=checksum,
        )

    def protect_source_from_deletion(self, camera_id: str, start: datetime, end: datetime) -> bool:
        # The mock VMS has no real retention to protect; report success so
        # the calling flow exercises the "preserved from deletion" audit path.
        return True


def default_time_range(seconds: int = 30) -> tuple[datetime, datetime]:
    end = datetime.utcnow()
    return end - timedelta(seconds=seconds), end
