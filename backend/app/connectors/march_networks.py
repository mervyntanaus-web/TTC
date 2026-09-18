from datetime import datetime

from app.connectors.base import CameraInfo, RetrievedFootage, VMSConnector


class MarchNetworksConnector(VMSConnector):
    """Stub for March Networks Command integration.

    A real implementation would:
      1. Authenticate against the Command Enterprise API (REST, token-based).
      2. `list_cameras()` -> `GET /api/devices` / `/api/channels` to enumerate
         recorders and camera channels.
      3. `retrieve_footage()` -> `POST /api/export` (or the legacy Archiver
         export API) for a channel + time range, producing a `.cme` archive,
         then either ship the raw `.cme` (ingested as `needs_vendor_decoder`
         via ProprietaryFormatStub) or convert it first using March Networks'
         `mnConvert`/Command Client Export SDK to MP4.
      4. `protect_source_from_deletion()` -> mark the exported time range as
         "protected" via the Archiver's retention-lock API so it isn't
         cycled out by the recorder's own storage policy.

    Not implemented until TTC provisions March Networks Command API
    credentials for this environment.
    """

    name = "march_networks_command"

    def list_cameras(self) -> list[CameraInfo]:
        raise NotImplementedError(
            "MarchNetworksConnector requires Command Enterprise API "
            "credentials. Configure TTC_MARCH_NETWORKS_* settings."
        )

    def retrieve_footage(
        self, camera_id: str, start: datetime, end: datetime, dest_dir: str
    ) -> RetrievedFootage:
        raise NotImplementedError("See MarchNetworksConnector class docstring.")
