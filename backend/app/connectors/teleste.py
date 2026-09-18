from datetime import datetime

from app.connectors.base import CameraInfo, RetrievedFootage, VMSConnector


class TelesteConnector(VMSConnector):
    """Stub for Teleste (rail/transit onboard CCTV) integration.

    A real implementation would:
      1. Authenticate against the Teleste MDS/onboard recorder management
         API (typically deployed per-vehicle, synced to a depot server).
      2. `list_cameras()` -> query the depot management server for
         vehicle/camera inventory (Teleste systems are usually keyed by
         vehicle ID + camera position rather than a flat camera list).
      3. `retrieve_footage()` -> request an export from the onboard
         recorder or depot server for a vehicle + time range; Teleste
         exports are commonly AVI/MP4 already, simplifying decoding.
      4. `protect_source_from_deletion()` -> Teleste onboard recorders
         typically use ring-buffer storage; this would mark the export job's
         source segment as retained so the ring buffer doesn't overwrite it
         before the export completes and syncs to the depot server.

    Not implemented until TTC provisions Teleste depot/API access for this
    environment.
    """

    name = "teleste"

    def list_cameras(self) -> list[CameraInfo]:
        raise NotImplementedError(
            "TelesteConnector requires depot server API access. Configure "
            "TTC_TELESTE_* settings."
        )

    def retrieve_footage(
        self, camera_id: str, start: datetime, end: datetime, dest_dir: str
    ) -> RetrievedFootage:
        raise NotImplementedError("See TelesteConnector class docstring.")
