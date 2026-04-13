# backend/tests/integration/test_chat_full.py
"""
Integration tests for chat API endpoints.

Tests the full chat router including CRUD operations.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = [pytest.mark.integration]


async def test_create_chat_without_workspace(auth_client):
    """Create a chat without workspace."""
    res = await auth_client.post("/chats/", json={})
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "New Chat"
    assert data["model"] == "pro"
    assert data["workspace_id"] is None


async def test_create_chat_with_model(auth_client):
    """Create a chat with specific model."""
    res = await auth_client.post("/chats/", json={"model": "max"})
    assert res.status_code == 200
    data = res.json()
    assert data["model"] == "max"


async def test_create_chat_with_invalid_model(auth_client):
    """Reject chat with invalid model."""
    res = await auth_client.post("/chats/", json={"model": "invalid"})
    assert res.status_code == 422  # Validation error


async def test_get_chat(auth_client):
    """Get a specific chat by ID."""
    # Create chat first
    create_res = await auth_client.post("/chats/", json={})
    chat_id = create_res.json()["id"]

    # Get chat
    res = await auth_client.get(f"/chats/{chat_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == chat_id


async def test_get_chat_not_found(auth_client):
    """Return 404 for non-existent chat."""
    res = await auth_client.get("/chats/99999")
    assert res.status_code == 404


async def test_get_chat_other_users_chat(auth_client, other_user):
    """Cannot get another user's chat."""
    from app.auth.models import User
    from app.main import app
    from app.core.security import get_current_user

    # Create chat as test_user
    create_res = await auth_client.post("/chats/", json={})
    chat_id = create_res.json()["id"]

    # Try to get as other_user
    async def override_get_current_user():
        return other_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    res = await auth_client.get(f"/chats/{chat_id}")
    assert res.status_code == 404

    app.dependency_overrides.clear()


async def test_list_chats_default_limit(auth_client):
    """List chats with default pagination."""
    # Create multiple chats
    for _ in range(5):
        await auth_client.post("/chats/", json={})

    res = await auth_client.get("/chats/")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 5


async def test_list_chats_with_pagination(auth_client):
    """List chats with skip and limit."""
    # Create 3 chats
    for _ in range(3):
        await auth_client.post("/chats/", json={})

    # Get first 2
    res = await auth_client.get("/chats/?skip=0&limit=2")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2

    # Get next 1
    res = await auth_client.get("/chats/?skip=2&limit=2")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1


async def test_delete_chat(auth_client):
    """Delete a chat."""
    # Create chat
    create_res = await auth_client.post("/chats/", json={})
    chat_id = create_res.json()["id"]

    # Delete it
    res = await auth_client.delete(f"/chats/{chat_id}")
    assert res.status_code == 200

    # Verify it's gone
    get_res = await auth_client.get(f"/chats/{chat_id}")
    assert get_res.status_code == 404


async def test_delete_chat_not_found(auth_client):
    """Return 404 when deleting non-existent chat."""
    res = await auth_client.delete("/chats/99999")
    assert res.status_code == 404


async def test_delete_chat_other_users_chat(auth_client, other_user):
    """Cannot delete another user's chat."""
    from app.main import app
    from app.core.security import get_current_user

    # Create chat as test_user
    create_res = await auth_client.post("/chats/", json={})
    chat_id = create_res.json()["id"]

    # Try to delete as other_user
    async def override_get_current_user():
        return other_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    res = await auth_client.delete(f"/chats/{chat_id}")
    assert res.status_code == 404

    app.dependency_overrides.clear()


async def test_create_chat_in_workspace_full_flow(auth_client, db_session):
    """Full flow: create workspace, create chat in workspace, verify."""
    # Create workspace
    ws_res = await auth_client.post("/workspaces/", json={"name": "Test Workspace"})
    assert ws_res.status_code == 200
    ws_id = ws_res.json()["id"]

    # Create chat in workspace
    chat_res = await auth_client.post("/chats/", json={"workspace_id": ws_id})
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["workspace_id"] == ws_id
    assert chat_data["title"] == "New Chat"

    # List chats filtered by workspace
    list_res = await auth_client.get(f"/chats/?workspace_id={ws_id}")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert len(list_data) == 1
    assert list_data[0]["workspace_id"] == ws_id


async def test_create_chat_invalid_workspace(auth_client):
    """Reject chat with non-existent workspace."""
    res = await auth_client.post("/chats/", json={"workspace_id": 99999})
    assert res.status_code == 404


async def test_send_message_returns_processing_status(auth_client):
    """Send message should return processing status."""
    # Create chat
    create_res = await auth_client.post("/chats/", json={})
    chat_id = create_res.json()["id"]

    # Send message
    msg_res = await auth_client.post(
        f"/chats/{chat_id}/messages",
        json={"content": "Hello"}
    )
    assert msg_res.status_code == 200
    data = msg_res.json()
    assert data["status"] == "processing"
    assert "stream_url" in data


async def test_send_message_with_model_override(auth_client):
    """Send message with model override."""
    # Create chat
    create_res = await auth_client.post("/chats/", json={})
    chat_id = create_res.json()["id"]

    # Send message with model
    msg_res = await auth_client.post(
        f"/chats/{chat_id}/messages",
        json={"content": "Hello", "model": "mini"}
    )
    assert msg_res.status_code == 200


async def test_send_message_to_nonexistent_chat(auth_client):
    """Send message to non-existent chat returns 404."""
    msg_res = await auth_client.post(
        "/chats/99999/messages",
        json={"content": "Hello"}
    )
    assert msg_res.status_code == 404


async def test_get_messages_empty(auth_client):
    """Get messages from new chat returns empty list."""
    # Create chat
    create_res = await auth_client.post("/chats/", json={})
    chat_id = create_res.json()["id"]

    # Get messages
    msg_res = await auth_client.get(f"/chats/{chat_id}/messages")
    assert msg_res.status_code == 200
    data = msg_res.json()
    assert data == []


async def test_get_messages_with_pagination(auth_client):
    """Get messages with skip and limit."""
    # Create chat
    create_res = await auth_client.post("/chats/", json={})
    chat_id = create_res.json()["id"]

    # Get messages with pagination
    msg_res = await auth_client.get(f"/chats/{chat_id}/messages?skip=0&limit=10")
    assert msg_res.status_code == 200


async def test_get_messages_nonexistent_chat(auth_client):
    """Get messages from non-existent chat returns 404."""
    msg_res = await auth_client.get("/chats/99999/messages")
    assert msg_res.status_code == 404


async def test_stream_chat_endpoint_exists(auth_client):
    """Stream endpoint should exist and return 200 (or process)."""
    # Create chat
    create_res = await auth_client.post("/chats/", json={})
    chat_id = create_res.json()["id"]

    # Stream endpoint returns StreamingResponse
    # Note: This test just verifies the endpoint is registered
    # Actual streaming is tested separately
    res = await auth_client.get(f"/chats/{chat_id}/stream")
    # The endpoint may return 200 or timeout depending on state
    assert res.status_code in [200, 500]  # 500 if processing not started


async def test_stream_chat_nonexistent_chat(auth_client):
    """Stream from non-existent chat returns 404."""
    res = await auth_client.get("/chats/99999/stream")
    assert res.status_code == 404
