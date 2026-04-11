"""
Request-local tenant context using ContextVars.

This module provides async-safe, request-local storage for the current
organization slug. The context is set by TenantMiddleware and cleared
after each request.
"""
from contextvars import ContextVar
from typing import Optional

_current_org_slug: ContextVar[Optional[str]] = ContextVar('current_org_slug', default=None)

def set_current_org(org_slug: Optional[str]) -> None:
    _current_org_slug.set(org_slug)

def get_current_org() -> Optional[str]:
    return _current_org_slug.get()

def get_schema_name(org_slug: str) -> str:
    """Convert org slug to schema name (org_{slug})."""
    return f"org_{org_slug}"

def clear_current_org() -> None:
    _current_org_slug.set(None)
