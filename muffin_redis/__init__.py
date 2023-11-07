"""Redis support for Muffin framework."""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any, ClassVar, Dict, Optional

from asgi_tools._compat import json_dumps, json_loads
from muffin.plugins import BasePlugin
from redis.asyncio import BlockingConnectionPool, ConnectionPool, Redis, RedisError

if TYPE_CHECKING:
    from muffin import Application
    from redis.typing import EncodableT, KeyT


class Plugin(BasePlugin):
    """Manage Redis."""

    name = "redis"
    defaults: ClassVar[Dict[str, Any]] = {
        "url": "redis://localhost",
        "db": None,
        "password": None,
        "encoding": "utf-8",
        "decode_responses": True,
        "jsonify": False,
        "poolsize": 10,
        "blocking": True,
        "timeout": 20,
        # ===
        "redislite": False,
    }

    Error = RedisError

    def __init__(self, app: Optional[Application] = None, **options):
        """Initialize the plugin."""
        self.__client__: Optional[Redis] = None
        self.redislite = None
        super().__init__(app, **options)

    async def startup(self):
        """Setup a redis connection."""
        cfg = self.cfg

        params = {
            "db": cfg.db,
            "password": cfg.password,
            "decode_responses": cfg.decode_responses,
            "encoding": cfg.encoding,
        }

        if cfg.blocking:
            params["timeout"] = cfg.timeout

        pool_cls = BlockingConnectionPool if cfg.blocking else ConnectionPool

        url = cfg.url
        if cfg.redislite:
            from redislite import Redis as RedisLite

            self.redislite = RedisLite()
            url = f"unix://{self.redislite.socket_file}"

        pool = pool_cls.from_url(url, max_connections=cfg.poolsize, **params)
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
        client = self.client
        await client.aclose()
        await client.connection_pool.disconnect()
        if self.redislite is not None:
            self.redislite.shutdown()

    def set(
        self,
        name: KeyT,
        value: EncodableT,
        *,
        jsonify: Optional[bool] = None,
        **options,
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
