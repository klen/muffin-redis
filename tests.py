import asyncio
import muffin
import pytest


@pytest.fixture(scope='session')
def aiolib():
    """Disable uvloop for tests."""
    return ('asyncio', {'use_uvloop': False})


@pytest.fixture
async def app(redis_url):
    from muffin_redis import Plugin as Redis

    app = muffin.Application(debug=True)
    redis = Redis(app, url=redis_url)
    async with app.lifespan:
        yield app
        await redis.flushall()


async def test_muffin_redis(app):
    redis = app.plugins['redis']

    result = await redis.get('key')
    assert result is None

    await redis.set('key', 'value', ex=10)
    result = await redis.get('key')
    assert result == 'value'

    import time
    await redis.set('dict', {'now': time.time()}, jsonify=True)
    result = await redis.get('dict', jsonify=True)
    assert result and 'now' in result

    result = await redis.get('unknown')
    assert result is None


async def test_pool(redis_url):
    from muffin_redis import Plugin as Redis

    app = muffin.Application(REDIS_URL=redis_url)

    async def block_conn(client):
        async with client:
            await asyncio.sleep(1e-2)
            return await client.info()

    redis = Redis(app, poolsize=2)
    await redis.startup()

    res = await asyncio.gather(block_conn(redis), block_conn(redis), block_conn(redis))
    assert res
    assert len(res) == 3
    await redis.shutdown()

    redis = Redis(app, poolsize=2, blocking=False)
    await redis.startup()

    with pytest.raises(redis.Error):
        await asyncio.gather(block_conn(redis), block_conn(redis), block_conn(redis))
    await redis.shutdown()


async def test_jsonnify(app):
    redis = app.plugins['redis']

    res = await redis.get('l1', jsonify=True)
    assert res is None

    await redis.set('l1', "[1, 2, 3")
    res = await redis.get('l1', jsonify=True)
    assert res == '[1, 2, 3'

    await redis.set('l1', [1, 2, 3], jsonify=True)
    res = await redis.get('l1', jsonify=True)
    assert res == [1, 2, 3]


async def test_simple_lock(app):
    redis = app.plugins['redis']

    async with redis.lock('l1') as lock:
        assert lock

        async with redis.lock('l2') as lock2:
            assert lock2

    async with redis.lock('l1') as lock:
        assert lock


async def test_muffin_redis_pubsub(app):
    from asgi_tools._compat import aio_spawn, aio_sleep

    redis = app.plugins['redis']

    async def reader(channel_name: str):

        async def callback(channel):
            while True:
                msg = await channel.get_message(ignore_subscribe_messages=True)
                if msg:
                    return msg['data']

        async with redis.pubsub() as psub:
            await psub.subscribe(channel_name)
            res = await callback(psub)
            await psub.unsubscribe(channel_name)

        return res

    async with aio_spawn(reader, 'chan:1') as task:
        await aio_sleep(0.1)
        await redis.publish('chan:1', 'test')
        await aio_sleep(0.1)

    assert task.result() == 'test'
