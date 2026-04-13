import json
import logging
import os
from contextvars import ContextVar
from fastapi import Request

from fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.future import select

from app.core.security import _get_user_by_token
from app.core.database import AsyncSessionLocal
from app.mcp.tools import MCPToolsConfig, register_mcp_tools
from app.org.models import Organization, OrganizationMember
from app.tenant.context import get_schema_name

# Configure logging
logger = logging.getLogger(__name__)

# Context variables for MCP requests
_current_user_id: ContextVar[int | None] = ContextVar("current_user_id", default=None)
_current_org_slug: ContextVar[str | None] = ContextVar("current_org_slug", default=None)
_current_org_schema: ContextVar[str | None] = ContextVar("current_org_schema", default=None)

def get_current_user_id() -> int | None:
    """Get the current user_id from context."""
    return _current_user_id.get()

def get_current_org_slug() -> str | None:
    """Get the current org slug from context."""
    return _current_org_slug.get()

def get_current_org_schema() -> str | None:
    """Get the current org schema from context."""
    return _current_org_schema.get()


def _is_valid_org_slug(org_slug: str) -> bool:
    """Validate org_slug to prevent search_path injection."""
    if not org_slug:
        return False
    # Must be alphanumeric with underscores/dashes only, and not pure underscore/dash
    if not (org_slug.replace("_", "").replace("-", "").isalnum() and org_slug.replace("_", "").replace("-", "")):
        return False
    # Must not start with digit
    if org_slug[0].isdigit():
        return False
    # Reserved names that could cause issues
    if org_slug.lower() in ("public", "pg_catalog", "information_schema"):
        return False
    # Length limit
    if len(org_slug) > 64:
        return False
    return True


def create_mcp_server() -> FastMCP:
    """
    Create and configure the Motifold MCP server.
    """
    mcp = FastMCP("motifold-mcp-server")

    # Configure and register tools
    config = MCPToolsConfig(
        user_id_resolver=get_current_user_id,
        org_slug_resolver=get_current_org_slug,
        org_schema_resolver=get_current_org_schema,
        tools=None, # Register all default tools
    )

    register_mcp_tools(mcp, config)

    # Make all tools tolerant of extra arguments from LLMs
    _make_tools_tolerant(mcp)

    return mcp

def _make_tools_tolerant(mcp: FastMCP) -> None:
    """Wrap all tool run methods to strip unknown arguments before validation.

    LLMs frequently add extra fields like "explanation" or "reasoning" to tool calls.
    FastMCP's Pydantic TypeAdapter rejects these with "Unexpected keyword argument".
    This wraps each tool's run() to filter arguments to only known parameters.
    """
    try:
        # FastMCP 3.x stores tools in _local_provider._components
        # Keys are like 'tool:workspace_list@', values are FunctionTool objects
        components = mcp._local_provider._components

        for key, tool in components.items():
            if not key.startswith("tool:"):
                continue
            if hasattr(tool, "parameters") and tool.parameters:
                allowed = set(tool.parameters.get("properties", {}).keys())

                # Check for run method
                if hasattr(tool, "run"):
                    original_run = tool.run
                    async def _tolerant_run(arguments, _allowed=allowed, _orig=original_run):
                        extra_keys = set(arguments.keys()) - _allowed
                        if extra_keys:
                            logger.debug(f"Stripping unknown arguments from tool call: {extra_keys}")
                            arguments = {k: v for k, v in arguments.items() if k in _allowed}
                        return await _orig(arguments)

                    object.__setattr__(tool, "run", _tolerant_run)
    except Exception as e:
        logger.warning(f"Could not make tools tolerant of extra arguments: {e}")

