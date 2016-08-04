"""Redis support for Muffin framework."""

import warnings
import asyncio
import jsonpickle
import asyncio_redis
from muffin.plugins import BasePlugin, PluginException

try:
    from asyncio import ensure_future
except ImportError:
    ensure_future = asyncio.async


__version__ = "1.2.0"
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
        'pubsub': False,
        'timeout': 10,
    }

    def __init__(self, *args, **kwargs):
        """Initialize the plugin."""
        super().__init__(*args, **kwargs)
        self.conn = None
        self.pubsub_conn = None
        self.pubsub_subscription = None
        self.pubsub_reader = None
        # this is a mapping from channels to subscription objects
        self._subscriptions = {}

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
            if self.cfg.pubsub:
                self.pubsub_conn = self.conn

        else:
            try:
                if self.cfg.poolsize <= 1:
                    self.conn = yield from asyncio.wait_for(
                        asyncio_redis.Connection.create(
                            host=self.cfg.host, port=self.cfg.port,
                            password=self.cfg.password, db=self.cfg.db,
                        ), self.cfg.timeout)
                else:
                    self.conn = yield from asyncio.wait_for(asyncio_redis.Pool.create(
                        host=self.cfg.host, port=self.cfg.port,
                        password=self.cfg.password, db=self.cfg.db,
                        poolsize=self.cfg.poolsize,
                    ), self.cfg.timeout)
                if self.cfg.pubsub:
                    self.pubsub_conn = yield from asyncio.wait_for(
                        asyncio_redis.Connection.create(
                            host=self.cfg.host, port=self.cfg.port,
                            password=self.cfg.password, db=self.cfg.db,
                        ), self.cfg.timeout
                    )
            except asyncio.TimeoutError:
                raise PluginException('Muffin-redis connection timeout.')

        if self.cfg.pubsub:
            self.pubsub_subscription = yield from self.pubsub_conn.start_subscribe()

            self.pubsub_reader = ensure_future(self._pubsub_reader_proc(), loop=self.app.loop)

    @asyncio.coroutine
    def finish(self, app):
        """Close self connections."""
        self.conn.close()
        if self.pubsub_conn:
            self.pubsub_reader.cancel()
            self.pubsub_conn.close()
        # give connections a chance to actually terminate
        # TODO: use better method once it will be added,
        # see https://github.com/jonathanslenders/asyncio-redis/issues/56
        yield  # or: yield from asyncio.sleep(0)

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
        """Publish message to channel."""
        if self.cfg.jsonpickle:
            message = jsonpickle.encode(message)
        return (yield from self.conn.publish(channel, message))

    def start_subscribe(self):
        """Create a new Subscription context manager."""
        if not self.conn:
            raise ValueError('Not connected')
        elif not self.pubsub_conn:
            raise ValueError('PubSub not enabled')

        # creates a new context manager
        return Subscription(self)

    @asyncio.coroutine
    def _pubsub_reader_proc(self):
        while True:
            try:
                # receive and unpickle next message
                msg = (yield from self.pubsub_subscription.next_published())
                if self.cfg.jsonpickle:
                    # We overwrite 'hidden' field `_value` on the message received.
                    # Hackish way, I know. How can we do it better? XXX
                    if isinstance(msg.value, bytes):
                        msg._value = msg.value.decode('utf-8')
                    if isinstance(msg._value, str):
                        msg._value = jsonpickle.decode(msg.value)

                # notify all receivers for that message (including self, if any)
                for receiver in self._subscriptions.get((msg.channel, False), []):
                    yield from receiver.put(msg)

                for receiver in self._subscriptions.get((msg.pattern, True), []):
                    yield from receiver.put(msg)
            except asyncio.CancelledError:
                raise
            except Exception: # noqa
                self.app.logger.exception('Pubsub reading failure')
                # and continue working
                # unless we are testing
                if self.cfg.fake:
                    raise
            # TODO: maybe we need special handling for other exceptions?

    def __getattr__(self, name):
        """Proxy attribute to self connection."""
        return getattr(self.conn, name)


