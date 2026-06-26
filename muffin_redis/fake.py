"""FakeRedis support for testing without a real Redis server."""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING

from redis.asyncio import RedisError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


def create_fake_client(*, decode_responses: bool = True):
    """Create a FakeRedis client instance."""
    from fakeredis.aioredis import FakeRedis  # noqa: PLC0415

    return FakeRedis(decode_responses=decode_responses)


@asynccontextmanager
async def fake_lock(  # noqa: PLR0913
    client,
    name,
    *,
    timeout: float | None = 30,
    blocking: bool = True,
    blocking_timeout: float | None = None,
    sleep: float = 0.1,
) -> AsyncGenerator[bool]:
    """Acquire and release a lock using SET NX + DEL (no Lua)."""
    token = uuid.uuid4().hex.encode()
    timeout_ms = int(timeout * 1000) if timeout else None

    acquired = False
    deadline = None
    if blocking and blocking_timeout is not None:
        deadline = time.monotonic() + blocking_timeout

    while True:
        if await client.set(name, token, nx=True, px=timeout_ms):
            acquired = True
            break
        if not blocking:
            break
        if deadline is not None and time.monotonic() >= deadline:
            break
        await asyncio.sleep(sleep)

    try:
        yield acquired
    finally:
        if acquired:
            with suppress(RedisError):
                await client.delete(name)
