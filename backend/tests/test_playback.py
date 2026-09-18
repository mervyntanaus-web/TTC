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


def test_stream_full_video(client, auth_headers, demo_folder, sample_mp4):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    resp = client.get(f"/videos/{video['id']}/stream", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "video/mp4"
    assert len(resp.content) > 0


def test_stream_supports_byte_ranges_for_seeking(client, auth_headers, demo_folder, sample_mp4):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    resp = client.get(
        f"/videos/{video['id']}/stream", headers={**auth_headers, "Range": "bytes=0-999"}
    )
    assert resp.status_code == 206
    assert resp.headers["content-range"].startswith("bytes 0-999/")
    assert len(resp.content) == 1000


def test_versions_lists_original(client, auth_headers, demo_folder, sample_mp4):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    resp = client.get(f"/videos/{video['id']}/versions", headers=auth_headers)
    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) == 1
    assert versions[0]["kind"] == "original"
