import asyncio

import muffin
import pytest


@pytest.fixture(scope="session")
def aiolib():
    """Disable uvloop for tests."""
    return ("asyncio", {"use_uvloop": False})


@pytest.fixture
async def app():
    return muffin.Application(debug=True)


@pytest.fixture
async def redis(app):
    from muffin_redis import Plugin

    redis = Plugin(app, redislite=True)
    async with redis:
        yield redis
        await redis.flushall()


async def test_muffin_redis(redis):
    result = await redis.get("key")
    assert result is None

    await redis.set("key", "value", ex=10)
    result = await redis.get("key")
    assert result == "value"

    import time

    await redis.set("dict", {"now": time.time()}, jsonify=True)
    result = await redis.get("dict", jsonify=True)
    assert result
    assert "now" in result

    result = await redis.get("unknown")
    assert result is None


async def test_pool(app):
    from muffin_redis import Plugin as Redis

    async def block_conn(client):
        await asyncio.sleep(1e-2)
        return await client.info()

    redis = Redis(app, poolsize=2, redislite=True)

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


async def test_muffin_redis_pubsub(redis):
    from asgi_tools._compat import aio_sleep, aio_spawn

    async def reader(channel_name: str):
        async def callback(channel):
            while True:
                msg = await channel.get_message(ignore_subscribe_messages=True)
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
