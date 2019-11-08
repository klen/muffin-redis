"""Redis support for Muffin framework."""
import asyncio as aio
import warnings

import asyncio_redis
import jsonpickle
from muffin.plugins import BasePlugin, PluginException
from muffin.utils import to_coroutine


__version__ = "1.3.3"
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

    async def startup(self, app):
        """Connect to Redis."""
        if self.cfg.fake:
            if not FakeConnection:
                raise PluginException('Install fakeredis for fake connections.')

            self.conn = await FakeConnection.create()
            if self.cfg.pubsub:
                self.pubsub_conn = self.conn

        else:
            try:
                if self.cfg.poolsize <= 1:
                    self.conn = await aio.wait_for(
                        asyncio_redis.Connection.create(
                            host=self.cfg.host, port=self.cfg.port,
                            password=self.cfg.password, db=self.cfg.db,
                        ), self.cfg.timeout)
                else:
                    self.conn = await aio.wait_for(asyncio_redis.Pool.create(
                        host=self.cfg.host, port=self.cfg.port,
                        password=self.cfg.password, db=self.cfg.db,
                        poolsize=self.cfg.poolsize,
                    ), self.cfg.timeout)
                if self.cfg.pubsub:
                    self.pubsub_conn = await aio.wait_for(
                        asyncio_redis.Connection.create(
                            host=self.cfg.host, port=self.cfg.port,
                            password=self.cfg.password, db=self.cfg.db,
                        ), self.cfg.timeout
                    )
            except aio.TimeoutError:
                raise PluginException('Muffin-redis connection timeout.')

        if self.cfg.pubsub:
            self.pubsub_subscription = await self.pubsub_conn.start_subscribe()
            self.pubsub_reader = aio.ensure_future(self._pubsub_reader_proc(), loop=self.app.loop)

    async def cleanup(self, app):
        """Close self connections."""
        self.conn.close()
        if self.pubsub_conn:
            self.pubsub_reader.cancel()
            self.pubsub_conn.close()
        # give connections a chance to actually terminate
        # TODO: use better method once it will be added,
        # see https://github.com/jonathanslenders/asyncio-redis/issues/56
        await aio.sleep(0)

    def set(self, key, value, *args, **kwargs):
        """Store the given value into Redis.

        :returns: a coroutine
        """
        if self.cfg.fake and 'expire' in kwargs:
            kwargs['ex'] = kwargs.pop('expire')
            kwargs.pop('only_if_not_exists')

        if self.cfg.jsonpickle:
            value = jsonpickle.encode(value)

        return self.conn.set(key, value, *args, **kwargs)

    async def get(self, key):
        """Decode the value."""
        value = await self.conn.get(key)
        if self.cfg.jsonpickle:
            if isinstance(value, bytes):
                return jsonpickle.decode(value.decode('utf-8'))

            if isinstance(value, str):
                return jsonpickle.decode(value)

        return value

    def publish(self, channel, message):
        """Publish message to channel.

        :returns: a coroutine
        """
        if self.cfg.jsonpickle:
            message = jsonpickle.encode(message)
        return self.conn.publish(channel, message)

    def start_subscribe(self):
        """Create a new Subscription context manager."""
        if not self.conn:
            raise ValueError('Not connected')
        elif not self.pubsub_conn:
            raise ValueError('PubSub not enabled')

        # creates a new context manager
        return Subscription(self)

    async def _pubsub_reader_proc(self):
        while True:
            try:
                # receive and unpickle next message
                msg = await self.pubsub_subscription.next_published()
                if self.cfg.jsonpickle:
                    # We overwrite 'hidden' field `_value` on the message received.
                    # Hackish way, I know. How can we do it better? XXX
                    if isinstance(msg.value, bytes):
                        msg._value = msg.value.decode('utf-8')
                    if isinstance(msg._value, str):
                        msg._value = jsonpickle.decode(msg.value)

                # notify all receivers for that message (including self, if any)
                for receiver in self._subscriptions.get((msg.channel, False), []):
                    await receiver.put(msg)

                for receiver in self._subscriptions.get((msg.pattern, True), []):
                    await receiver.put(msg)

            except aio.CancelledError:
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
        self._queue = aio.Queue()

    async def open(self):
        """Do nothing (because connection was established during initialization).

        Returns self for convenience and for compatibility with __aenter__.
        """
        return self

    async def close(self):
        """Unsubscribe from all channels used by this object."""
        await self.unsubscribe()
        await self.punsubscribe()

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

    async def _subscribe(self, channels, is_mask):
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
            await getattr(self._sub, 'psubscribe' if is_mask else 'subscribe')(news)

    async def _unsubscribe(self, channels, is_mask):
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
            await getattr(self._sub, 'punsubscribe' if is_mask else 'unsubscribe')(vanished)

    def subscribe(self, channels):
        """Subscribe to given channels.
        :returns: a coroutine
        """
        return self._subscribe(channels, False)

    def psubscribe(self, channels):
        """Subscribe to given channel's masks.
        :returns: a coroutine
        """
        return self._subscribe(channels, True)

    def unsubscribe(self, channels=None):
        """Unsubscribe from given channels.
        :returns: a coroutine
        """
        return self._unsubscribe(channels, False)

    def punsubscribe(self, channels=None):
        """Unsubscribe from given channel's masks.
        :returns: a coroutine
        """
        return self._unsubscribe(channels, True)

    def next_published(self):
        """Get a message from subscribed channels.
        :returns: a coroutine
        """
        if not self._sub:
            raise ValueError('Not connected')

        # we could check if we are subscribed to anything,
        # but let's leave it for user to decide:
        # user may want to first start listening in one task
        # and only after that subscribe from another task

        # just wait for plugin._pubsub_reader_proc to feed us
        return self._queue.get()

    __aenter__ = open  # alias

    async def __aexit__(self, exc_type, exc, tb):
        """Exit from context manager."""
        await self.close()
        return None  # will reraise exception, if any

    async def __aiter__(self):
        """Support async."""
        return self

    def __anext__(self):
        """Iterate self."""
        # behaves like a coroutine
        return self.next_published()


