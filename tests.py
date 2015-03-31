import asyncio

import muffin
import pytest


@pytest.fixture(scope='session')
def app(loop):
    return muffin.Application(
        'redis', loop=loop,

        PLUGINS=['muffin_redis'],
        REDIS_FAKE=True,
    )


def test_muffin_redis(loop, app):
    assert app.ps.redis
    assert app.ps.redis.conn

    @asyncio.coroutine
    def test():
        yield from app.ps.redis.set('key', 'value')

    loop.run_until_complete(test())

    @asyncio.coroutine
    def test():
        return (yield from app.ps.redis.get('key'))

    result = loop.run_until_complete(test())
    assert result == b'value'
