import pytest
from app.workspace.models import Workspace
from app.chat.models import Chat

pytestmark = pytest.mark.asyncio

async def test_create_workspace(auth_client, test_user, db_session):
    response = await auth_client.post(
        "/workspaces/",
        json={"name": "Test Workspace"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Workspace"
    assert "id" in data
    
    # Advanced assertion: Check DB directly
    db_ws = await db_session.get(Workspace, data["id"])
    assert db_ws is not None
    assert db_ws.user_id == test_user.id

async def test_list_workspaces(auth_client):
    # Create two workspaces
    await auth_client.post("/workspaces/", json={"name": "Test Workspace"})
    await auth_client.post("/workspaces/", json={"name": "Second Workspace"})
    
    response = await auth_client.get("/workspaces/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = [w["name"] for w in data]
    assert "Test Workspace" in names
    assert "Second Workspace" in names

async def test_create_chat_in_workspace(auth_client, db_session):
    # 1. Create a workspace
    ws_res = await auth_client.post("/workspaces/", json={"name": "Chat Workspace"})
    ws_id = ws_res.json()["id"]
    
    # 2. Create a chat in that workspace
    chat_res = await auth_client.post("/chats/", json={"workspace_id": ws_id})
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["workspace_id"] == ws_id
    assert chat_data["title"] == "New Chat"

async def test_list_chats_by_workspace(auth_client):
    ws1_res = await auth_client.post("/workspaces/", json={"name": "WS 1"})
    ws1_id = ws1_res.json()["id"]
    
    ws2_res = await auth_client.post("/workspaces/", json={"name": "WS 2"})
    ws2_id = ws2_res.json()["id"]
    
    # Create chats
    await auth_client.post("/chats/", json={"workspace_id": ws1_id})
    await auth_client.post("/chats/", json={"workspace_id": ws1_id})
    await auth_client.post("/chats/", json={"workspace_id": ws2_id})
    
    # List chats in WS 1
    res1 = await auth_client.get(f"/chats/?workspace_id={ws1_id}")
    assert res1.status_code == 200
    data1 = res1.json()
    assert len(data1) == 2
    for chat in data1:
        assert chat["workspace_id"] == ws1_id
        
    # List chats in WS 2
    res2 = await auth_client.get(f"/chats/?workspace_id={ws2_id}")
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2) == 1
    assert data2[0]["workspace_id"] == ws2_id

async def test_delete_workspace(auth_client):
    ws_res = await auth_client.post("/workspaces/", json={"name": "To Delete"})
    ws_id = ws_res.json()["id"]
    
    del_res = await auth_client.delete(f"/workspaces/{ws_id}")
    assert del_res.status_code == 200
    
    get_res = await auth_client.get(f"/workspaces/{ws_id}")
    assert get_res.status_code == 404
