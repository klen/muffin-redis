"""Redis support for Muffin framework."""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, ClassVar

from asgi_tools._compat import json_dumps, json_loads
from muffin.plugins import BasePlugin
from redis.asyncio import BlockingConnectionPool, ConnectionPool, Redis, RedisError

if TYPE_CHECKING:
    from muffin import Application
    from redis.typing import EncodableT, KeyT


class Plugin(BasePlugin):
    """Manage Redis."""

    name = "redis"
    defaults: ClassVar = {
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

    def __init__(self, app: Application | None = None, **options):
        """Initialize the plugin."""
        self.__client__: Redis | None = None
        self.redislite = None
        super().__init__(app, **options)

    def setup(self, app: Application, *, name: str | None = None, **options) -> bool:
        super().setup(app, name=name, **options)

        cfg = self.cfg

        params = {
            "db": cfg.db,
            "password": cfg.password,
            "encoding": cfg.encoding,
            "decode_responses": cfg.decode_responses,
        }

        if cfg.blocking:
            params["timeout"] = cfg.timeout

        pool_cls = BlockingConnectionPool if cfg.blocking else ConnectionPool

        url = cfg.url
        if cfg.redislite:
            from redislite import Redis as RedisLite  # noqa: PLC0415

            self.redislite = RedisLite()
            url = f"unix://{self.redislite.socket_file}"  # type: ignore[attr-defined]
            cfg.update_from_dict({"url": url})

        pool = pool_cls.from_url(url, max_connections=cfg.poolsize, **params)
        self.__client__ = Redis(connection_pool=pool)

        return True

    @property
    def client(self) -> Redis:
        """Return a client instance."""
        if self.__client__ is None:
            raise RuntimeError("Redis Plugin should be started")

        return self.__client__

    def __getattr__(self, name):
        """Proxy attribute to self connection."""
        if name in ("startup", "shutdown", "middleware"):
            return object.__getattribute__(self, name)
        return getattr(self.client, name)

    async def startup(self):
        """Initialize a redis connection."""
        self.app.logger.info("Connecting to Redis at %s", self.cfg.url)
        await self.client.initialize()

    async def shutdown(self):
        """Close the redis pool."""
        self.app.logger.info("Disconnecting from Redis at %s", self.cfg.url)
        client = self.client
        await client.aclose()  # type: ignore[]
        await client.connection_pool.disconnect()

    def set(
        self,
        name: KeyT,
        value: EncodableT,
        *,
        jsonify: bool | None = None,
        **options,
    ):
        """Store the given value into Redis."""
        if self.cfg.jsonify if jsonify is None else jsonify:
            value = json_dumps(value)

        return self.client.set(name, value, **options)

    async def get(self, key, *, jsonify: bool | None = None, **options):
        """Decode the value."""
        client = self.client
        value = await client.get(key, **options)

        if value is not None and (self.cfg.jsonify if jsonify is None else jsonify):
            if isinstance(value, bytes):
                value = value.decode("utf-8")

            with suppress(ValueError):
                return json_loads(value)

        return value
