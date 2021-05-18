"""Redis support for Muffin framework."""

import typing as t

import aioredis
from contextlib import asynccontextmanager
from asgi_tools._compat import json_dumps, json_loads

from muffin import Application
from muffin.plugins import BasePlugin

try:
    import fakeredis
    from fakeredis import aioredis as fake_aioredis
except ImportError:
    fakeredis = None
    fake_aioredis = None

__version__ = "2.1.4"


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

    client = None

    def __getattr__(self, name):
        """Proxy attribute to self connection."""
        return getattr(self.client, name)

    def setup(self, app: Application, **options):
        """Check the configuration."""
        super(Plugin, self).setup(app, **options)
        if self.cfg.fake and not fake_aioredis:
            raise RuntimeError('`fakeredis` is required to support `fake` mode.')

    async def startup(self):
        """Setup a redis connection."""
        params = {'db': self.cfg.db, 'password': self.cfg.password, 'encoding': self.cfg.encoding}

        if self.cfg.fake and self.cfg.poolsize:
            self.client = await fake_aioredis.create_redis_pool(
                fakeredis.FakeServer(), maxsize=self.cfg.poolsize, **params)

        elif self.cfg.fake and not self.cfg.poolsize:
            self.client = await fake_aioredis.create_redis(fakeredis.FakeServer(), **params)

        elif not self.cfg.fake and self.cfg.poolsize:
            self.client = await aioredis.create_redis_pool(
                self.cfg.address, maxsize=self.cfg.poolsize, **params)

        elif not self.cfg.fake and not self.cfg.poolsize:
            self.client = await aioredis.create_redis(self.cfg.address, **params)

    async def shutdown(self):
        """Close the redis pool."""
        self.client.connection.close()
        await self.client.connection.wait_closed()

    def set(self, key, value, *, jsonify: bool = None, **options) -> t.Awaitable:
        """Store the given value into Redis."""
        if (self.cfg.jsonify if jsonify is None else jsonify):
            value = json_dumps(value)

        return self.client.set(key, value, **options)

    async def get(self, key, *, jsonify: bool = None, **options):
        """Decode the value."""
        value = await self.client.get(key, **options)

        if value is not None and (self.cfg.jsonify if jsonify is None else jsonify):
            if isinstance(value, bytes):
                value = value.decode('utf-8')

            try:
                return json_loads(value)
            except ValueError:
                pass

        return value

    @asynccontextmanager
    async def lock(self, key: str, ex: int = None):
        """Simplest lock (before aioredis 2.0+)."""  # noqa
        lock_ = await self.client.set(key, '1', expire=ex, exist='SET_IF_NOT_EXIST')
        try:
            yield lock_
        finally:
            if lock_:
                await self.client.delete(key)
