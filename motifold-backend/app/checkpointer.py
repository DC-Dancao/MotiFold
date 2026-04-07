import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.rows import dict_row

from app.config import settings

SYNC_DB_URL = settings.DATABASE_URL.replace("+asyncpg", "")
CHECKPOINTER_SETUP_LOCK_ID = 84125019

_checkpointer_ready = False
_checkpointer_ready_lock = asyncio.Lock()


async def ensure_checkpointer_ready() -> None:
    global _checkpointer_ready

    if _checkpointer_ready:
        return

    async with _checkpointer_ready_lock:
        if _checkpointer_ready:
            return

        async with await AsyncConnection.connect(
            SYNC_DB_URL,
            autocommit=True,
            prepare_threshold=0,
            row_factory=dict_row,
        ) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT pg_advisory_lock(%s)",
                    (CHECKPOINTER_SETUP_LOCK_ID,),
                )

            try:
                checkpointer = AsyncPostgresSaver(conn=conn)
                await checkpointer.setup()
            finally:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "SELECT pg_advisory_unlock(%s)",
                        (CHECKPOINTER_SETUP_LOCK_ID,),
                    )

        _checkpointer_ready = True


@asynccontextmanager
async def get_checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    await ensure_checkpointer_ready()

    async with AsyncPostgresSaver.from_conn_string(SYNC_DB_URL) as checkpointer:
        yield checkpointer
