from datetime import datetime

from app.connectors.base import CameraInfo, RetrievedFootage, VMSConnector


class AxonConnector(VMSConnector):
    """Stub for Axon Evidence (Evidence.com) integration.

    A real implementation would:
      1. Authenticate via the Axon Evidence Partner API (OAuth2 client
         credentials).
      2. `list_cameras()` -> Axon Evidence is device/upload-centric rather
         than live-camera-centric (body cams, fleet, interview room); this
         would enumerate registered devices/agencies via the Partner API.
      3. `retrieve_footage()` -> `GET /evidence/{id}/media` on the Axon
         Partner API to pull a specific evidence item's video file directly
         (Axon evidence is typically already MP4).
      4. `protect_source_from_deletion()` -> Axon Evidence enforces its own
         retention categories tied to evidence records; this would call the
         Partner API to attach/extend a retention category or legal hold
         flag on the source evidence item.

    Not implemented until TTC provisions Axon Evidence Partner API
    credentials for this environment.
    """

    name = "axon_evidence"

    def list_cameras(self) -> list[CameraInfo]:
        raise NotImplementedError(
            "AxonConnector requires Axon Evidence Partner API credentials. "
            "Configure TTC_AXON_* settings."
        )

    def retrieve_footage(
        self, camera_id: str, start: datetime, end: datetime, dest_dir: str
    ) -> RetrievedFootage:
        raise NotImplementedError("See AxonConnector class docstring.")
