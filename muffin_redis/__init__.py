"""Redis support for Muffin framework."""

import typing as t

import aioredis
from asgi_tools._compat import json_dumps, json_loads

from muffin.plugins import BasePlugin

__version__ = "3.0.0"


class Plugin(BasePlugin):

    """Manage Redis."""

    name = 'redis'
    defaults = {
        'url': 'redis://localhost',
        'db': None,
        'password': None,
        'poolsize': 10,
        'encoding': 'utf-8',
        'decode_responses': True,
        'jsonify': False,
    }

    client = None

    def __getattr__(self, name):
        """Proxy attribute to self connection."""
        return getattr(self.client, name)

    async def startup(self):
        """Setup a redis connection."""
        params = {
            'db': self.cfg.db, 'password': self.cfg.password,
            'decode_responses': self.cfg.decode_responses, 'encoding': self.cfg.encoding}

        self.client = aioredis.from_url(self.cfg.url, max_connections=self.cfg.poolsize, **params)

    async def shutdown(self):
        """Close the redis pool."""
        await self.client.close()
        await self.client.connection_pool.disconnect()

    def set(self, key, value, *, jsonify: bool = None, **options) -> t.Awaitable:
        """Store the given value into Redis."""
        if (self.cfg.jsonify if jsonify is None else jsonify):
            value = json_dumps(value)

        client = self.client
        if client is None:
            raise RuntimeError('Redis Plugin should be started')

        return client.set(key, value, **options)

    async def get(self, key, *, jsonify: bool = None, **options):
        """Decode the value."""
        client = self.client
        if client is None:
            raise RuntimeError('Redis Plugin should be started')

        value = await client.get(key, **options)

        if value is not None and (self.cfg.jsonify if jsonify is None else jsonify):
            if isinstance(value, bytes):
                value = value.decode('utf-8')

            try:
                return json_loads(value)
            except ValueError:
                pass

        return value
