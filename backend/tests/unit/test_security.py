"""
Unit tests for app.core.security module.

Tests password hashing, JWT token creation/validation, and authentication.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import jwt

pytestmark = [pytest.mark.unit]


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_verify_password_correct(self):
        """verify_password should return True for correct password."""
        from app.core.security import get_password_hash, verify_password

        password = "securepassword123"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """verify_password should return False for incorrect password."""
        from app.core.security import get_password_hash, verify_password

        password = "securepassword123"
        wrong_password = "wrongpassword"
        hashed = get_password_hash(password)

        assert verify_password(wrong_password, hashed) is False

    def test_hash_is_unique_each_call(self):
        """Each hash of the same password should be different (due to salt)."""
        from app.core.security import get_password_hash

        password = "samepassword"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        assert hash1 != hash2
        # But both should verify correctly
        from app.core.security import verify_password
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    def test_get_password_hash_returns_string(self):
        """get_password_hash should return a string."""
        from app.core.security import get_password_hash

        result = get_password_hash("anypassword")
        assert isinstance(result, str)
        assert len(result) > 0


class TestCreateAccessToken:
    """Tests for access token creation."""

    def test_creates_valid_jwt(self):
        """Should create a valid JWT with correct claims."""
        from app.core.security import create_access_token, settings

        token = create_access_token({"sub": "testuser"})

        # Decode and verify
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "testuser"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_token_expiry_with_custom_delta(self):
        """Should set expiry based on provided timedelta."""
        from app.core.security import create_access_token, settings

        delta = timedelta(hours=1)
        token = create_access_token({"sub": "testuser"}, expires_delta=delta)

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)

        # Should expire roughly 1 hour from now (within 5 second tolerance)
        diff = exp_time - now
        assert timedelta(minutes=55) < diff < timedelta(minutes=65)

    def test_default_expiry_is_15_minutes(self):
        """Default expiry should be 15 minutes when no delta provided."""
        from app.core.security import create_access_token, settings

        token = create_access_token({"sub": "testuser"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)

        diff = exp_time - now
        assert timedelta(minutes=14) < diff < timedelta(minutes=16)


class TestCreateRefreshToken:
    """Tests for refresh token creation."""

    def test_creates_valid_jwt_with_refresh_type(self):
        """Should create a valid JWT with type='refresh'."""
        from app.core.security import create_refresh_token, settings

        token = create_refresh_token({"sub": "testuser"})

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "testuser"
        assert payload["type"] == "refresh"
        assert "exp" in payload

    def test_refresh_token_default_expiry_is_7_days(self):
        """Default expiry for refresh token should be 7 days."""
        from app.core.security import create_refresh_token, settings

        token = create_refresh_token({"sub": "testuser"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)

        diff = exp_time - now
        assert timedelta(days=6) < diff < timedelta(days=8)


class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_raises_without_token(self):
        """Should raise 401 when no token provided."""
        from app.core.security import get_current_user
        from fastapi import HTTPException

        mock_request = MagicMock()
        mock_request.cookies.get = MagicMock(return_value=None)

        # oauth2_scheme returns None when no token
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, token=None)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_raises_with_expired_token(self):
        """Should raise 401 when token is expired."""
        from app.core.security import get_current_user, settings
        from fastapi import HTTPException

        # Create an expired token
        expired_payload = {
            "sub": "testuser",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "type": "access"
        }
        expired_token = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        mock_request = MagicMock()
        mock_request.cookies.get = MagicMock(return_value=None)

        mock_db = MagicMock()
        mock_db.execute = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, token=expired_token, db=mock_db)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_raises_with_wrong_token_type(self):
        """Should raise 401 when token type is 'refresh' but 'access' expected."""
        from app.core.security import get_current_user, settings
        from fastapi import HTTPException

        # Create a refresh token (wrong type for access)
        refresh_payload = {
            "sub": "testuser",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "type": "refresh"
        }
        refresh_token = jwt.encode(refresh_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        mock_request = MagicMock()
        mock_request.cookies.get = MagicMock(return_value=None)

        mock_db = MagicMock()
        mock_db.execute = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, token=refresh_token, db=mock_db)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_falls_back_to_cookie(self):
        """Should fall back to cookie token when Authorization header not present."""
        from app.core.security import get_current_user, settings
        from app.auth.models import User

        # Create a valid token
        valid_payload = {
            "sub": "cookieuser",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "type": "access"
        }
        valid_token = jwt.encode(valid_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        mock_request = MagicMock()
        mock_request.cookies.get = MagicMock(return_value="cookie_token_value")
        mock_request.cookies.get.side_effect = None

        # Simulate the cookie being returned on second call
        mock_request.cookies.get = lambda key: valid_token if key == "motifold_token" else None

        mock_user = MagicMock(spec=User)
        mock_user.username = "cookieuser"

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_user

        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        # The token here is None (from oauth2), so it falls back to cookie
        result = await get_current_user(mock_request, token=None, db=mock_db)

        assert result.username == "cookieuser"


class TestGetCurrentUserFromQuery:
    """Tests for get_current_user_from_query dependency."""

    @pytest.mark.asyncio
    async def test_raises_without_token_in_query_or_cookie(self):
        """Should raise 401 when no token in query or cookies."""
        from app.core.security import get_current_user_from_query
        from fastapi import HTTPException

        mock_request = MagicMock()
        mock_request.cookies.get = MagicMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_from_query(mock_request, token=None)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_uses_query_token_when_provided(self):
        """Should use token from query parameter when provided."""
        from app.core.security import get_current_user_from_query, settings
        from app.auth.models import User

        valid_payload = {
            "sub": "queryuser",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "type": "access"
        }
        valid_token = jwt.encode(valid_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        mock_request = MagicMock()
        mock_request.cookies.get = MagicMock(return_value=None)

        mock_user = MagicMock(spec=User)
        mock_user.username = "queryuser"

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_user

        mock_db = MagicMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await get_current_user_from_query(mock_request, token=valid_token, db=mock_db)

        assert result.username == "queryuser"
