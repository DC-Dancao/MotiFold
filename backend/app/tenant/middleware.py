"""
Tenant resolution middleware for multi-tenancy support.

Extracts org_slug from X-Org-ID header (preferred) or URL path: /{org_slug}/api/...
Sets PostgreSQL search_path to the org's schema for data isolation.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import HTTPException
from app.tenant.context import set_current_org, clear_current_org, get_schema_name
import logging

logger = logging.getLogger(__name__)

# Paths that should not be parsed as org-scoped
PUBLIC_PATHS = {"/", "/auth", "/docs", "/openapi.json", "/redoc", "/notifications"}


def _get_org_slug_from_path(path: str) -> str | None:
    """Parse org_slug from URL path like /{org_slug}/resource."""
    parts = path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] and parts[1]:
        org_slug = parts[0]
        if not org_slug.replace('_', '').replace('-', '').isalnum():
            return None
        return org_slug
    return None


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip non-org paths (exact match or auth/docs prefix)
        if path == "/" or path.startswith("/auth") or path.startswith("/docs") or path.startswith("/openapi") or path.startswith("/redoc") or path.startswith("/notifications"):
            set_current_org(None)
            request.state.org_schema = None
            return await call_next(request)

        # Skip /api and /stats prefixes (API routes, not org-scoped)
        if path.startswith("/api/") or path.startswith("/stats"):
            set_current_org(None)
            request.state.org_schema = None
            return await call_next(request)

        # Try X-Org-ID header first (from frontend)
        x_org_id = request.headers.get("X-Org-ID")
        logger.info(f"TenantMiddleware: path=%s, X-Org-ID=%s", path, x_org_id)

        # Fall back to URL path parsing
        org_slug = x_org_id or _get_org_slug_from_path(path)

        if org_slug:
            set_current_org(org_slug)
            request.state.org_schema = get_schema_name(org_slug)

            # Rewrite path to strip org prefix if present
            parts = path.strip("/").split("/")
            if len(parts) >= 2 and parts[0] == org_slug:
                new_path = "/" + "/".join(parts[1:])
                request.scope["path"] = new_path
        else:
            set_current_org(None)
            request.state.org_schema = None

        try:
            response = await call_next(request)
            return response
        finally:
            clear_current_org()
