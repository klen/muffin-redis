""" Support redis in Muffin framework. """

import asyncio
import asyncio_redis
from muffin.plugins import BasePlugin, PluginException


__version__ = "0.0.2"
__project__ = "muffin-redis"
__author__ = "Kirill Klenov <horneds@gmail.com>"
__license__ = "MIT"


class Plugin(BasePlugin):

    """ Connect to Redis. """

    name = 'redis'
    defaults = {
        'db': 0,
        'fake': False,
        'host': '127.0.0.2',
        'password': None,
        'poolsize': 1,
        'port': 6379,
    }

    def __init__(self, *args, **kwargs):
        """ Initialize the Plugin. """
        super().__init__(*args, **kwargs)
        self.conn = None

    def setup(self, app):
        """ Setup self options. """
        super().setup(app)
        self.options.port = int(self.options.port)
        self.options.db = int(self.options.db)
        self.options.poolsize = int(self.options.poolsize)

    @asyncio.coroutine
    def start(self, app):
        """ Connect to Redis. """
        if self.options.fake:
            if not FakeConnection:
                raise PluginException('Install fakeredis for fake connections.')

            self.conn = yield from FakeConnection.create()

        elif self.options.poolsize == 1:
            self.conn = yield from asyncio_redis.Connection.create(
                host=self.options.host, port=self.options.port,
                password=self.options.password, db=self.options.db,
            )

        else:
            self.conn = yield from asyncio_redis.Pool.create(
                host=self.options.host, port=self.options.port,
                password=self.options.password, db=self.options.db,
                poolsize=self.options.poolsize,
            )

    def finish(self, app):
        """ Close self connections. """
        self.conn.close()

    def __getattr__(self, name):
        """ Proxy attribute to self connection. """
        return getattr(self.conn, name)


try:
    import fakeredis

    class FakeRedis(fakeredis.FakeRedis):

        """ Fake connection for tests. """

        def __getattribute__(self, name):
            """ Make a coroutine. """
            method = super().__getattribute__(name)
            if not name.startswith('_'):
                @asyncio.coroutine
                def coro(*args, **kwargs):
                    return method(*args, **kwargs)
                return coro
            return method

    class FakeConnection(asyncio_redis.Connection):

        """ Fake Redis for tests. """

        @classmethod
        @asyncio.coroutine
        def create(cls, *args, **kwargs):
            """ Create a fake connection. """
            return FakeRedis()

except ImportError:
    FakeConnection = False
