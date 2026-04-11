from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
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
from app.mcp.server import MCPMiddleware
from app.memory.router import router as memory_router

# Import all models so Alembic/SQLAlchemy can find them via Base.metadata
from app.auth.models import User  # noqa: F401
from app.workspace.models import Workspace  # noqa: F401
from app.chat.models import Chat, Message  # noqa: F401
from app.matrix.models import Keyword, MorphologicalAnalysis  # noqa: F401
from app.blackboard.models import BlackboardData  # noqa: F401
from app.memory.models import MemoryBank, MemoryUnit, Entity  # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await ensure_schema_ready()
    await ensure_checkpointer_ready()
    # Initialize embedding service for memory
    try:
        from app.memory.embedding import init_embedding_service
        await init_embedding_service()
    except ModuleNotFoundError:
        logger.warning("Embedding service dependencies not installed; memory embeddings disabled", exc_info=True)
    except Exception:
        logger.warning("Failed to initialize embedding service; memory embeddings disabled", exc_info=True)
    yield
    await close_redis_clients()


app = FastAPI(title="Motifold Chat MVP", lifespan=lifespan)

# Add MCP Middleware (it intercepts /mcp)
app.add_middleware(MCPMiddleware, prefix="/mcp")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(workspace_router, prefix="/workspaces", tags=["workspaces"])
app.include_router(chat_router, prefix="/chats", tags=["chats"])
app.include_router(matrix_router)
app.include_router(notification_router)
app.include_router(blackboard_router)
app.include_router(research_router)
app.include_router(memory_router)

@app.get("/")
def read_root():
    return {"message": "Welcome to Motifold API"}
