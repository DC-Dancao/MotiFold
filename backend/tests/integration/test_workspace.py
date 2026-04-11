# backend/tests/integration/test_workspace.py
"""
Integration tests for workspace CRUD.
"""
from app.workspace.models import Workspace

# pytestmark set in conftest.py: pytest.mark.integration
# asyncio_mode = auto in pytest.ini handles async detection


async def test_create_workspace(auth_client, test_user, db_session):
    """Create a workspace and verify it exists in DB."""
    response = await auth_client.post(
        "/workspaces/",
        json={"name": "Test Workspace"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Workspace"
    assert "id" in data

    db_ws = await db_session.get(Workspace, data["id"])
    assert db_ws is not None
    assert db_ws.user_id == test_user.id


async def test_list_workspaces(auth_client):
    """List workspaces returns all workspaces for the user."""
    await auth_client.post("/workspaces/", json={"name": "Test Workspace"})
    await auth_client.post("/workspaces/", json={"name": "Second Workspace"})

    response = await auth_client.get("/workspaces/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = [w["name"] for w in data]
    assert "Test Workspace" in names
    assert "Second Workspace" in names


async def test_delete_workspace(auth_client):
    """Delete workspace removes it from DB."""
    ws_res = await auth_client.post("/workspaces/", json={"name": "To Delete"})
    ws_id = ws_res.json()["id"]

    del_res = await auth_client.delete(f"/workspaces/{ws_id}")
    assert del_res.status_code == 200

    get_res = await auth_client.get(f"/workspaces/{ws_id}")
    assert get_res.status_code == 404
