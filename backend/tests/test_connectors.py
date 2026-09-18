from datetime import datetime, timedelta

from app.connectors.mock import MockVMSConnector


def test_mock_connector_lists_cameras():
    connector = MockVMSConnector()
    cameras = connector.list_cameras()
    assert len(cameras) >= 1
    assert all(c.camera_id for c in cameras)


def test_mock_connector_retrieves_real_clip(tmp_path):
    connector = MockVMSConnector()
    start = datetime.utcnow() - timedelta(seconds=5)
    end = datetime.utcnow()
    footage = connector.retrieve_footage("MOCK-CAM-01", start, end, str(tmp_path))

    assert footage.format == "mp4"
    local_path = tmp_path / footage.filename
    assert local_path.exists()
    assert local_path.stat().st_size > 0
    assert len(footage.checksum_sha256) == 64


def test_mock_connector_protects_source():
    connector = MockVMSConnector()
    assert connector.protect_source_from_deletion("MOCK-CAM-01", datetime.utcnow(), datetime.utcnow())
