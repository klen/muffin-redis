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
