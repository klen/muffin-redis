import muffin
import pytest
import datetime


@pytest.fixture(scope='session')
def app(loop):
    return muffin.Application(
        'redis', loop=loop,

        PLUGINS=['muffin_redis'],
        REDIS_FAKE=True,
    )


@pytest.mark.async
def test_muffin_redis(app):  # noqa
    assert app.ps.redis
    assert app.ps.redis.conn

    yield from app.ps.redis.set('key', 'value', 10)
    result = yield from app.ps.redis.get('key')
    assert result == 'value'

    yield from app.ps.redis.set('dict', {
        'now': datetime.datetime.now()
    })
    result = yield from app.ps.redis.get('dict')
    assert result and 'now' in result and isinstance(result['now'], datetime.datetime)

    result = yield from app.ps.redis.get('unknown')
    assert result is None

    subscriber = yield from app.ps.redis.start_subscribe()
    yield from subscriber.subscribe(['channel'])
    channels = yield from app.ps.redis.conn.pubsub_channels()
    assert 'channel' in channels

    yield from app.ps.publish('channel', 'Hello world')
    yield from app.ps.publish('channel', {
        'now': datetime.datetime.now(),
    })

    result = yield from subscriber.next_published()
    assert result and result.value == 'Hello world'

    # another way: iterator style
    #async for result in subscriber:
    #    value = result.value
    #    assert value and 'now' in value and isinstance(value['now'], datetime.datetime)
    #    break
    # -- but this test requires python 3.5, so for now use simplified syntax
    result = yield from subscriber.__anext__()
    assert value and 'now' in value and isinstance(value['now'], datetime.datetime)

    yield from subscriber.unsubscribe()
    result = yield from app.ps.redis.conn.pubsub_channels()
    assert 'channel' not in result
