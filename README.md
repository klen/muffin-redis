# Muffin-Redis

**Muffin-Redis** — Redis support for the [Muffin](https://github.com/klen/muffin) framework.

![Tests Status](https://github.com/klen/muffin-redis/workflows/tests/badge.svg)
[![PyPI Version](https://img.shields.io/pypi/v/muffin-redis)](https://pypi.org/project/muffin-redis/)
[![Python Versions](https://img.shields.io/pypi/pyversions/muffin-redis)](https://pypi.org/project/muffin-redis/)

---

## Features

- Built on `redis.asyncio` client.
- Optional support for `fakeredis` for testing without a real Redis server.
- JSON serialization support
- Automatic connection pool management (blocking or non-blocking).
- Simple `get()` / `set()` with optional `jsonify` flag.
- Async locks with automatic release.
- Lifecycle support: `startup` and `shutdown` integrate with Muffin app lifecycle.

## Requirements

- Python >= 3.11 (tested on 3.11 - 3.15)

## Installation

Install using pip:

```bash
pip install muffin-redis
```

Optionally with `fakeredis`:

```bash
pip install muffin-redis[fake]
```

## Usage

Setup the plugin and connect it into your app:

```python
from muffin import Application
from muffin_redis import Plugin as Redis

app = Application('example')

# Initialize the plugin
redis = Redis(url='redis://localhost')
redis.setup(app)
```

Only the options from the table below are read from the configuration, anything else is ignored
(so a mistyped option name silently falls back to its default). Everything else is passed to
`redis.asyncio.Redis`, so the [redis-py documentation](https://redis.readthedocs.io/) applies to
any command or option not listed here.

You can now use Redis in your routes:

```python
@app.route('/some_url', methods=['POST'])
async def some_method(request):
    value = await redis.get('key', jsonify=True)
    if value is None:
        value = {'some': 'value'}  # Do some work
        await redis.set('key', value, jsonify=True, ex=60)
    return value
```

## Configuration Options

| Name               | Default               | Description                                                  |
| ------------------ | --------------------- | ------------------------------------------------------------ |
| `url`              | `"redis://localhost"` | Redis connection URL                                         |
| `db`               | `None`                | Redis DB index (`None` keeps the server default, `0`)        |
| `password`         | `None`                | Redis password                                               |
| `encoding`         | `"utf-8"`             | Encoding used by the client                                  |
| `poolsize`         | `10`                  | Max pool size (`0` means no limit and lets redis-py use its default of `100`) |
| `decode_responses` | `True`                | Whether to decode binary responses                           |
| `jsonify`          | `False`               | Automatically encode/decode JSON with get/set                |
| `blocking`         | `True`                | Use a blocking connection pool                               |
| `timeout`          | `20`                  | Seconds to wait for a free connection (blocking pool only)   |
| `fake`             | `False`               | Use [fakeredis](https://github.com/cunla/fakeredis) instead of a real Redis server |

## API

### `client`

Property returning the underlying `redis.asyncio.Redis` instance. Raises `RuntimeError` when the
plugin is not started yet.

### `set(name, value, *, jsonify=None, **options)`

Coroutine storing `value` under `name` and returning the client's result (`True` on success).
`jsonify` falls back to the `jsonify` config option. `**options` are passed to the Redis `SET`
command, e.g. `ex=60` (expire in seconds), `px=...`, `nx=True`, `xx=True`. Note that the keyword is
`ex`, not `expire`.

### `get(key, *, jsonify=None, **options)`

Coroutine returning the stored value, or `None` when the key does not exist. With `jsonify` enabled
the value (a `str` because `decode_responses` defaults to `True`) is parsed as JSON; values that are
not valid JSON are returned unchanged.

### `lock(name, *, timeout=30, blocking=True, blocking_timeout=None, sleep=0.1)`

Async context manager yielding `True` when the lock was acquired and `False` otherwise. The lock is
released on a normal or exceptional exit (and only if it was acquired).

- `timeout` — lock lifetime in seconds; the lock expires automatically, `None` disables expiry.
- `blocking` — wait for a busy lock instead of returning `False` immediately.
- `blocking_timeout` — how long a blocking acquire waits before giving up (`None` waits until the
  current holder's `timeout` expires).
- `sleep` — delay between acquire attempts.

```python
async with redis.lock('reports', timeout=10) as acquired:
    if acquired:
        ...  # only one worker at a time
```

With `fake=True` the lock is emulated with `SET NX`/`DEL` polling, so it has no Lua dependency and
no distributed guarantees.

### Everything else

Unknown attributes are proxied to the client, so regular Redis commands work directly:

```python
await redis.hgetall('some-hash')
await redis.publish('chan:1', 'test')
```

Inside an application the plugin is started and stopped with the app lifecycle; standalone it can be
used as an async context manager (`async with redis: ...`).

## Bug Tracker

Please report bugs or feature requests at:
[https://github.com/klen/muffin-redis/issues](https://github.com/klen/muffin-redis/issues)

## Contributing

Development happens at:
[https://github.com/klen/muffin-redis](https://github.com/klen/muffin-redis)

## License

Licensed under the [MIT license](http://opensource.org/licenses/MIT).

## Credits

- Created by [klen](https://github.com/klen) (Kirill Klenov)
