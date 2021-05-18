import muffin
import pytest
import time


@pytest.fixture(scope='session')
def aiolib():
    """Disable uvloop for tests."""
    return ('asyncio', {'use_uvloop': False})


@pytest.fixture
async def app(request):
    from muffin_redis import Plugin as Redis

    app = muffin.Application(debug=True)
    redis = Redis(app, fake=request.param)
    async with app.lifespan:
        yield app
        if not request.param:
            await redis.flushall()


@pytest.mark.parametrize('app', (True, False), indirect=True)
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


@pytest.mark.parametrize('app', (True, False), indirect=True)
async def test_muffin_redis_pubsub(app):
    from asgi_tools._compat import aio_spawn, aio_sleep

    redis = app.plugins['redis']

    async def reader(channel, conn):
        await conn.execute('subscribe', channel)
        ch = conn.pubsub_channels[channel]
        await ch.wait_message()
        msg = await ch.get()
        return msg

    async with aio_spawn(reader, 'chan:1', redis.connection) as task:
        await aio_sleep(0.1)
        await redis.publish('chan:1', 'test')
        await aio_sleep(0.1)

    assert task.result() == b'test'


@pytest.mark.parametrize('app', (True, False), indirect=True)
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


@pytest.mark.parametrize('app', (True, False), indirect=True)
async def test_jsonnify(app):
    redis = app.plugins['redis']

    await redis.set('l1', "[1, 2, 3")
    res = await redis.get('l1', jsonify=True)
    assert res == '[1, 2, 3'

    await redis.set('l1', [1, 2, 3], jsonify=True)
    res = await redis.get('l1', jsonify=True)
    assert res == [1, 2, 3]
