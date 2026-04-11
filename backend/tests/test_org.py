"""Tests for Organization multi-tenancy features."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.org.models import Organization, OrganizationMember
from app.core.security import get_current_user
from app.main import app


pytestmark = pytest.mark.asyncio


class TestOrgCreation:
    async def test_create_org_valid_slug(self, auth_client: AsyncClient, db_session: AsyncSession, test_user: User):
        """Create org with valid slug returns 200 and status provisioning."""
        response = await auth_client.post(
            "/api/orgs/",
            json={"name": "Test Org", "slug": "test-org"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Org"
        assert data["slug"] == "test-org"
        assert data["status"] == "provisioning"

    async def test_create_org_invalid_slug_uppercase(self, auth_client: AsyncClient, db_session: AsyncSession):
        """Create org with uppercase slug returns 422."""
        response = await auth_client.post(
            "/api/orgs/",
            json={"name": "Test Org", "slug": "TestOrg"},
        )
        assert response.status_code == 422

    async def test_create_org_invalid_slug_special_chars(self, auth_client: AsyncClient, db_session: AsyncSession):
        """Create org with special characters returns 422."""
        response = await auth_client.post(
            "/api/orgs/",
            json={"name": "Test Org", "slug": "test@org!"},
        )
        assert response.status_code == 422

    async def test_create_org_duplicate_slug(self, auth_client: AsyncClient, db_session: AsyncSession):
        """Create org with duplicate slug returns 400."""
        # Create first org
        await auth_client.post(
            "/api/orgs/",
            json={"name": "First Org", "slug": "unique-slug"},
        )
        # Try to create second with same slug
        response = await auth_client.post(
            "/api/orgs/",
            json={"name": "Second Org", "slug": "unique-slug"},
        )
        assert response.status_code == 400
        assert "Slug already taken" in response.json()["detail"]


class TestOrgMembership:
    async def test_list_orgs_returns_memberships(self, auth_client: AsyncClient, db_session: AsyncSession):
        """List orgs returns only orgs user is member of."""
        # Create org (user becomes owner)
        await auth_client.post(
            "/api/orgs/",
            json={"name": "My Org", "slug": "my-org"},
        )
        response = await auth_client.get(
            "/api/orgs/",
        )
        assert response.status_code == 200
        orgs = response.json()
        assert any(o["slug"] == "my-org" for o in orgs)

    async def test_get_org_requires_membership(
        self, auth_client: AsyncClient, async_client: AsyncClient, db_session: AsyncSession, test_user: User, other_user: User
    ):
        """Getting org user is not member of returns 403."""
        # Create org as test_user
        await auth_client.post(
            "/api/orgs/",
            json={"name": "Private Org", "slug": "private-org"},
        )
        # Try to access as other_user using async_client with different auth
        async def override_get_current_user():
            return other_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        try:
            response = await async_client.get(
                "/api/orgs/private-org",
            )
            assert response.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    async def test_invite_member(
        self, auth_client: AsyncClient, db_session: AsyncSession, test_user: User, other_user: User
    ):
        """Owner can invite a member to org."""
        # Create org
        await auth_client.post(
            "/api/orgs/",
            json={"name": "Team Org", "slug": "team-org"},
        )
        # Invite other user
        response = await auth_client.post(
            "/api/orgs/team-org/members",
            json={"user_id": str(other_user.id), "role": "member"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "member"
        assert data["organization_id"] == "team-org"

    async def test_invite_non_existent_user(self, auth_client: AsyncClient, db_session: AsyncSession):
        """Inviting non-existent user returns 404."""
        await auth_client.post(
            "/api/orgs/",
            json={"name": "Test Org", "slug": "test-invite"},
        )
        response = await auth_client.post(
            "/api/orgs/test-invite/members",
            json={"user_id": "999999", "role": "member"},
        )
        assert response.status_code == 404

    async def test_remove_member(
        self, auth_client: AsyncClient, db_session: AsyncSession, test_user: User, other_user: User
    ):
        """Owner can remove a member from org."""
        # Create org and invite member
        await auth_client.post(
            "/api/orgs/",
            json={"name": "Removable Org", "slug": "removable-org"},
        )
        await auth_client.post(
            "/api/orgs/removable-org/members",
            json={"user_id": str(other_user.id), "role": "member"},
        )
        # Remove member
        response = await auth_client.delete(
            f"/api/orgs/removable-org/members/{other_user.id}",
        )
        assert response.status_code == 200

    async def test_cannot_remove_owner(
        self, auth_client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """Cannot remove org owner."""
        # Create org
        await auth_client.post(
            "/api/orgs/",
            json={"name": "Owner Org", "slug": "owner-org"},
        )
        # Try to remove self (owner)
        response = await auth_client.delete(
            f"/api/orgs/owner-org/members/{test_user.id}",
        )
        assert response.status_code == 400
        assert "Cannot remove organization owner" in response.json()["detail"]