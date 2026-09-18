from datetime import datetime

from app.connectors.base import CameraInfo, RetrievedFootage, VMSConnector


class GenetecConnector(VMSConnector):
    """Stub for Genetec Security Center integration.

    A real implementation would:
      1. Authenticate via the Genetec SDK / Security Center Web SDK
         (`Sdk.SdkApplication.Initialize` + username/password or Windows auth
         against the Directory).
      2. `list_cameras()` -> enumerate `Camera` entities via
         `Sdk.QueryContext` / the "Query camera list" REST endpoint.
      3. `retrieve_footage()` -> use the Genetec Video Export API (or the
         G64 Export SDK) to export a time range for a camera to a G64/G64x
         (or converted MP4) file, polling the export job until complete.
      4. `protect_source_from_deletion()` -> apply a Genetec "Bookmark" with
         a protection/retention-lock flag via the Bookmark API so archived
         video for that time range isn't purged by the source's own
         retention schedule while under investigation.

    This connector is intentionally not implemented (raises) until TTC
    provisions Security Center API credentials and network access for this
    environment. See docs/architecture.md for the integration checklist.
    """

    name = "genetec_security_center"

    def list_cameras(self) -> list[CameraInfo]:
        raise NotImplementedError(
            "GenetecConnector requires Security Center SDK credentials. "
            "Configure TTC_GENETEC_* settings and implement against the "
            "Security Center Web SDK / native SDK before use."
        )

    def retrieve_footage(
        self, camera_id: str, start: datetime, end: datetime, dest_dir: str
    ) -> RetrievedFootage:
        raise NotImplementedError("See GenetecConnector class docstring.")
