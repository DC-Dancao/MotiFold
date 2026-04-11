# backend/tests/fixtures/factories.py
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.models import User
from app.workspace.models import Workspace
from app.chat.models import Chat


class UserFactory:
    """Factory for creating test User instances."""

    @staticmethod
    async def create(
        session: AsyncSession,
        username: str = "testuser",
        password_hash: Optional[str] = None,
        **kwargs: Any,
    ) -> User:
        if password_hash is None:
            password_hash = "fakehash"
        user = User(username=username, password_hash=password_hash, **kwargs)
        session.add(user)
        await session.flush()
        return user


class WorkspaceFactory:
    """Factory for creating test Workspace instances."""

    @staticmethod
    async def create(
        session: AsyncSession,
        user_id: int,
        name: str = "Test Workspace",
        **kwargs: Any,
    ) -> Workspace:
        ws = Workspace(user_id=user_id, name=name, **kwargs)
        session.add(ws)
        await session.flush()
        return ws


class ChatFactory:
    """Factory for creating test Chat instances."""

    @staticmethod
    async def create(
        session: AsyncSession,
        workspace_id: int,
        title: str = "New Chat",
        **kwargs: Any,
    ) -> Chat:
        chat = Chat(workspace_id=workspace_id, title=title, **kwargs)
        session.add(chat)
        await session.flush()
        return chat
