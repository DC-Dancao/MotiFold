# backend/tests/integration/test_auth.py
"""
Integration tests for authentication: register, login, invalid login.
"""
# pytestmark set in conftest.py: pytest.mark.integration
# asyncio_mode = auto in pytest.ini handles async detection


async def test_register_and_login(async_client):
    """Register a new user and then login with valid credentials."""
    # 1. Register
    reg_res = await async_client.post(
        "/auth/register",
        json={"username": "realuser", "password": "realpassword"}
    )
    assert reg_res.status_code == 200
    data = reg_res.json()
    assert data["username"] == "realuser"
    assert "id" in data

    # 2. Login
    login_res = await async_client.post(
        "/auth/login",
        data={"username": "realuser", "password": "realpassword"}
    )
    assert login_res.status_code == 200
    tokens = login_res.json()
    assert "access_token" in tokens
    assert tokens["token_type"] == "bearer"

    # 3. Invalid Login
    invalid_res = await async_client.post(
        "/auth/login",
        data={"username": "realuser", "password": "wrongpassword"}
    )
    assert invalid_res.status_code == 401


async def test_register_duplicate_username(async_client):
    """Registering with existing username should fail."""
    await async_client.post(
        "/auth/register",
        json={"username": "dupuser", "password": "password123"}
    )
    dup_res = await async_client.post(
        "/auth/register",
        json={"username": "dupuser", "password": "password456"}
    )
    assert dup_res.status_code == 400