class MCPMiddleware:
    """ASGI middleware that intercepts MCP requests and routes to the MCP server.

    This middleware wraps the main FastAPI app and intercepts requests matching the
    configured prefix (default: /mcp). Non-MCP requests pass through to the inner app.

    Authentication:
        Validates against the provided Bearer token (JWT) using Motifold's auth system.
        Alternatively, accepts a direct API key if configured.
    """

    def __init__(
        self,
        app,
        prefix: str = "/mcp",
        mcp_app=None,
    ):
        self.app = app
        self.prefix = prefix
        
        if mcp_app:
            self.mcp_app = mcp_app
        else:
            self.mcp_server = create_mcp_server()
            self.mcp_app = self.mcp_server.http_app(transport="streamable-http")

    def _get_header(self, scope: dict, name: str) -> str | None:
        """Extract a header value from ASGI scope."""
        name_lower = name.lower().encode()
        for header_name, header_value in scope.get("headers", []):
            if header_name.lower() == name_lower:
                return header_value.decode()
        return None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Check if this is an MCP request (matches prefix)
        if not (path == self.prefix or path.startswith(self.prefix + "/")):
            # Not an MCP request — pass through to the inner app
            await self.app(scope, receive, send)
            return

        # Extract auth token, API key, and org context from headers
        auth_header = self._get_header(scope, "Authorization")
        api_key_header = self._get_header(scope, "X-API-Key")
        org_slug = self._get_header(scope, "X-Org-ID")
        auth_token: str | None = None
        if auth_header:
            auth_token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else auth_header.strip()

        # Determine if auth is required
        has_auth = bool(auth_token) or bool(api_key_header)
        if not has_auth and os.environ.get("MOTIFOLD_MCP_AUTH_TOKEN"):
            await self._send_error(send, 401, "Authorization header or X-API-Key required")
            return

        if not org_slug:
            await self._send_error(send, 400, "X-Org-ID header required")
            return
        if not _is_valid_org_slug(org_slug):
            await self._send_error(send, 400, "Invalid org slug format")
            return

        # Authenticate and validate org membership
        user_id: int | None = None
        org_id_from_key: int | None = None
        try:
            async with AsyncSessionLocal() as session:
                # 1. API key auth (takes precedence)
                if api_key_header:
                    import hashlib
                    from datetime import datetime, UTC
                    from app.auth.models import ApiKey
                    key_hash = hashlib.sha256(api_key_header.encode()).hexdigest()
                    key_result = await session.execute(
                        select(ApiKey).where(ApiKey.key_hash == key_hash)
                    )
                    api_key = key_result.scalars().first()
                    if not api_key:
                        await self._send_error(send, 401, "Invalid API key")
                        return
                    if api_key.expires_at and api_key.expires_at < datetime.now(UTC):
                        await self._send_error(send, 401, "API key expired")
                        return
                    user_id = api_key.user_id
                    org_id_from_key = api_key.organization_id
                    # Update last used
                    api_key.last_used_at = datetime.now(UTC)
                    await session.commit()

                # 2. Bearer token auth
                elif auth_token:
                    local_api_key = os.environ.get("MOTIFOLD_MCP_AUTH_TOKEN")
                    if local_api_key and auth_token == local_api_key:
                        user_id = 1  # Local debug override
                    else:
                        user = await _get_user_by_token(auth_token, session)
                        user_id = user.id

                if not user_id:
                    await self._send_error(send, 401, "Valid Authentication required for MCP")
                    return

                org_result = await session.execute(
                    select(Organization).where(Organization.slug == org_slug)
                )
                org = org_result.scalars().first()
                if not org:
                    await self._send_error(send, 404, "Organization not found")
                    return
                if org.status != "active":
                    await self._send_error(send, 503, "Organization not active")
                    return

                # If auth was via API key, verify key belongs to this org
                if org_id_from_key is not None and org_id_from_key != org.id:
                    await self._send_error(send, 403, "API key not valid for this organization")
                    return

                membership_result = await session.execute(
                    select(OrganizationMember).where(
                        OrganizationMember.organization_id == org.id,
                        OrganizationMember.user_id == user_id,
                    )
                )
                membership = membership_result.scalars().first()
                if not membership:
                    await self._send_error(send, 403, "Not a member of this organization")
                    return

                org_result = await session.execute(
                    select(Organization).where(Organization.slug == org_slug)
                )
                org = org_result.scalars().first()
                if not org:
                    await self._send_error(send, 404, "Organization not found")
                    return
                if org.status != "active":
                    await self._send_error(send, 503, "Organization not active")
                    return

                membership_result = await session.execute(
                    select(OrganizationMember).where(
                        OrganizationMember.organization_id == org.id,
                        OrganizationMember.user_id == user_id,
                    )
                )
                membership = membership_result.scalars().first()
                if not membership:
                    await self._send_error(send, 403, "Not a member of this organization")
                    return
        except Exception as e:
            await self._send_error(send, 401, f"Authentication failed: {str(e)}")
            return

        # Set request context
        user_id_token = _current_user_id.set(user_id)
        org_slug_token = _current_org_slug.set(org_slug)
        org_schema_token = _current_org_schema.set(get_schema_name(org_slug) if org_slug else None)

        try:
            new_scope = scope.copy()
            # Pass the original path to the MCP app.
            new_scope["path"] = path
            new_scope["root_path"] = ""

            # Ensure Accept header includes required MIME types for MCP SDK.
            accept_header = self._get_header(new_scope, "accept")
            if not accept_header or "text/event-stream" not in accept_header:
                headers = [(k, v) for k, v in new_scope.get("headers", []) if k.lower() != b"accept"]
                headers.append((b"accept", b"application/json, text/event-stream"))
                new_scope["headers"] = headers

            await self.mcp_app(new_scope, receive, send)
        finally:
            _current_user_id.reset(user_id_token)
            _current_org_slug.reset(org_slug_token)
            _current_org_schema.reset(org_schema_token)

    async def _send_error(self, send, status: int, message: str, extra_headers: dict[str, str] | None = None):
        """Send an error response."""
        body = json.dumps({"error": message}).encode()
        headers = [(b"content-type", b"application/json")]
        for key, value in (extra_headers or {}).items():
            headers.append((key.encode(), value.encode()))
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": headers,
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })
