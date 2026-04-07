import json
import logging
import os
from contextvars import ContextVar
from fastapi import Request

from fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import _get_user_by_token
from app.database import AsyncSessionLocal
from app.mcp_tools import MCPToolsConfig, register_mcp_tools

# Configure logging
logger = logging.getLogger(__name__)

# Context variable to hold the current user_id for MCP requests
_current_user_id: ContextVar[int | None] = ContextVar("current_user_id", default=None)

def get_current_user_id() -> int | None:
    """Get the current user_id from context."""
    return _current_user_id.get()

def create_mcp_server() -> FastMCP:
    """
    Create and configure the Motifold MCP server.
    """
    mcp = FastMCP("motifold-mcp-server")

    # Configure and register tools
    config = MCPToolsConfig(
        user_id_resolver=get_current_user_id,
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
        # Compatibility with FastMCP versions
        if hasattr(mcp, "_tool_manager"):
            tools_dict = mcp._tool_manager._tools
        elif hasattr(mcp, "tools"):
            tools_dict = {t.name: t for t in mcp.tools}
        else:
            return
            
        for name, tool in tools_dict.items():
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
            self.mcp_app = self.mcp_server.http_app(transport="sse")

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

        # Extract auth token from header
        auth_header = self._get_header(scope, "Authorization")
        auth_token: str | None = None
        if auth_header:
            auth_token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else auth_header.strip()

        if not auth_token:
            # Check for a static API key just in case we are in development mode
            local_api_key = os.environ.get("MOTIFOLD_MCP_AUTH_TOKEN")
            if local_api_key:
                # If they didn't provide a token, but we have a static one, we fail auth
                await self._send_error(send, 401, "Authorization header required")
                return

        # Authenticate token
        user_id = None
        if auth_token:
            local_api_key = os.environ.get("MOTIFOLD_MCP_AUTH_TOKEN")
            if local_api_key and auth_token == local_api_key:
                # Local override for testing, we can pretend to be a superuser or the first user
                # We will assign user_id = 1 for local debugging if static token matches
                user_id = 1
            else:
                try:
                    async with AsyncSessionLocal() as session:
                        user = await _get_user_by_token(auth_token, session)
                        user_id = user.id
                except Exception as e:
                    await self._send_error(send, 401, f"Authentication failed: {str(e)}")
                    return

        if not user_id:
            await self._send_error(send, 401, "Valid Authentication required for MCP")
            return

        # Set user_id context
        user_id_token = _current_user_id.set(user_id)
        
        try:
            new_scope = scope.copy()
            # Strip prefix from path for the mcp app routing
            new_path = path[len(self.prefix) :] or "/"
            new_scope["path"] = new_path
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
