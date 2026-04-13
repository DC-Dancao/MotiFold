"""
Unit tests for app.tenant.context module.

Tests the ContextVar-based request-local tenant context.
"""
import pytest
from unittest.mock import patch

pytestmark = [pytest.mark.unit]


class TestTenantContext:
    """Tests for tenant context functions."""

    def test_set_and_get_current_org(self):
        """Setting org slug should be retrievable via get_current_org."""
        from app.tenant.context import set_current_org, get_current_org, clear_current_org

        clear_current_org()
        set_current_org("test-org")
        assert get_current_org() == "test-org"
        clear_current_org()

    def test_get_current_org_default_is_none(self):
        """get_current_org should return None when not set."""
        from app.tenant.context import get_current_org, clear_current_org

        clear_current_org()
        assert get_current_org() is None

    def test_clear_current_org(self):
        """clear_current_org should reset the context to None."""
        from app.tenant.context import set_current_org, get_current_org, clear_current_org

        set_current_org("some-org")
        clear_current_org()
        assert get_current_org() is None

    def test_context_isolation_between_sets(self):
        """Multiple set calls should overwrite the previous value."""
        from app.tenant.context import set_current_org, get_current_org, clear_current_org

        clear_current_org()
        set_current_org("first-org")
        assert get_current_org() == "first-org"

        set_current_org("second-org")
        assert get_current_org() == "second-org"

        clear_current_org()

    def test_set_with_none_value(self):
        """Setting org to None should work and return None."""
        from app.tenant.context import set_current_org, get_current_org, clear_current_org

        clear_current_org()
        set_current_org("some-org")
        set_current_org(None)
        assert get_current_org() is None


class TestGetSchemaName:
    """Tests for get_schema_name function."""

    def test_simple_slug_conversion(self):
        """Simple slug should be prefixed with org_."""
        from app.tenant.context import get_schema_name

        assert get_schema_name("test-org") == "org_test-org"
        assert get_schema_name("mycompany") == "org_mycompany"

    def test_slug_with_underscores(self):
        """Slug with underscores should be preserved."""
        from app.tenant.context import get_schema_name

        assert get_schema_name("my_company") == "org_my_company"

    def test_slug_with_hyphens(self):
        """Slug with hyphens should be preserved."""
        from app.tenant.context import get_schema_name

        assert get_schema_name("my-company") == "org_my-company"

    def test_schema_name_format(self):
        """Schema name should always start with org_ prefix."""
        from app.tenant.context import get_schema_name

        result = get_schema_name("acme")
        assert result.startswith("org_")
        assert result == "org_acme"
