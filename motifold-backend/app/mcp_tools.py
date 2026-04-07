import json
import logging
from dataclasses import dataclass
from typing import Callable, Any

from fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import AsyncSessionLocal
from app.models import Workspace, Chat, Message
from app.blackboard_agent import run_blackboard_agent

logger = logging.getLogger(__name__)

@dataclass
class MCPToolsConfig:
    """Configuration for MCP tools registration."""
    # How to resolve user_id for operations
    user_id_resolver: Callable[[], int | None]
    
    # How to resolve API key or token if needed
    auth_token_resolver: Callable[[], str | None] | None = None
    
    # Which tools to register
    tools: set[str] | None = None  # None means all tools


def register_mcp_tools(mcp: FastMCP, config: MCPToolsConfig) -> None:
    """Register MCP tools on a FastMCP server."""
    tools_to_register = config.tools or {
        "list_workspaces",
        "list_chats",
        "get_chat_history",
        "generate_blackboard"
    }

    if "list_workspaces" in tools_to_register:
        _register_list_workspaces(mcp, config)
        
    if "list_chats" in tools_to_register:
        _register_list_chats(mcp, config)
        
    if "get_chat_history" in tools_to_register:
        _register_get_chat_history(mcp, config)
        
    if "generate_blackboard" in tools_to_register:
        _register_generate_blackboard(mcp, config)


def _register_list_workspaces(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def list_workspaces() -> str:
        """
        List all available workspaces for the authenticated user.
        
        Returns:
            JSON list of workspaces with their IDs and names.
        """
        user_id = config.user_id_resolver()
        if user_id is None:
            return json.dumps({"error": "Unauthorized: No user_id configured"})
            
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Workspace).where(Workspace.user_id == user_id))
                workspaces = result.scalars().all()
                return json.dumps({
                    "workspaces": [
                        {"id": w.id, "name": w.name, "created_at": w.created_at.isoformat()} 
                        for w in workspaces
                    ]
                })
        except Exception as e:
            logger.error(f"Error listing workspaces: {e}", exc_info=True)
            return json.dumps({"error": str(e)})


def _register_list_chats(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def list_chats(workspace_id: int | None = None) -> str:
        """
        List chats for the authenticated user, optionally filtered by workspace.
        
        Args:
            workspace_id: Optional workspace ID to filter chats.
            
        Returns:
            JSON list of chats.
        """
        user_id = config.user_id_resolver()
        if user_id is None:
            return json.dumps({"error": "Unauthorized: No user_id configured"})
            
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(Chat).where(Chat.user_id == user_id)
                if workspace_id is not None:
                    stmt = stmt.where(Chat.workspace_id == workspace_id)
                
                result = await session.execute(stmt)
                chats = result.scalars().all()
                return json.dumps({
                    "chats": [
                        {
                            "id": c.id, 
                            "title": c.title, 
                            "workspace_id": c.workspace_id,
                            "created_at": c.created_at.isoformat()
                        } 
                        for c in chats
                    ]
                })
        except Exception as e:
            logger.error(f"Error listing chats: {e}", exc_info=True)
            return json.dumps({"error": str(e)})


def _register_get_chat_history(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def get_chat_history(chat_id: int, limit: int = 50) -> str:
        """
        Get the message history of a specific chat.
        
        Args:
            chat_id: The ID of the chat.
            limit: Maximum number of recent messages to return (default 50).
            
        Returns:
            JSON list of messages in the chat.
        """
        user_id = config.user_id_resolver()
        if user_id is None:
            return json.dumps({"error": "Unauthorized: No user_id configured"})
            
        try:
            async with AsyncSessionLocal() as session:
                # Verify chat belongs to user
                chat_result = await session.execute(select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id))
                chat = chat_result.scalars().first()
                if not chat:
                    return json.dumps({"error": f"Chat {chat_id} not found or unauthorized"})
                    
                msg_result = await session.execute(
                    select(Message)
                    .where(Message.chat_id == chat_id)
                    .order_by(Message.created_at.desc())
                    .limit(limit)
                )
                messages = msg_result.scalars().all()
                messages.reverse() # Chronological order
                
                return json.dumps({
                    "messages": [
                        {
                            "id": m.id,
                            "role": m.role,
                            "content": m.content,
                            "created_at": m.created_at.isoformat()
                        }
                        for m in messages
                    ]
                })
        except Exception as e:
            logger.error(f"Error getting chat history: {e}", exc_info=True)
            return json.dumps({"error": str(e)})


def _register_generate_blackboard(mcp: FastMCP, config: MCPToolsConfig) -> None:
    @mcp.tool()
    async def generate_blackboard(topic: str) -> str:
        """
        Generate a visual blackboard teaching layout for a given topic.
        
        Args:
            topic: The educational topic to explain (e.g. "Quantum Mechanics", "React Hooks").
            
        Returns:
            JSON representing the generated blackboard steps and blocks.
        """
        # User auth check is optional for this agent but good to have
        user_id = config.user_id_resolver()
        if user_id is None:
            return json.dumps({"error": "Unauthorized: No user_id configured"})
            
        try:
            result = await run_blackboard_agent(topic)
            return json.dumps({"topic": topic, "result": result})
        except Exception as e:
            logger.error(f"Error generating blackboard: {e}", exc_info=True)
            return json.dumps({"error": str(e)})
