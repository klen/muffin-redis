"""Redis support for Muffin framework."""

import asyncio
import jsonpickle
import asyncio_redis
from muffin.plugins import BasePlugin, PluginException


__version__ = "0.2.1"
__project__ = "muffin-redis"
__author__ = "Kirill Klenov <horneds@gmail.com>"
__license__ = "MIT"


class Plugin(BasePlugin):

    """Manage Redis connection."""

    name = 'redis'
    defaults = {
        'db': 0,
        'fake': False,
        'host': '127.0.0.1',
        'jsonpickle': True,
        'password': None,
        'poolsize': 1,
        'port': 6379,
    }

    def __init__(self, *args, **kwargs):
        """Initialize the plugin."""
        super().__init__(*args, **kwargs)
        self.conn = None

    def setup(self, app):
        """Setup the plugin."""
        super().setup(app)
        self.cfg.port = int(self.cfg.port)
        self.cfg.db = int(self.cfg.db)
        self.cfg.poolsize = int(self.cfg.poolsize)

    @asyncio.coroutine
    def start(self, app):
        """Connect to Redis."""
        if self.cfg.fake:
            if not FakeConnection:
                raise PluginException('Install fakeredis for fake connections.')

            self.conn = yield from FakeConnection.create()

        elif self.cfg.poolsize == 1:
            self.conn = yield from asyncio_redis.Connection.create(
                host=self.cfg.host, port=self.cfg.port,
                password=self.cfg.password, db=self.cfg.db,
            )

        else:
            self.conn = yield from asyncio_redis.Pool.create(
                host=self.cfg.host, port=self.cfg.port,
                password=self.cfg.password, db=self.cfg.db,
                poolsize=self.cfg.poolsize,
            )

    def finish(self, app):
        """Close self connections."""
        self.conn.close()

    @asyncio.coroutine
    def set(self, key, value, **params):
        """Encode the value."""
        if self.cfg.jsonpickle:
            value = jsonpickle.encode(value)
        return (yield from self.conn.set(key, value, **params))

    @asyncio.coroutine
    def get(self, key):
        """Decode the value."""
        value = yield from self.conn.get(key)
        if self.cfg.jsonpickle:
            if isinstance(value, bytes):
                return jsonpickle.decode(value.decode('utf-8'))
            if isinstance(value, str):
                return jsonpickle.decode(value)
        return value

    def __getattr__(self, name):
        """Proxy attribute to self connection."""
        return getattr(self.conn, name)


try:
    import fakeredis

    class FakeRedis(fakeredis.FakeRedis):

        """Fake connection for tests."""

        def __getattribute__(self, name):
            """Make a coroutine."""
            method = super().__getattribute__(name)
            if not name.startswith('_'):
                @asyncio.coroutine
                def coro(*args, **kwargs):
                    return method(*args, **kwargs)
                return coro
            return method

        def close(self):
            """Do nothing."""
            pass

        @asyncio.coroutine
        def multi(self):
            """Do nothing."""
            return self

        @asyncio.coroutine
        def exec(self):
            """Do nothing."""
            return self

    class FakeConnection(asyncio_redis.Connection):

        """Fake Redis for tests."""

        @classmethod
        @asyncio.coroutine
        def create(cls, *args, **kwargs):
            """Create a fake connection."""
            return FakeRedis()

except ImportError:
    FakeConnection = False
