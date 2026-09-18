def test_create_case_and_nested_folders(client, auth_headers):
    case_resp = client.post(
        "/cases", headers=auth_headers, json={"name": "Case A", "retention_category": "standard"}
    )
    assert case_resp.status_code == 201
    case = case_resp.json()

    root_resp = client.post(
        "/folders", headers=auth_headers, json={"case_id": case["id"], "name": "Root"}
    )
    assert root_resp.status_code == 201
    root = root_resp.json()

    child_resp = client.post(
        "/folders",
        headers=auth_headers,
        json={"case_id": case["id"], "parent_id": root["id"], "name": "Subfolder"},
    )
    assert child_resp.status_code == 201

    children = client.get(f"/folders/{root['id']}/children", headers=auth_headers).json()
    assert len(children) == 1
    assert children[0]["name"] == "Subfolder"


def test_search_videos_by_keyword_and_metadata(client, auth_headers, demo_folder, sample_mp4):
    with open(sample_mp4, "rb") as fh:
        client.post(
            "/videos/upload",
            headers=auth_headers,
            data={
                "folder_id": str(demo_folder.id),
                "metadata_fields": '{"suspect_description": "red jacket"}',
            },
            files={"file": ("platform-incident.mp4", fh, "video/mp4")},
        )

    by_keyword = client.get("/search/videos", headers=auth_headers, params={"q": "platform-incident"})
    assert by_keyword.status_code == 200
    assert len(by_keyword.json()) == 1

    by_metadata = client.get(
        "/search/videos",
        headers=auth_headers,
        params={"metadata_field": "suspect_description", "metadata_value": "red jacket"},
    )
    assert len(by_metadata.json()) == 1

    by_case = client.get(
        "/search/videos", headers=auth_headers, params={"case_id": str(demo_folder.case_id)}
    )
    assert len(by_case.json()) == 1

    no_match = client.get("/search/videos", headers=auth_headers, params={"q": "nonexistent-xyz"})
    assert no_match.json() == []
