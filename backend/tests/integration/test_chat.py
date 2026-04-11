# backend/tests/integration/test_chat.py
"""
Integration tests for chat CRUD.
"""
# pytestmark set in conftest.py: pytest.mark.integration
# asyncio_mode = auto in pytest.ini handles async detection


async def test_create_chat_in_workspace(auth_client, db_session):
    """Create a chat in a workspace."""
    ws_res = await auth_client.post("/workspaces/", json={"name": "Chat Workspace"})
    ws_id = ws_res.json()["id"]

    chat_res = await auth_client.post("/chats/", json={"workspace_id": ws_id})
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["workspace_id"] == ws_id
    assert chat_data["title"] == "New Chat"


async def test_list_chats_by_workspace(auth_client):
    """List chats filtered by workspace."""
    ws1_res = await auth_client.post("/workspaces/", json={"name": "WS 1"})
    ws1_id = ws1_res.json()["id"]

    ws2_res = await auth_client.post("/workspaces/", json={"name": "WS 2"})
    ws2_id = ws2_res.json()["id"]

    await auth_client.post("/chats/", json={"workspace_id": ws1_id})
    await auth_client.post("/chats/", json={"workspace_id": ws1_id})
    await auth_client.post("/chats/", json={"workspace_id": ws2_id})

    res1 = await auth_client.get(f"/chats/?workspace_id={ws1_id}")
    assert res1.status_code == 200
    data1 = res1.json()
    assert len(data1) == 2
    for chat in data1:
        assert chat["workspace_id"] == ws1_id

    res2 = await auth_client.get(f"/chats/?workspace_id={ws2_id}")
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2) == 1
    assert data2[0]["workspace_id"] == ws2_id
