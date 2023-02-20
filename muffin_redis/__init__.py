"""Redis support for Muffin framework."""

from contextlib import suppress
from typing import Optional

from asgi_tools._compat import json_dumps, json_loads
from muffin import Application
from muffin.plugins import BasePlugin

from redis.asyncio import BlockingConnectionPool, ConnectionPool, Redis, RedisError
from redis.typing import EncodableT, KeyT

__version__ = "3.3.0"


class Plugin(BasePlugin):

    """Manage Redis."""

    name = "redis"
    defaults = {
        "url": "redis://localhost",
        "db": None,
        "password": None,
        "encoding": "utf-8",
        "decode_responses": True,
        "jsonify": False,
        "poolsize": 10,
        "blocking": True,
        "timeout": 20,
    }

    Error = RedisError

    def __init__(self, app: Optional[Application], **options):
        """Initialize the plugin."""
        self.__client__: Optional[Redis] = None
        super().__init__(app, **options)

    async def startup(self):
        """Setup a redis connection."""
        params = {
            "db": self.cfg.db,
            "password": self.cfg.password,
            "decode_responses": self.cfg.decode_responses,
            "encoding": self.cfg.encoding,
        }

        if self.cfg.blocking:
            params["timeout"] = self.cfg.timeout

        pool_cls = BlockingConnectionPool if self.cfg.blocking else ConnectionPool
        pool = pool_cls.from_url(
            self.cfg.url, max_connections=self.cfg.poolsize, **params
        )
        self.__client__ = Redis(connection_pool=pool)

    @property
    def client(self) -> Redis:
        """Return a client instance."""
        if self.__client__ is None:
            raise RuntimeError("Redis Plugin should be started")

        return self.__client__

    def __getattr__(self, name):
        """Proxy attribute to self connection."""
        return getattr(self.client, name)

    async def __aenter__(self):
        await self.client.__aenter__()
        return self

    async def __aexit__(self, *args):
        await self.client.__aexit__(*args)

    async def shutdown(self):
        """Close the redis pool."""
        await self.client.close()
        await self.client.connection_pool.disconnect()

    def set(
        self,
        name: KeyT,
        value: EncodableT,
        *,
        jsonify: Optional[bool] = None,
        **options
    ):
        """Store the given value into Redis."""
        if self.cfg.jsonify if jsonify is None else jsonify:
            value = json_dumps(value)

        return self.client.set(name, value, **options)

    async def get(self, key, *, jsonify: Optional[bool] = None, **options):
        """Decode the value."""
        client = self.client
        value = await client.get(key, **options)

        if value is not None and (self.cfg.jsonify if jsonify is None else jsonify):
            if isinstance(value, bytes):
                value = value.decode("utf-8")

            with suppress(ValueError):
                return json_loads(value)

        return value
