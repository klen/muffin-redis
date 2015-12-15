import muffin
import pytest


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

    yield from app.ps.redis.set('key', 'value')
    result = yield from app.ps.redis.get('key')
    assert result == b'value'
