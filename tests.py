import asyncio
import time

import muffin
import pytest
from asgi_tools._compat import aio_sleep, aio_spawn

from muffin_redis import Plugin


# Pin the suite to asyncio: `redis.asyncio` cannot run under trio/curio
@pytest.fixture(scope="module")
def aiolib():
    return "asyncio", {"loop_factory": None}


@pytest.fixture
async def app():
    return muffin.Application(debug=True)


@pytest.fixture
async def redis(app):
    redis = Plugin(app, fake=True)
    async with redis:
        yield redis
        await redis.flushall()


async def test_muffin_redis(redis):
    result = await redis.get("key")
    assert result is None

    await redis.set("key", "value", ex=10)
    result = await redis.get("key")
    assert result == "value"

    await redis.set("dict", {"now": time.time()}, jsonify=True)
    result = await redis.get("dict", jsonify=True)
    assert result
    assert "now" in result

    result = await redis.get("unknown")
    assert result is None


async def test_pool(app):
    async def block_conn(client):
        await asyncio.sleep(1e-2)
        return await client.ping()

    redis = Plugin(app, poolsize=2, fake=True)

    async with redis:
        res = await asyncio.gather(block_conn(redis), block_conn(redis), block_conn(redis))
        assert len(res) == 3


async def test_jsonnify(redis):
    res = await redis.get("l1", jsonify=True)
    assert res is None

    await redis.set("l1", "[1, 2, 3")
    res = await redis.get("l1", jsonify=True)
    assert res == "[1, 2, 3"

    await redis.set("l1", [1, 2, 3], jsonify=True)
    res = await redis.get("l1", jsonify=True)
    assert res == [1, 2, 3]


async def test_simple_lock(redis):
    async with redis.lock("l1") as lock:
        assert lock

        async with redis.lock("l2") as lock2:
            assert lock2

    async with redis.lock("l1") as lock:
        assert lock


async def test_lock_context(redis):
    async with redis.lock("ctx-lock", timeout=1, blocking=False) as acquired:
        assert acquired is True

        async with redis.lock("ctx-lock", timeout=1, blocking=False) as nested:
            assert nested is False

    async with redis.lock("ctx-lock", timeout=1, blocking=False) as acquired:
        assert acquired is True


async def test_lock_blocking_timeout(redis):
    async with redis.lock("blocking", timeout=1) as acquired:
        assert acquired is True

        started = time.monotonic()
        async with redis.lock("blocking", blocking_timeout=0.2) as waited:
            assert waited is False
        assert time.monotonic() - started >= 0.2

    async with redis.lock("blocking") as acquired:
        assert acquired is True


async def test_muffin_redis_pubsub(redis):
    async def reader(channel_name: str):
        async def callback(channel):
            while True:
                msg = await channel.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg:
                    return msg["data"]

        async with redis.pubsub() as psub:
            await psub.subscribe(channel_name)
            res = await callback(psub)
            await psub.unsubscribe(channel_name)

        return res

    async with aio_spawn(reader, "chan:1") as task:
        await aio_sleep(0.1)
        await redis.publish("chan:1", "test")
        await aio_sleep(0.1)

    assert task.result() == "test"
