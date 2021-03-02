import muffin
import pytest
import datetime


@pytest.fixture
async def app():
    from muffin_redis import Plugin as Redis

    app = muffin.Application('redis', debug=True)
    Redis(app, fake=True)
    async with app.lifespan:
        yield app


@pytest.mark.parametrize('aiolib', ['asyncio'])
async def test_muffin_redis(app):
    redis = app.plugins['redis']

    result = await redis.get('key')
    assert result is None

    await redis.set('key', 'value', expire=10)
    result = await redis.get('key')
    assert result == 'value'

    await redis.set('dict', {
        'now': datetime.datetime.now()
    }, jsonify=True)
    result = await redis.get('dict', jsonify=True)
    assert result and 'now' in result

    result = await redis.get('unknown')
    assert result is None


@pytest.mark.parametrize('aiolib', ['asyncio'])
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
