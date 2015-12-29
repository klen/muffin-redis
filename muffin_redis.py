"""Redis support for Muffin framework."""

import asyncio
import jsonpickle
import asyncio_redis
from muffin.plugins import BasePlugin, PluginException


__version__ = "0.3.0"
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
        'timeout': 10,
        'jsonpickle': True,
        'password': None,
        'poolsize': 1,
        'port': 6379,
    }

    def __init__(self, *args, **kwargs):
        """Initialize the plugin."""
        super().__init__(*args, **kwargs)
        self.conn = None
        self.pubsub_conn = None
        self._subscription = None

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

        else:
            try:
                if self.cfg.poolsize == 1:
                    self.conn = yield from asyncio.wait_for(asyncio_redis.Connection.create(
                                    host=self.cfg.host, port=self.cfg.port,
                                    password=self.cfg.password, db=self.cfg.db,
                                ), self.cfg.timeout)
                else:
                    self.conn = yield from asyncio.wait_for(asyncio_redis.Pool.create(
                        host=self.cfg.host, port=self.cfg.port,
                        password=self.cfg.password, db=self.cfg.db,
                        poolsize=self.cfg.poolsize,
                    ), self.cfg.timeout)
            except asyncio.TimeoutError:
                raise PluginException('Muffin-redis connection timeout.')

    def finish(self, app):
        """Close self connections."""
        self.conn.close()

    @asyncio.coroutine
    def set(self, key, value, *args, **kwargs):
        """Encode the value."""
        if self.cfg.jsonpickle:
            value = jsonpickle.encode(value)
        return (yield from self.conn.set(key, value, *args, **kwargs))

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

    @asyncio.coroutine
    def publish(self, channel, message):
        if self.cfg.jsonpickle:
            message = jsonpickle.encode(message)
        return (yield from self.conn.publish(channel, message))

    @asyncio.coroutine
    def start_subscribe(self, *args):
        # create separate connection
        return Subscription(self)

    def __getattr__(self, name):
        """Proxy attribute to self connection."""
        return getattr(self.conn, name)

class Subscription():
    """
    This class is a proxy for asyncio_redis Subscription.
    It serves two purposes:
        1. Creates and handles separate connection for subscription
        2. Unpickles all received messages if needed;
        3. Implements `async iterator` interface to be used with `async for`.
    """
    def __init__(self, plugin):
        self._plugin = plugin
        self._conn = None
        self._sub = None
    @asyncio.coroutine
    def open(self):
        """
        Create connection, after which it is possible to subscribe.
        Returns self for convenience.
        """
        cfg = self._plugin.cfg
        self._conn = yield from asyncio.wait_for(
            asyncio_redis.Connection.create(
                host=cfg.host, port=cfg.port,
                password=cfg.password, db=cfg.db,
            ), cfg.timeout
        )
        self._sub = (yield from self._conn.start_subscribe(*args))
        return self
    __aenter__ = open # alias
    @asyncio.coroutine
    def close(self):
        """
        Close connection which was used for subscriptions
        and free its resources.
        """
        if not self._conn:
            raise ValueError('Was not connected')
        yield from self._conn.close()
    def __aexit__(self, exc_type, exc, tb):
        # this is not a coroutine but it returns a coroutine object
        return self.close()

    @asyncio.coroutine
    def next_published(self):
        if not self._sub:
            raise ValueError('Not connected')

        msg = (yield from self._sub.next_published())
        if self._plugin.cfg.jsonpickle:
            # We overwrite 'hidden' field `_value` on the message received.
            # Hackish way, I know. How can we do it better? XXX
            if isinstance(msg.value, bytes):
                msg._value = jsonpickle.decode(msg.value.decode('utf-8'))
            if isinstance(msg._value, str):
                msg._value = jsonpickle.decode(msg.value)
        return msg
    @asyncio.coroutine
    def __aiter__(self):
        return self
    def __anext__(self):
        # behaves like a coroutine
        return self.next_published()

    def __getattr__(self, attr):
        # proxy all remaining methods/fields
        return getattr(self._sub, attr)


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
