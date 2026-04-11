import pytest
from app.mcp.server import create_mcp_server

def test_mcp_server_creation():
    """Test that MCP server can be created with all default tools."""
    mcp = create_mcp_server()
    assert mcp is not None
    # Verify expected tool count - FastMCP 3.x stores tools in _local_provider._components
    # Keys are like 'tool:workspace_list@'
    components = mcp._local_provider._components
    tool_names = {k.split(":")[1][:-1] for k in components if k.startswith("tool:")}
    expected = {
        "workspace_list", "workspace_get", "workspace_create", "workspace_delete",
        "chat_list", "chat_get", "chat_create", "chat_send_message", "chat_get_history",
        "matrix_list_analyses", "matrix_get_analysis", "matrix_start_analysis",
        "matrix_evaluate_consistency", "matrix_save_analysis", "matrix_delete_analysis",
        "blackboard_list", "blackboard_get", "blackboard_generate", "blackboard_delete",
        "research_list_reports", "research_get_report", "research_start",
        "research_get_result", "research_get_state", "research_delete_report",
        "operation_list", "operation_get_status",
    }
    assert expected.issubset(tool_names), f"Missing: {expected - tool_names}"
