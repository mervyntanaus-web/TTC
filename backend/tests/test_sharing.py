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


def test_create_share_link_and_public_metadata_lookup(client, auth_headers, demo_folder, sample_mp4):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    resp = client.post(
        "/share-links",
        headers=auth_headers,
        json={
            "resource_type": "video",
            "resource_id": video["id"],
            "scope": "view_only",
            "recipient_type": "police",
            "recipient_label": "Det. Smith",
        },
    )
    assert resp.status_code == 201, resp.text
    link = resp.json()
    assert link["token"]

    # Public lookup requires no auth headers at all.
    public = client.get(f"/share/{link['token']}")
    assert public.status_code == 200
    assert public.json()["resource_id"] == video["id"]


def test_view_only_link_cannot_download(client, auth_headers, demo_folder, sample_mp4):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    link = client.post(
        "/share-links",
        headers=auth_headers,
        json={"resource_type": "video", "resource_id": video["id"], "scope": "view_only", "recipient_type": "guest"},
    ).json()

    stream = client.get(f"/share/{link['token']}/stream")
    assert stream.status_code == 200

    download = client.get(f"/share/{link['token']}/download")
    assert download.status_code == 403


def test_download_scoped_link_allows_download(client, auth_headers, demo_folder, sample_mp4):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    link = client.post(
        "/share-links",
        headers=auth_headers,
        json={"resource_type": "video", "resource_id": video["id"], "scope": "download", "recipient_type": "court"},
    ).json()

    download = client.get(f"/share/{link['token']}/download")
    assert download.status_code == 200
    assert "attachment" in download.headers["content-disposition"]


def test_revoked_link_is_rejected(client, auth_headers, demo_folder, sample_mp4):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    link = client.post(
        "/share-links",
        headers=auth_headers,
        json={"resource_type": "video", "resource_id": video["id"], "scope": "view_only", "recipient_type": "insurance"},
    ).json()

    revoke = client.post(f"/share-links/{link['id']}/revoke", headers=auth_headers)
    assert revoke.status_code == 200
    assert revoke.json()["revoked"] is True

    resp = client.get(f"/share/{link['token']}")
    assert resp.status_code == 410


def test_expired_link_is_rejected(client, auth_headers, demo_folder, sample_mp4):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    link = client.post(
        "/share-links",
        headers=auth_headers,
        json={
            "resource_type": "video",
            "resource_id": video["id"],
            "scope": "view_only",
            "recipient_type": "foi",
            "expires_in_days": 0,
        },
    ).json()

    resp = client.get(f"/share/{link['token']}")
    assert resp.status_code == 410


def test_access_count_increments(client, auth_headers, demo_folder, sample_mp4):
    video = _upload(client, auth_headers, demo_folder, sample_mp4)
    link = client.post(
        "/share-links",
        headers=auth_headers,
        json={"resource_type": "video", "resource_id": video["id"], "scope": "view_only", "recipient_type": "guest"},
    ).json()

    client.get(f"/share/{link['token']}")
    client.get(f"/share/{link['token']}")

    listed = client.get("/share-links", headers=auth_headers, params={"resource_id": video["id"]}).json()
    assert listed[0]["access_count"] == 2
