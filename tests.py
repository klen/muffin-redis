import muffin
import pytest
import datetime


@pytest.fixture
def app(loop):
    app = muffin.Application(
        'redis',
        PLUGINS=['muffin_redis'],
        REDIS_FAKE=True,
        REDIS_PUBSUB=True,
    )
    app.on_startup.freeze()
    loop.run_until_complete(app.startup())
    app.freeze()
    return app


async def test_muffin_redis(app):  # noqa
    assert app.ps.redis
    assert app.ps.redis.conn

    await app.ps.redis.set('key', 'value', 10)
    result = await app.ps.redis.get('key')
    assert result == 'value'

    await app.ps.redis.set('dict', {
        'now': datetime.datetime.now()
    })
    result = await app.ps.redis.get('dict')
    assert result and 'now' in result and isinstance(result['now'], datetime.datetime)

    result = await app.ps.redis.get('unknown')
    assert result is None

    await app.ps.redis.cleanup(app)


async def test_muffin_redis_pubsub(app):
    subscriber = await app.ps.redis.start_subscribe().open()
    await subscriber.subscribe(['channel'])
    channels = await app.ps.redis.pubsub_conn.pubsub_channels()
    assert b'channel' in channels

    await app.ps.redis.publish('channel', 'Hello world')
    await app.ps.redis.publish('channel', {
        'now': datetime.datetime.now(),
    })

    result = await subscriber.next_published()
    assert result and result.value == 'Hello world'

    # another way: iterator style
    #async for result in subscriber:
    #    value = result.value
    #    assert value and 'now' in value and isinstance(value['now'], datetime.datetime)
    #    break
    # -- but this test requires python 3.5, so for now use older syntax
    result = await subscriber.__anext__()
    assert result and 'now' in result.value and isinstance(result.value['now'], datetime.datetime)

    await subscriber.unsubscribe()
    result = await app.ps.redis.conn.pubsub_channels()
    #assert 'channel' not in result --
    # disabled because fakeredis' unsubscribe doesn't remove channel from list
    # when unsubscribing from it

    await subscriber.close()
