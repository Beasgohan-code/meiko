
async def test_conversation_crud_lifecycle(app_client):
    # create
    resp = await app_client.post("/api/conversations", json={"user_id": "alice", "title": "hi"})
    assert resp.status_code == 200
    conv_id = resp.json()["conversation_id"]

    # list
    resp = await app_client.get("/api/conversations", params={"user_id": "alice"})
    assert resp.status_code == 200
    assert any(c["id"] == conv_id for c in resp.json())

    # rename
    resp = await app_client.patch(f"/api/conversations/{conv_id}", json={"title": "renamed"})
    assert resp.status_code == 200
    resp = await app_client.get("/api/conversations", params={"user_id": "alice"})
    assert any(c["id"] == conv_id and c["title"] == "renamed" for c in resp.json())

    # search matches title
    resp = await app_client.get("/api/conversations/search", params={"user_id": "alice", "q": "rename"})
    assert resp.status_code == 200
    assert any(c["id"] == conv_id for c in resp.json())

    # pin
    resp = await app_client.post(f"/api/conversations/{conv_id}/pin", params={"pinned": "true"})
    assert resp.status_code == 200

    # delete
    resp = await app_client.delete(f"/api/conversations/{conv_id}")
    assert resp.status_code == 200
    resp = await app_client.get("/api/conversations", params={"user_id": "alice"})
    assert not any(c["id"] == conv_id for c in resp.json())


async def test_rename_missing_conversation_404(app_client):
    resp = await app_client.patch("/api/conversations/does-not-exist", json={"title": "x"})
    assert resp.status_code == 404


async def test_delete_missing_conversation_404(app_client):
    resp = await app_client.delete("/api/conversations/does-not-exist")
    assert resp.status_code == 404


async def test_usage_summary_shape(app_client):
    resp = await app_client.get("/api/usage", params={"user_id": "alice"})
    assert resp.status_code == 200
    data = resp.json()
    assert "totals" in data and "by_provider_mode" in data and "window_days" in data
