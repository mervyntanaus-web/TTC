def _upload(client, auth_headers, demo_folder, sample_mp4):
    with open(sample_mp4, "rb") as fh:
        resp = client.post(
            "/videos/upload",
            headers=auth_headers,
            data={"folder_id": str(demo_folder.id)},
            files={"file": ("clip.mp4", fh, "video/mp4")},
        )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_chain_of_custody_records_upload_and_view(client, auth_headers, demo_folder, sample_mp4):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    client.get(f"/videos/{video['id']}/stream", headers=auth_headers)

    log = client.get(f"/audit/videos/{video['id']}/chain-of-custody", headers=auth_headers)
    assert log.status_code == 200
    actions = [entry["action"] for entry in log.json()]
    assert "video.upload.manual" in actions
    assert "video.view" in actions
    # Chronological order (upload before view).
    assert actions.index("video.upload.manual") < actions.index("video.view")


def test_audit_export_csv(client, auth_headers, demo_folder, sample_mp4):
    _upload(client, auth_headers, demo_folder, sample_mp4)
    resp = client.get("/audit/export", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "video.upload.manual" in resp.text


def test_reports_inventory_and_storage_utilization(client, auth_headers, demo_folder, sample_mp4):
    _upload(client, auth_headers, demo_folder, sample_mp4)

    inventory = client.get("/reports/inventory", headers=auth_headers).json()
    assert inventory["total_videos"] >= 1
    assert inventory["by_format"].get("mp4", 0) >= 1

    utilization = client.get("/reports/storage-utilization", headers=auth_headers).json()
    assert "hot" in utilization
    assert utilization["hot"]["count"] >= 1


def test_reports_investigation_workload(client, auth_headers, demo_folder, sample_mp4, db_session):
    _upload(client, auth_headers, demo_folder, sample_mp4)
    rows = client.get("/reports/investigation-workload", headers=auth_headers).json()
    assert any(r["video_count"] >= 1 for r in rows)


def test_reports_redaction_workload_empty_when_no_jobs(client, auth_headers):
    workload = client.get("/reports/redaction-workload", headers=auth_headers).json()
    assert workload["by_type"] == {}
