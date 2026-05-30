"""
Tenant resolution middleware for multi-tenancy support.

Reads the tenant org slug from the ``X-Org-ID`` request header and pushes
it into the per-request context so downstream queries can scope to the
correct PostgreSQL schema.

After the routing refactor, every business endpoint lives under ``/api/*``
and is tenant-scoped, with three exceptions that operate outside any
single tenant:

* ``/api/auth/*``   – signup, login, refresh, API keys
* ``/api/orgs/*``   – org CRUD itself
* ``/api/notifications/*`` – SSE stream that picks its own filter
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.tenant.context import set_current_org, clear_current_org, get_schema_name
import logging

logger = logging.getLogger(__name__)

# Path prefixes that bypass tenant resolution entirely.
# Some entries (``/docs``, ``/openapi``, ``/redoc``) are matched as bare
# prefixes so that ``/openapi.json`` and ``/docs/oauth2-redirect`` are
# both covered. The ``/api/...`` entries match with a path-segment
# boundary so that look-alikes like ``/api/orgschemas`` are not silently
# treated as tenant-free.
_TENANT_FREE_SEGMENT_PREFIXES: tuple[str, ...] = (
    "/api/auth",
    "/api/orgs",
    "/api/notifications",
)
_TENANT_FREE_BARE_PREFIXES: tuple[str, ...] = (
    "/docs",
    "/openapi",
    "/redoc",
)


def _is_tenant_free(path: str) -> bool:
    if path == "/":
        return True
    if any(path.startswith(prefix) for prefix in _TENANT_FREE_BARE_PREFIXES):
        return True
    return any(
        path == prefix or path.startswith(prefix + "/")
        for prefix in _TENANT_FREE_SEGMENT_PREFIXES
    )


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if _is_tenant_free(path):
            set_current_org(None)
            request.state.org_schema = None
            return await call_next(request)

        org_slug = request.headers.get("X-Org-ID")
        if org_slug:
            set_current_org(org_slug)
            request.state.org_schema = get_schema_name(org_slug)
        else:
            set_current_org(None)
            request.state.org_schema = None

        try:
            return await call_next(request)
        finally:
            clear_current_org()
