import os
import asyncio
from app.mcp.server import create_mcp_server, _current_user_id

def main() -> None:
    """Start the Motifold MCP server with local defaults (stdio transport)."""
    
    # By default, we use user_id = 1 for local stdio MCP interactions unless overridden
    user_id = os.environ.get("MOTIFOLD_MCP_USER_ID", "1")
    try:
        user_id = int(user_id)
    except ValueError:
        user_id = 1
        
    _current_user_id.set(user_id)
    
    mcp_server = create_mcp_server()
    mcp_server.run()

if __name__ == "__main__":
    main()
