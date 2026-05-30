"""
End-to-end verification that the TenantMiddleware actually plumbs the
``X-Org-ID`` header through to ``request.state.org_schema`` when a real
HTTP request flows through Starlette's middleware stack and lands on a
handler.

The middleware itself is exercised in
``tests/unit/test_tenant_middleware.py`` against a mocked Request. This
file complements that by running the full ASGI dispatch — middleware,
routing, handler — through ``httpx.AsyncClient``.

A self-contained Starlette app is used so the test does not depend on
the project's database fixtures or on any business route, but the
TenantMiddleware imported here is the exact same one wired into
``app.main``.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.tenant.middleware import TenantMiddleware
from app.tenant.context import clear_current_org

pytestmark = pytest.mark.asyncio


def _build_probe_app():
    """Return a tiny app whose only job is to echo the tenant context."""
    async def probe(request: Request):
        return JSONResponse(
            {"schema": getattr(request.state, "org_schema", None)}
        )

    app = Starlette(routes=[Route("/{path:path}", probe)])
    app.add_middleware(TenantMiddleware)
    return app


async def _get(client: AsyncClient, path: str, *, x_org_id: str | None = None):
    clear_current_org()
    headers = {"X-Org-ID": x_org_id} if x_org_id else {}
    response = await client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def test_x_org_id_header_sets_schema_on_business_route():
    transport = ASGITransport(app=_build_probe_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        data = await _get(client, "/api/chats", x_org_id="my-org")
        assert data["schema"] == "org_my-org"


async def test_missing_x_org_id_leaves_schema_none_on_business_route():
    transport = ASGITransport(app=_build_probe_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        data = await _get(client, "/api/workspaces")
        assert data["schema"] is None


async def test_tenant_free_routes_ignore_x_org_id():
    transport = ASGITransport(app=_build_probe_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # /api/auth, /api/orgs, /api/notifications, /docs, /openapi, /redoc
        # are all tenant-free even when a header is supplied.
        for path in ["/api/auth/login", "/api/orgs", "/api/notifications/stream", "/docs", "/openapi.json"]:
            data = await _get(client, path, x_org_id="should-be-ignored")
            assert data["schema"] is None, f"Expected no schema for {path}"


async def test_lookalike_prefixes_are_not_treated_as_tenant_free():
    transport = ASGITransport(app=_build_probe_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # /api/orgschemas should NOT match the /api/orgs tenant-free entry.
        data = await _get(client, "/api/orgschemas", x_org_id="acme")
        assert data["schema"] == "org_acme"
