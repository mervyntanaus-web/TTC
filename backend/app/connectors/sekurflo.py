from datetime import datetime

from app.connectors.base import CameraInfo, RetrievedFootage, VMSConnector


class SekurfloConnector(VMSConnector):
    """Stub for Sekurflo integration.

    Sekurflo is a smaller/regional VMS vendor with no widely-published
    public API reference at the time of writing. A real implementation
    would need to obtain Sekurflo's integration/API documentation from the
    vendor directly, but the shape should follow the same pattern as the
    other connectors:
      1. Authenticate to the Sekurflo management server.
      2. `list_cameras()` -> enumerate cameras/sites from their management API.
      3. `retrieve_footage()` -> request/export a clip for a camera + time
         range, converting to MP4 if Sekurflo exports a proprietary
         container.
      4. `protect_source_from_deletion()` -> apply whatever retention-lock
         mechanism Sekurflo exposes, if any.

    Not implemented — contact Sekurflo for API/SDK access before building
    this connector for real.
    """

    name = "sekurflo"

    def list_cameras(self) -> list[CameraInfo]:
        raise NotImplementedError(
            "SekurfloConnector requires vendor API documentation and "
            "credentials that TTC has not yet provided/obtained."
        )

    def retrieve_footage(
        self, camera_id: str, start: datetime, end: datetime, dest_dir: str
    ) -> RetrievedFootage:
        raise NotImplementedError("See SekurfloConnector class docstring.")