try:  # noqa
    import fakeredis as fake
    # this is to ensure that fakeredis installed is new enough

    class FakeRedis(fake.FakeRedis):

        """Fake connection for tests."""

        def __init__(self, *args, **kwargs):
            super(FakeRedis, self).__init__(*args, **kwargs)

            # Convert methods to coroutines
            fake._patch_responses(self, to_coroutine)

        def start_subscribe(self):
            # rewrote using our class
            fps = FakePubSub()
            self._pubsubs.append(fps)
            return fps

        async def pubsub_channels(self):
            channels = set()
            for ps in self._pubsubs:
                for channel in ps.channels:
                    channels.add(channel)
            return list(channels)

        @staticmethod
        def close():
            """Close a fake connection."""
            return

    class FakePubSub(fake.FakePubSub):

        def __init__(self, *args, **kwargs):
            super(FakePubSub, self).__init__(*args, **kwargs)

            # Convert methods to coroutines
            obj, decorator = self, to_coroutine
            for attr_name in dir(obj):
                attr = getattr(obj, attr_name)
                if not callable(attr) or attr_name.startswith('_') or attr_name == 'put':
                    continue
                if aio.iscoroutinefunction(attr):
                    continue
                func = decorator(attr)
                setattr(obj, attr_name, func)

        # convert API for subscribe methods
        def subscribe(self, chl):
            return super().subscribe(*chl)

        def psubscribe(self, chl):
            return super().psubscribe(*chl)

        def unsubscribe(self, chl):
            return super().unsubscribe(*chl)

        def punsubscribe(self, chl):
            return super().punsubscribe(*chl)

        # convert API for subscribe methods
        async def next_published(self):
            # rewrote `listen` as a coro
            # but do not respect `self.subscribed`
            while True:
                message = await self.get_message()
                if message and 'message' in message['type']:
                    # convert from fakeredis format to asyncio_redis one
                    return asyncio_redis.replies.PubSubReply(
                        channel=message['channel'].decode(),
                        value=message['data'],
                        pattern=message['pattern'],
                    )
                await aio.sleep(.1)

    class FakeConnection(asyncio_redis.Connection):

        """Fake Redis for tests."""

        @classmethod
        async def create(cls, *args, **kwargs):
            """Create a fake connection."""
            return FakeRedis()

except ImportError:
    FakeConnection = False
