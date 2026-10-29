"""Redis support for Muffin framework."""

from __future__ import annotations

from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import urlsplit

from asgi_tools._compat import json_dumps, json_loads
from muffin.plugins import BasePlugin
from redis.asyncio import BlockingConnectionPool, ConnectionPool, Redis, RedisError

from .fake import create_fake_client, fake_lock

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from muffin import Application
    from redis.typing import EncodableT, KeyT


def _address(url: str) -> str:
    """Return the Redis address without credentials."""
    parsed = urlsplit(url)
    return parsed.netloc.rsplit("@", 1)[-1] or parsed.path


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
        "fake": False,
    }

    Error = RedisError

    def __init__(self, app: Application | None = None, **options):
        """Initialize the plugin."""
        self.__client__: Redis | None = None
        super().__init__(app, **options)

    def setup(self, app: Application, *, name: str | None = None, **options) -> bool:
        if not super().setup(app, name=name, **options):
            return False

        cfg = self.cfg

        if cfg.fake:
            self.__client__ = create_fake_client(
                decode_responses=cfg.decode_responses,
                db=cfg.db or 0,
            )
            return True

        params = {
            "db": cfg.db,
            "password": cfg.password,
            "encoding": cfg.encoding,
            "decode_responses": cfg.decode_responses,
        }

        if cfg.blocking:
            params["timeout"] = cfg.timeout

        pool_cls = BlockingConnectionPool if cfg.blocking else ConnectionPool

        pool = pool_cls.from_url(cfg.url, max_connections=cfg.poolsize, **params)
        self.__client__ = Redis(connection_pool=pool)

        return True

    @property
    def client(self) -> Redis:
        """Return a client instance."""
        client = self.__dict__.get("__client__")
        if client is None:
            raise RuntimeError("Redis Plugin should be started")

        return client

    def __getattr__(self, name):
        """Proxy attribute to self connection."""
        if name.startswith("__"):
            raise AttributeError(name)

        if name in ("startup", "shutdown", "middleware"):
            return object.__getattribute__(self, name)

        client = self.__dict__.get("__client__")
        if client is None:
            raise AttributeError(f"Redis Plugin should be started (no attribute {name!r})")

        return getattr(client, name)

    async def startup(self):
        """Initialize a redis connection."""
        self.app.logger.info("Connecting to Redis at %s", _address(self.cfg.url))
        await self.client.initialize()

    async def shutdown(self):
        """Close the redis pool."""
        self.app.logger.info("Disconnecting from Redis at %s", _address(self.cfg.url))
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

    async def get(self, key, *, jsonify: bool | None = None):
        """Decode the value."""
        value = await self.client.get(key)

        if value is not None and (self.cfg.jsonify if jsonify is None else jsonify):
            if isinstance(value, bytes):
                value = value.decode("utf-8")

            with suppress(ValueError):
                return json_loads(value)

        return value

    @asynccontextmanager
    async def lock(
        self,
        name: KeyT,
        *,
        timeout: float | None = 30,
        blocking: bool = True,
        blocking_timeout: float | None = None,
        sleep: float = 0.1,
    ) -> AsyncGenerator[bool]:
        """Acquire and release a Redis lock with one async context manager."""
        if self.cfg.fake:
            async with fake_lock(
                self.client,
                name,
                timeout=timeout,
                blocking=blocking,
                blocking_timeout=blocking_timeout,
                sleep=sleep,
            ) as acquired:
                yield acquired
        else:
            lock = self.client.lock(
                name,
                timeout=timeout,
                sleep=sleep,
                blocking_timeout=blocking_timeout,
            )
            acquired = await lock.acquire(blocking=blocking)

            try:
                yield acquired
            finally:
                if acquired:
                    with suppress(RedisError):
                        await lock.release()
