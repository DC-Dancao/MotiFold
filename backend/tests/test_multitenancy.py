"""Tests for multi-tenancy features: template cloning, path routing, and org provisioning."""
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.future import select

from app.main import app
from app.core.database import AsyncSessionLocal
from app.auth.models import User
from app.org.models import Organization, OrganizationMember
from app.org import provisioner


pytestmark = pytest.mark.asyncio


class TestPathBasedRouting:
    """The legacy /{org_slug}/<resource> URL form was removed when the API
    moved entirely under /api/*. This test now just verifies that bare org-slug
    paths fall through to the normal 404 handling without crashing."""

    async def test_legacy_org_slug_paths_no_longer_route(self, async_client: AsyncClient):
        """A bare /{org_slug}/<resource> request should return 404 cleanly."""
        response = await async_client.get("/nonexistent/workspaces")
        # No routing crash. Could be 404 from FastAPI or from business logic.
        assert response.status_code != 500
        assert response.status_code == 404


class TestTemplateCloneProvisioning:
    """Test that new org schema is cloned from template instantly."""

    async def test_provision_org_schema_creates_tables(self, db_session):
        """Test that provision_org_schema creates schema with expected tables."""
        import uuid
        org_slug = f"test_clone_{uuid.uuid4().hex[:8]}"

        try:
            # Create a test org
            org = Organization(name="Clone Test", slug=org_slug, status="provisioning")
            db_session.add(org)
            await db_session.commit()

            # Provision schema
            await provisioner.provision_org_schema(org_slug)

            # Verify schema exists
            result = await db_session.execute(
                text(f"SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'org_{org_slug}'")
            )
            schema_exists = result.fetchone() is not None
            assert schema_exists, f"Schema org_{org_slug} should exist"

            # Verify schema has expected tables (from template)
            result = await db_session.execute(
                text(f"SELECT table_name FROM information_schema.tables WHERE table_schema = 'org_{org_slug}'")
            )
            tables = [row[0] for row in result.fetchall()]

            assert "workspaces" in tables, f"Expected 'workspaces' table in org schema, got: {tables}"
            assert "chats" in tables, f"Expected 'chats' table in org schema, got: {tables}"

            # Verify org status was updated to active
            result = await db_session.execute(
                select(Organization).where(Organization.slug == org_slug)
            )
            updated_org = result.scalars().first()
            assert updated_org is not None
            assert updated_org.status == "active"

        finally:
            # Cleanup
            try:
                await provisioner.deprovision_org_schema(org_slug)
            except Exception:
                pass
            await db_session.execute(text("DELETE FROM organizations WHERE slug = :slug"), {"slug": org_slug})
            await db_session.commit()

    async def test_deprovision_org_schema_drops_schema(self, db_session):
        """Test that deprovision_org_schema drops the schema."""
        import uuid
        org_slug = f"test_deprov_{uuid.uuid4().hex[:8]}"

        try:
            # Create and provision org
            org = Organization(name="Deprov Test", slug=org_slug, status="provisioning")
            db_session.add(org)
            await db_session.commit()
            await provisioner.provision_org_schema(org_slug)

            # Deprovision
            await provisioner.deprovision_org_schema(org_slug)

            # Verify schema is gone
            result = await db_session.execute(
                text(f"SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'org_{org_slug}'")
            )
            schema_exists = result.fetchone() is not None
            assert not schema_exists, f"Schema org_{org_slug} should not exist after deprovision"

        finally:
            # Cleanup if deprovision failed
            try:
                await provisioner.deprovision_org_schema(org_slug)
            except Exception:
                pass
            await db_session.execute(text("DELETE FROM organizations WHERE slug = :slug"), {"slug": org_slug})
            await db_session.commit()


class TestRegistrationCreatesPersonalOrg:
    """Test that new user registration creates personal org with schema."""

    async def test_registration_creates_personal_org(self, db_session, test_user: User):
        """Test that user has personal org created with schema."""
        from app.org import provisioner

        # The user fixture creates testuser, but we need to ensure personal org exists
        # Check if personal org was created
        result = await db_session.execute(
            select(Organization).where(Organization.slug == f"user_{test_user.id}")
        )
        org = result.scalars().first()

        assert org is not None, f"Personal org for user_{test_user.id} should exist"
        # Status should be 'active' after provisioning completes (if provisioning was triggered)

        # Verify schema was cloned
        result = await db_session.execute(
            text(f"SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'org_user_{test_user.id}'")
        )
        schema_exists = result.fetchone() is not None
        assert schema_exists, f"Schema org_user_{test_user.id} should exist"
