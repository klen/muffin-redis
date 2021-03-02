"""Redis support for Muffin framework."""

import typing as t

import aioredis
from asgi_tools._compat import json_dumps, json_loads

from muffin import Application
from muffin.plugin import BasePlugin

try:
    import fakeredis
    from fakeredis import aioredis as fake_aioredis
except ImportError:
    fakeredis = None
    fake_aioredis = None

__version__ = "2.0.0"


class Plugin(BasePlugin):

    """Manage Redis."""

    name = 'redis'
    defaults = {
        'address': 'redis://localhost',
        'db': None,
        'password': None,
        'poolsize': 10,
        'fake': False,
        'encoding': 'utf-8',
        'jsonify': False,
    }

    def __init__(self, *args, **kwargs):
        """Initialize the plugin."""
        self.conn = None
        super(Plugin, self).__init__(*args, **kwargs)

    def __getattr__(self, name):
        """Proxy attribute to self connection."""
        return getattr(self.conn, name)

    def setup(self, app: Application, **options):
        """Check the configuration."""
        super(Plugin, self).setup(app, **options)
        if self.cfg.fake and not fake_aioredis:
            raise RuntimeError('`fakeredis` is required to support `fake` mode.')

    async def startup(self):
        """Setup a redis connection."""
        params = {'db': self.cfg.db, 'password': self.cfg.password, 'encoding': self.cfg.encoding}

        if self.cfg.fake and self.cfg.poolsize:
            self.conn = await fake_aioredis.create_redis_pool(
                fakeredis.FakeServer(), maxsize=self.cfg.poolsize, **params)

        elif self.cfg.fake and not self.cfg.poolsize:
            self.conn = await fake_aioredis.create_redis(fakeredis.FakeServer(), **params)

        elif not self.cfg.fake and self.cfg.poolsize:
            self.conn = await aioredis.create_pool(
                self.cfg.address, maxsize=self.cfg.poolsize, **params)

        elif not self.cfg.fake and not self.cfg.poolsize:
            self.conn = await aioredis.create_connection(self.cfg.address, **params)

    async def shutdown(self):
        """Close the redis pool."""
        self.conn.close()
        await self.conn.wait_closed()

    def set(self, key, value, *, jsonify: bool = None, **options) -> t.Awaitable:
        """Store the given value into Redis."""
        if (self.cfg.jsonify if jsonify is None else jsonify):
            value = json_dumps(value)

        return self.conn.set(key, value, **options)

    async def get(self, key, *, jsonify: bool = None, **options):
        """Decode the value."""
        value = await self.conn.get(key, **options)

        if (self.cfg.jsonify if jsonify is None else jsonify):
            if isinstance(value, bytes):
                value = value.decode('utf-8')
            return json_loads(value)

        return value
