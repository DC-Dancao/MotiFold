"""
Unit tests for app.org.schemas module.

Tests Organization schemas and slug validation.
"""
import pytest
from pydantic import ValidationError

pytestmark = [pytest.mark.unit]


class TestOrganizationCreate:
    """Tests for OrganizationCreate schema."""

    def test_valid_org_creation(self):
        """Should create OrganizationCreate with valid data."""
        from app.org.schemas import OrganizationCreate

        org = OrganizationCreate(name="Test Org", slug="test-org")
        assert org.name == "Test Org"
        assert org.slug == "test-org"

    def test_valid_slug_with_underscores(self):
        """Should accept slugs with underscores."""
        from app.org.schemas import OrganizationCreate

        org = OrganizationCreate(name="Test", slug="my_company")
        assert org.slug == "my_company"

    def test_valid_slug_with_hyphens(self):
        """Should accept slugs with hyphens."""
        from app.org.schemas import OrganizationCreate

        org = OrganizationCreate(name="Test", slug="my-company")
        assert org.slug == "my-company"

    def test_valid_slug_starting_with_number(self):
        """Should accept slugs starting with numbers."""
        from app.org.schemas import OrganizationCreate

        org = OrganizationCreate(name="Test", slug="123company")
        assert org.slug == "123company"

    def test_invalid_slug_uppercase_rejected(self):
        """Should reject slugs with uppercase letters."""
        from app.org.schemas import OrganizationCreate

        with pytest.raises(ValidationError) as exc_info:
            OrganizationCreate(name="Test", slug="TestOrg")

        assert "Invalid slug format" in str(exc_info.value)

    def test_invalid_slug_special_chars_rejected(self):
        """Should reject slugs with special characters."""
        from app.org.schemas import OrganizationCreate

        invalid_slugs = ["test@org", "test.org", "test org", "test!org", "test#org"]

        for slug in invalid_slugs:
            with pytest.raises(ValidationError) as exc_info:
                OrganizationCreate(name="Test", slug=slug)
            assert "Invalid slug format" in str(exc_info.value)

    def test_invalid_slug_starts_with_hyphen(self):
        """Should reject slugs starting with hyphen."""
        from app.org.schemas import OrganizationCreate

        with pytest.raises(ValidationError) as exc_info:
            OrganizationCreate(name="Test", slug="-testorg")

        assert "Invalid slug format" in str(exc_info.value)

    def test_invalid_slug_starts_with_underscore(self):
        """Should reject slugs starting with underscore."""
        from app.org.schemas import OrganizationCreate

        with pytest.raises(ValidationError) as exc_info:
            OrganizationCreate(name="Test", slug="_testorg")

        assert "Invalid slug format" in str(exc_info.value)

    def test_slug_too_long_rejected(self):
        """Should reject slugs longer than 50 characters."""
        from app.org.schemas import OrganizationCreate

        with pytest.raises(ValidationError) as exc_info:
            OrganizationCreate(name="Test", slug="a" * 51)

        assert "Invalid slug format" in str(exc_info.value)

    def test_slug_exactly_50_chars_accepted(self):
        """Should accept slugs exactly 50 characters."""
        from app.org.schemas import OrganizationCreate

        org = OrganizationCreate(name="Test", slug="a" * 50)
        assert len(org.slug) == 50


class TestOrganizationOut:
    """Tests for OrganizationOut schema."""

    def test_from_attributes_config(self):
        """Should have from_attributes = True for ORM compatibility."""
        from app.org.schemas import OrganizationOut

        assert OrganizationOut.model_config["from_attributes"] is True


class TestOrganizationMemberCreate:
    """Tests for OrganizationMemberCreate schema."""

    def test_valid_member_creation(self):
        """Should create member with valid data."""
        from app.org.schemas import OrganizationMemberCreate

        member = OrganizationMemberCreate(user_id=1)
        assert member.user_id == 1
        assert member.role == "member"

    def test_custom_role(self):
        """Should accept custom role."""
        from app.org.schemas import OrganizationMemberCreate

        member = OrganizationMemberCreate(user_id=1, role="admin")
        assert member.role == "admin"


class TestOrgMemberWithUser:
    """Tests for OrgMemberWithUser schema."""

    def test_inherits_from_organization_member_out(self):
        """Should inherit fields from OrganizationMemberOut."""
        from app.org.schemas import OrgMemberWithUser
        from datetime import datetime

        member = OrgMemberWithUser(
            id="123",
            organization_id=1,
            user_id=1,
            role="member",
            joined_at=datetime.now(),
            username="testuser",
            email="test@example.com"
        )

        assert member.username == "testuser"
        assert member.email == "test@example.com"
        assert member.role == "member"
