"""
Unit tests for app.tenant.middleware module.

Tests TenantMiddleware: tenant-free path detection and X-Org-ID based
tenant resolution. URL-path-based slug parsing was removed when the API
moved entirely under /api/* — the X-Org-ID header is now the only source
of tenant context.
"""
import pytest
from unittest.mock import MagicMock
from starlette.requests import Request
from starlette.responses import JSONResponse

pytestmark = [pytest.mark.unit]


class TestIsTenantFree:
    """Tests for the _is_tenant_free helper."""

    def test_root_path_is_tenant_free(self):
        from app.tenant.middleware import _is_tenant_free

        assert _is_tenant_free("/") is True

    def test_auth_and_orgs_and_notifications_are_tenant_free(self):
        from app.tenant.middleware import _is_tenant_free

        assert _is_tenant_free("/api/auth") is True
        assert _is_tenant_free("/api/auth/login") is True
        assert _is_tenant_free("/api/orgs") is True
        assert _is_tenant_free("/api/orgs/foo") is True
        assert _is_tenant_free("/api/notifications/stream") is True

    def test_docs_routes_are_tenant_free(self):
        from app.tenant.middleware import _is_tenant_free

        assert _is_tenant_free("/docs") is True
        assert _is_tenant_free("/openapi.json") is True
        assert _is_tenant_free("/redoc") is True

    def test_business_api_routes_are_tenant_scoped(self):
        from app.tenant.middleware import _is_tenant_free

        assert _is_tenant_free("/api/chats") is False
        assert _is_tenant_free("/api/workspaces") is False
        assert _is_tenant_free("/api/blackboard/history") is False
        assert _is_tenant_free("/api/memory/123/recall") is False

    def test_prefix_lookalikes_do_not_match(self):
        from app.tenant.middleware import _is_tenant_free

        # /api/orgschemas should NOT match /api/orgs
        assert _is_tenant_free("/api/orgschemas") is False
        assert _is_tenant_free("/api/authority") is False


class TestTenantMiddlewareDispatch:
    """Tests for TenantMiddleware.dispatch method."""

    async def test_tenant_free_paths_skip_tenant_processing(self):
        from app.tenant.middleware import TenantMiddleware
        from app.tenant.context import get_current_org, clear_current_org

        middleware = TenantMiddleware(app=MagicMock())

        tenant_free_paths = [
            "/",
            "/api/auth/login",
            "/api/orgs",
            "/api/notifications/stream",
            "/docs",
            "/openapi.json",
            "/redoc",
        ]

        for path in tenant_free_paths:
            clear_current_org()
            request = MagicMock(spec=Request)
            request.url.path = path
            request.state = MagicMock()
            request.headers.get = MagicMock(return_value=None)

            async def call_next(req):
                return JSONResponse({})

            await middleware.dispatch(request, call_next)
            assert get_current_org() is None, f"Failed for path: {path}"

    async def test_x_org_id_header_sets_tenant(self):
        from app.tenant.middleware import TenantMiddleware
        from app.tenant.context import get_current_org, clear_current_org

        middleware = TenantMiddleware(app=MagicMock())
        clear_current_org()

        request = MagicMock(spec=Request)
        request.url.path = "/api/chats"
        request.headers.get = MagicMock(return_value="acme-org")
        request.state = MagicMock()

        captured: dict = {}

        async def call_next(req):
            from app.tenant.context import get_current_org as gco
            captured["org"] = gco()
            return JSONResponse({})

        await middleware.dispatch(request, call_next)
        assert captured["org"] == "acme-org"
        # Context is cleared after request completes.
        assert get_current_org() is None

    async def test_missing_x_org_id_leaves_tenant_unset(self):
        from app.tenant.middleware import TenantMiddleware
        from app.tenant.context import get_current_org, clear_current_org

        middleware = TenantMiddleware(app=MagicMock())
        clear_current_org()

        request = MagicMock(spec=Request)
        request.url.path = "/api/workspaces"
        request.headers.get = MagicMock(return_value=None)
        request.state = MagicMock()

        async def call_next(req):
            return JSONResponse({})

        await middleware.dispatch(request, call_next)
        assert get_current_org() is None
        assert request.state.org_schema is None

    async def test_sets_org_schema_on_request_state(self):
        from app.tenant.middleware import TenantMiddleware
        from app.tenant.context import clear_current_org

        middleware = TenantMiddleware(app=MagicMock())
        clear_current_org()

        request = MagicMock(spec=Request)
        request.url.path = "/api/chats"
        request.headers.get = MagicMock(return_value="test-org")
        request.state = MagicMock()

        async def call_next(req):
            return JSONResponse({})

        await middleware.dispatch(request, call_next)
        assert request.state.org_schema == "org_test-org"

    async def test_clears_context_after_request(self):
        from app.tenant.middleware import TenantMiddleware
        from app.tenant.context import get_current_org, clear_current_org

        middleware = TenantMiddleware(app=MagicMock())
        clear_current_org()

        request = MagicMock(spec=Request)
        request.url.path = "/api/chats"
        request.headers.get = MagicMock(return_value="any-org")
        request.state = MagicMock()

        async def call_next(req):
            return JSONResponse({})

        await middleware.dispatch(request, call_next)
        assert get_current_org() is None
