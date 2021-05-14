import muffin
import pytest
import time


@pytest.fixture
def aiolib():
    """Disable uvloop for tests."""
    return ('asyncio', {'use_uvloop': False})


@pytest.fixture
async def app():
    from muffin_redis import Plugin as Redis

    app = muffin.Application(debug=True)
    Redis(app, fake=True)
    async with app.lifespan:
        yield app


async def test_muffin_redis(app):
    redis = app.plugins['redis']

    result = await redis.get('key')
    assert result is None

    await redis.set('key', 'value', expire=10)
    result = await redis.get('key')
    assert result == 'value'

    await redis.set('dict', {
        'now': time.time()
    }, jsonify=True)
    result = await redis.get('dict', jsonify=True)
    assert result and 'now' in result

    result = await redis.get('unknown')
    assert result is None


async def test_muffin_redis_pubsub(app):
    from asgi_tools._compat import aio_spawn, aio_sleep

    redis = app.plugins['redis']

    async def reader(channel, conn):
        await conn.execute('subscribe', channel)
        ch = conn.pubsub_channels[channel]
        await ch.wait_message()
        msg = await ch.get()
        return msg

    async with aio_spawn(reader, 'chan:1', redis.conn.connection) as task:
        await aio_sleep(0)
        await redis.publish('chan:1', 'test')
        await aio_sleep(0)

    assert task.result() == b'test'


async def test_simple_lock(app):
    redis = app.plugins['redis']

    async with redis.lock('l1') as lock:
        assert lock

        async with redis.lock('l2') as lock2:
            assert lock2

        async with redis.lock('l1') as same_lock:
            assert not same_lock

    async with redis.lock('l1') as lock:
        assert lock
