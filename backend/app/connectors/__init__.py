from app.connectors.axon import AxonConnector
from app.connectors.base import CameraInfo, RetrievedFootage, VMSConnector
from app.connectors.genetec import GenetecConnector
from app.connectors.march_networks import MarchNetworksConnector
from app.connectors.mock import MockVMSConnector
from app.connectors.sekurflo import SekurfloConnector
from app.connectors.teleste import TelesteConnector

CONNECTOR_REGISTRY: dict[str, type[VMSConnector]] = {
    "mock_vms": MockVMSConnector,
    "genetec_security_center": GenetecConnector,
    "march_networks_command": MarchNetworksConnector,
    "axon_evidence": AxonConnector,
    "teleste": TelesteConnector,
    "sekurflo": SekurfloConnector,
}


def get_connector(name: str) -> VMSConnector:
    try:
        return CONNECTOR_REGISTRY[name]()
    except KeyError as exc:
        raise ValueError(f"Unknown VMS connector '{name}'.") from exc


__all__ = [
    "VMSConnector",
    "CameraInfo",
    "RetrievedFootage",
    "CONNECTOR_REGISTRY",
    "get_connector",
]
