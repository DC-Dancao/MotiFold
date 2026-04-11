"""
Tenant resolution middleware for multi-tenancy support.

Extracts X-Org-ID header and sets the request-local tenant context.
Sets PostgreSQL search_path to the org's schema for data isolation.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi import HTTPException
from app.tenant.context import set_current_org, clear_current_org, get_schema_name

HEADER_ORG_ID = "x-org-id"

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        org_slug = request.headers.get(HEADER_ORG_ID)

        if org_slug:
            # Validate slug format (alphanumeric + underscore/dash only)
            if not org_slug.replace('_', '').replace('-', '').isalnum():
                raise HTTPException(status_code=400, detail="Invalid org slug format")
            set_current_org(org_slug)
            request.state.org_schema = get_schema_name(org_slug)
        else:
            set_current_org(None)
            request.state.org_schema = None

        try:
            response = await call_next(request)
            return response
        finally:
            clear_current_org()
