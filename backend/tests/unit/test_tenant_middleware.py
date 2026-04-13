"""
Unit tests for app.tenant.middleware module.

Tests the TenantMiddleware for org slug extraction and path rewriting.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from starlette.requests import Request
from starlette.responses import JSONResponse

pytestmark = [pytest.mark.unit]


class TestGetOrgSlugFromPath:
    """Tests for _get_org_slug_from_path helper."""

    def test_extracts_org_from_valid_path(self):
        """Should extract org slug from valid /{org_slug}/resource paths."""
        from app.tenant.middleware import _get_org_slug_from_path

        assert _get_org_slug_from_path("/my-org/api/users") == "my-org"
        assert _get_org_slug_from_path("/acme/data") == "acme"

    def test_returns_none_for_invalid_org_slug(self):
        """Should return None when org slug contains invalid characters."""
        from app.tenant.middleware import _get_org_slug_from_path

        assert _get_org_slug_from_path("/my org/api") is None
        assert _get_org_slug_from_path("/my@org/api") is None
        assert _get_org_slug_from_path("/my!org/api") is None

    def test_returns_none_for_single_segment_path(self):
        """Should return None for paths with fewer than 2 segments."""
        from app.tenant.middleware import _get_org_slug_from_path

        assert _get_org_slug_from_path("/single") is None
        assert _get_org_slug_from_path("/") is None

    def test_handles_paths_with_empty_segments(self):
        """Should return None when path starts with empty segment."""
        from app.tenant.middleware import _get_org_slug_from_path

        assert _get_org_slug_from_path("//api") is None
        assert _get_org_slug_from_path("/  /api") is None

    def test_org_slug_with_underscores_and_hyphens(self):
        """Org slugs with underscores and hyphens should be valid."""
        from app.tenant.middleware import _get_org_slug_from_path

        assert _get_org_slug_from_path("/my_company/api") == "my_company"
        assert _get_org_slug_from_path("/my-company/api") == "my-company"


class TestTenantMiddlewareDispatch:
    """Tests for TenantMiddleware.dispatch method."""

    async def test_public_paths_skip_tenant_processing(self):
        """Paths in PUBLIC_PATHS should not set org context."""
        from app.tenant.middleware import TenantMiddleware
        from app.tenant.context import get_current_org, clear_current_org

        middleware = TenantMiddleware(app=MagicMock())

        public_paths = ["/", "/auth/login", "/docs", "/openapi.json", "/redoc", "/notifications"]

        for path in public_paths:
            clear_current_org()
            request = MagicMock(spec=Request)
            request.url.path = path
            request.state = MagicMock()

            async def call_next(req):
                return JSONResponse({})

            response = await middleware.dispatch(request, call_next)
            assert get_current_org() is None, f"Failed for path: {path}"

    async def test_api_prefix_skips_tenant_processing(self):
        """Paths starting with /api/ should not set org context."""
        from app.tenant.middleware import TenantMiddleware
        from app.tenant.context import get_current_org, clear_current_org

        middleware = TenantMiddleware(app=MagicMock())
        clear_current_org()

        request = MagicMock(spec=Request)
        request.url.path = "/api/users"
        request.state = MagicMock()

        async def call_next(req):
            return JSONResponse({})

        response = await middleware.dispatch(request, call_next)
        assert get_current_org() is None

    async def test_x_org_id_header_takes_precedence(self):
        """X-Org-ID header should be used when present."""
        from app.tenant.middleware import TenantMiddleware
        from app.tenant.context import get_current_org, clear_current_org

        middleware = TenantMiddleware(app=MagicMock())
        clear_current_org()

        request = MagicMock(spec=Request)
        request.url.path = "/any-org/api/data"
        request.headers.get = MagicMock(return_value="header-org")
        request.state = MagicMock()

        async def call_next(req):
            return JSONResponse({})

        response = await middleware.dispatch(request, call_next)
        assert get_current_org() == "header-org"

    async def test_falls_back_to_path_parsing(self):
        """Should parse org slug from path when no X-Org-ID header."""
        from app.tenant.middleware import TenantMiddleware
        from app.tenant.context import get_current_org, clear_current_org

        middleware = TenantMiddleware(app=MagicMock())
        clear_current_org()

        request = MagicMock(spec=Request)
        request.url.path = "/path-org/api/data"
        request.headers.get = MagicMock(return_value=None)
        request.state = MagicMock()

        async def call_next(req):
            return JSONResponse({})

        response = await middleware.dispatch(request, call_next)
        assert get_current_org() == "path-org"

    async def test_sets_org_schema_on_request_state(self):
        """Should set org_schema on request.state when org is found."""
        from app.tenant.middleware import TenantMiddleware
        from app.tenant.context import clear_current_org

        middleware = TenantMiddleware(app=MagicMock())
        clear_current_org()

        request = MagicMock(spec=Request)
        request.url.path = "/test-org/api/data"
        request.headers.get = MagicMock(return_value=None)
        request.state = MagicMock()

        async def call_next(req):
            return JSONResponse({})

        await middleware.dispatch(request, call_next)
        assert request.state.org_schema == "org_test-org"

    async def test_clears_context_after_request(self):
        """Should clear org context after request completes."""
        from app.tenant.middleware import TenantMiddleware
        from app.tenant.context import get_current_org, clear_current_org

        middleware = TenantMiddleware(app=MagicMock())
        clear_current_org()

        request = MagicMock(spec=Request)
        request.url.path = "/test-org/api/data"
        request.headers.get = MagicMock(return_value=None)
        request.state = MagicMock()

        async def call_next(req):
            return JSONResponse({})

        await middleware.dispatch(request, call_next)
        assert get_current_org() is None

    async def test_strips_org_prefix_from_path(self):
        """Should rewrite path to remove org prefix after extracting slug."""
        from app.tenant.middleware import TenantMiddleware
        from app.tenant.context import clear_current_org

        middleware = TenantMiddleware(app=MagicMock())
        clear_current_org()

        request = MagicMock(spec=Request)
        request.url.path = "/my-org/api/users"
        request.headers.get = MagicMock(return_value=None)
        request.state = MagicMock()
        request.scope = {"path": "/my-org/api/users"}

        async def call_next(req):
            return JSONResponse({})

        await middleware.dispatch(request, call_next)
        assert request.scope["path"] == "/api/users"

    async def test_no_rewrite_when_org_not_in_path(self):
        """Should not rewrite path when org slug doesn't match path prefix."""
        from app.tenant.middleware import TenantMiddleware
        from app.tenant.context import clear_current_org

        middleware = TenantMiddleware(app=MagicMock())
        clear_current_org()

        request = MagicMock(spec=Request)
        request.url.path = "/other-org/api/data"
        request.headers.get = MagicMock(return_value=None)
        request.state = MagicMock()
        request.scope = {"path": "/other-org/api/data"}

        async def call_next(req):
            return JSONResponse({})

        await middleware.dispatch(request, call_next)
        # When X-Org-ID is not present and path org doesn't match, no rewrite
        assert request.scope["path"] == "/other-org/api/data"