class Subscription():

    """Implement Subscription Context Manager.

    This class is not just a proxy for asyncio_redis Subscription:
    while asyncio_redis can have only one Subscription at a time,
    we want to support multiple Subscription objects.

    This class serves the following purposes:
        1. Proxies commands/messages to/from dedicated subscription connection;
        2. Unpickles all received messages if needed;
        3. Implements `async iterator` interface to be used with `async for`.
    """

    def __init__(self, plugin):
        """Initialize self."""
        self._plugin = plugin
        self._sub = plugin.pubsub_subscription
        self._channels = []
        self._queue = asyncio.Queue()

    @asyncio.coroutine
    def open(self):
        """Do nothing (because connection was established during initialization).

        Returns self for convenience and for compatibility with __aenter__.
        """
        return self

    @asyncio.coroutine
    def close(self):
        """Unsubscribe from all channels used by this object."""
        yield from self.unsubscribe()
        yield from self.punsubscribe()

    def __del__(self):
        """Ensure that we unsubscribed from all channels and warn user if not."""
        if self._channels:
            warnings.warn(
                'Subscription is destroyed '
                'but was not unsubscribed from some channels: ' +
                ', '.join(c for c, m in self._channels),
                RuntimeWarning,
            )
            # do our best to fix this
            for chan, is_mask in self._channels:
                self._plugin._subscriptions[chan, is_mask].remove(self._queue)
            # Note: redis connection is still subscribed to events!

    @asyncio.coroutine
    def _subscribe(self, channels, is_mask):
        """Subscribe to given channel."""
        news = []
        for channel in channels:
            key = channel, is_mask
            self._channels.append(key)
            if key in self._plugin._subscriptions:
                self._plugin._subscriptions[key].append(self._queue)
            else:
                self._plugin._subscriptions[key] = [self._queue]
                news.append(channel)
        if news:
            yield from getattr(self._sub, 'psubscribe' if is_mask else 'subscribe')(news)

    @asyncio.coroutine
    def _unsubscribe(self, channels, is_mask):
        """Unsubscribe from given channel."""
        vanished = []
        if channels:
            for channel in channels:
                key = channel, is_mask
                self._channels.remove(key)
                self._plugin._subscriptions[key].remove(self._queue)
                if not self._plugin._subscriptions[key]:  # we were last sub?
                    vanished.append(channel)
                    del self._plugin._subscriptions[key]
        else:
            while self._channels:
                channel, is_mask = key = self._channels.pop()
                self._plugin._subscriptions[key].remove(self._queue)
                if not self._plugin._subscriptions[key]:
                    vanished.append(channel)
                    del self._plugin._subscriptions[key]
        if vanished:
            yield from getattr(
                self._sub,
                'punsubscribe' if is_mask else 'unsubscribe',
            )(vanished)

    @asyncio.coroutine
    def subscribe(self, channels):
        """Subscribe to given channels."""
        return self._subscribe(channels, False)

    @asyncio.coroutine
    def psubscribe(self, channels):
        """Subscribe to given channel's masks."""
        return self._subscribe(channels, True)

    @asyncio.coroutine
    def unsubscribe(self, channels=None):
        """Unsubscribe from given channels."""
        return self._unsubscribe(channels, False)

    @asyncio.coroutine
    def punsubscribe(self, channels=None):
        """Unsubscribe from given channel's masks."""
        return self._unsubscribe(channels, True)

    @asyncio.coroutine
    def next_published(self):
        """Get a message from subscribed channels."""
        if not self._sub:
            raise ValueError('Not connected')

        # we could check if we are subscribed to anything,
        # but let's leave it for user to decide:
        # user may want to first start listening in one task
        # and only after that subscribe from another task

        # just wait for plugin._pubsub_reader_proc to feed us
        return (yield from self._queue.get())

    __aenter__ = open  # alias

    @asyncio.coroutine
    def __aexit__(self, exc_type, exc, tb):
        """Exit from context manager."""
        yield from self.close()
        return None  # will reraise exception, if any

    @asyncio.coroutine
    def __aiter__(self):
        """Support async."""
        return self

    def __anext__(self):
        """Iterate self."""
        # behaves like a coroutine
        return self.next_published()


try:  # noqa
    import fakeredis
    from fakeredis import FakePubSub as _  # noqa
    # this is to ensure that fakeredis installed is new enough

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

        def start_subscribe(self):
            # rewrote using our class
            fps = FakePubSub()
            self._pubsubs.append(fps)
            return fps

        @asyncio.coroutine
        def pubsub_channels(self):
            channels = set()
            for ps in self._pubsubs:
                for channel in ps.channels:
                    channels.add(channel)
            return list(channels)

    class FakePubSub(fakeredis.FakePubSub):
        def __getattribute__(self, name):
            """Make a coroutine."""
            import inspect
            method = super().__getattribute__(name)
            if not inspect.isfunction(method):
                return method
            if method.startswith('_'):
                return method
            if not inspect.iscoroutinefunction(method):
                @asyncio.coroutine
                def coro(*args, **kwargs):
                    return method(*args, **kwargs)
                return coro
            return method

        # convert API for subscribe methods
        @asyncio.coroutine
        def subscribe(self, chl):
            return super().subscribe(*chl)

        @asyncio.coroutine
        def psubscribe(self, chl):
            return super().psubscribe(*chl)

        @asyncio.coroutine
        def unsubscribe(self, chl):
            return super().unsubscribe(*chl)

        @asyncio.coroutine
        def punsubscribe(self, chl):
            return super().punsubscribe(*chl)

        @asyncio.coroutine
        def next_published(self):
            # rewrote `listen` as a coro
            # but do not respect `self.subscribed`
            while True:
                message = super().get_message()
                if message and 'message' in message['type']:
                    # convert from fakeredis format to asyncio_redis one
                    return asyncio_redis.replies.PubSubReply(
                        channel=message['channel'].decode(),
                        value=message['data'],
                        pattern=message['pattern'],
                    )
                yield from asyncio.sleep(.1)

    class FakeConnection(asyncio_redis.Connection):

        """Fake Redis for tests."""

        @classmethod
        @asyncio.coroutine
        def create(cls, *args, **kwargs):
            """Create a fake connection."""
            return FakeRedis()

except ImportError:
    FakeConnection = False
