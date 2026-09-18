from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class CameraInfo:
    camera_id: str
    name: str
    location: str | None = None


@dataclass
class RetrievedFootage:
    camera_id: str
    local_path: str
    filename: str
    format: str
    captured_at: datetime
    checksum_sha256: str


class VMSConnector(ABC):
    """Common interface for pulling footage from a Video Management System.

    A real implementation (Genetec Security Center, March Networks Command,
    Axon Evidence, Teleste, Sekurflo) authenticates to the vendor's API,
    lists cameras, and exports/retrieves a clip for a given camera + time
    range into local storage so it can be ingested into TTC. Automated
    retrieval must preserve the footage from deletion at the source system
    per the RFP's chain-of-custody requirement — real connectors should call
    the vendor's "protect/lock" API on the source recording where available.
    """

    name: str

    @abstractmethod
    def list_cameras(self) -> list[CameraInfo]: ...

    @abstractmethod
    def retrieve_footage(
        self, camera_id: str, start: datetime, end: datetime, dest_dir: str
    ) -> RetrievedFootage: ...

    def protect_source_from_deletion(self, camera_id: str, start: datetime, end: datetime) -> bool:
        """Best-effort call to the vendor's retention-lock/bookmark API so the
        original recording at the source system isn't purged by its own
        retention policy while it's part of an active investigation. Returns
        whether protection was applied; connectors without this capability
        should return False rather than raising."""
        return False
