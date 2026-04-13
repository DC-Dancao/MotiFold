from contextlib import asynccontextmanager
import asyncio
import logging

from app.core.config import settings

# Configure logging for app modules
log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(level=log_level, format='%(name)s - %(levelname)s - %(message)s')
for logger_name in ['app', 'uvicorn', 'uvicorn.error', 'uvicorn.access']:
    logging.getLogger(logger_name).setLevel(log_level)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.llm.checkpointer import ensure_checkpointer_ready
from app.core.database import ensure_schema_ready
from app.matrix.stream import close_redis_clients
from app.auth.router import router as auth_router
from app.workspace.router import router as workspace_router
from app.chat.router import router as chat_router
from app.matrix.router import router as matrix_router
from app.notification.router import router as notification_router
from app.blackboard.router import router as blackboard_router
from app.research.router import router as research_router
from app.tenant.middleware import TenantMiddleware
from app.org.router import router as org_router
from app.memory.router import router as memory_router
from app.stats.router import router as stats_router

# Import all models so Alembic/SQLAlchemy can find them via Base.metadata
from app.auth.models import User  # noqa: F401
from app.workspace.models import Workspace  # noqa: F401
from app.chat.models import Chat, Message  # noqa: F401
from app.matrix.models import Keyword, MorphologicalAnalysis  # noqa: F401
from app.blackboard.models import BlackboardData  # noqa: F401
from app.memory.models import MemoryBank, MemoryUnit, Entity  # noqa: F401
from app.org.models import Organization, OrganizationMember  # noqa: F401

logger = logging.getLogger(__name__)

# Create MCP server and HTTP app once at module level so lifespan is shared with FastAPI
from app.mcp.server import create_mcp_server, MCPMiddleware
_mcp_server = create_mcp_server()
_mcp_http_app = _mcp_server.http_app(transport="streamable-http")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await ensure_schema_ready()
    await ensure_checkpointer_ready()
    # Note: embedding service is lazy-loaded on first use to avoid blocking startup
    yield
    await close_redis_clients()


@asynccontextmanager
async def combined_lifespan(app: FastAPI):
    # Enter both the MCP lifespan (FastMCP session manager) and FastAPI's own lifespan
    # The MCP lifespan needs the FastAPI app instance
    async with _mcp_http_app.lifespan(app):
        async with lifespan(app):
            yield


app = FastAPI(title="Motifold Chat MVP", lifespan=combined_lifespan)

# Add Tenant Middleware (must be first)
app.add_middleware(TenantMiddleware)

# Add MCP Middleware (it intercepts /mcp), passing the pre-created HTTP app
app.add_middleware(MCPMiddleware, prefix="/mcp", mcp_app=_mcp_http_app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(org_router, prefix="/api/orgs", tags=["organizations"])
app.include_router(workspace_router, prefix="/workspaces", tags=["workspaces"])
app.include_router(chat_router, prefix="/chats", tags=["chats"])
app.include_router(matrix_router, tags=["matrix"])
app.include_router(notification_router, tags=["notification"])
app.include_router(blackboard_router, tags=["blackboard"])
app.include_router(research_router, tags=["research"])
app.include_router(memory_router, tags=["memory"])
app.include_router(stats_router, tags=["stats"])

@app.get("/")
def read_root():
    return {"message": "Welcome to Motifold API"}
