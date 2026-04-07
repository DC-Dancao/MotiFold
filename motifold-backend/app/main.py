from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.checkpointer import ensure_checkpointer_ready
from app.database import ensure_schema_ready
from app.routers import auth_router, chat_router, workspace_router, matrix_router, notification_router, blackboard_router
from app.mcp_server import MCPMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI):
    await ensure_schema_ready()
    await ensure_checkpointer_ready()
    yield


app = FastAPI(title="Motifold Chat MVP", lifespan=lifespan)

# Add MCP Middleware (it intercepts /mcp)
app.add_middleware(MCPMiddleware, prefix="/mcp")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000", "http://localhost:8001"], # Must specify origins if allow_credentials is True
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/auth", tags=["auth"])
app.include_router(workspace_router.router, prefix="/workspaces", tags=["workspaces"])
app.include_router(chat_router.router, prefix="/chats", tags=["chats"])
app.include_router(matrix_router.router)
app.include_router(notification_router.router)
app.include_router(blackboard_router.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to Motifold API"}

