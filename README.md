# Muffin-Redis

**Muffin-Redis** — Redis support for the [Muffin](https://github.com/klen/muffin) framework.

![Tests Status](https://github.com/klen/muffin-redis/workflows/tests/badge.svg)
[![PyPI Version](https://img.shields.io/pypi/v/muffin-redis)](https://pypi.org/project/muffin-redis/)
[![Python Versions](https://img.shields.io/pypi/pyversions/muffin-redis)](https://pypi.org/project/muffin-redis/)

---

## Features

- Built on `redis.asyncio` client.
- Optional support for `redislite` with Unix socket configuration.
- JSON serialization support
- Automatic connection pool management (blocking or non-blocking).
- Simple `get()` / `set()` with optional `jsonify` flag.
- Lifecycle support: `startup` and `shutdown` integrate with Muffin app lifecycle.

## Requirements

- Python >= 3.10

## Installation

Install using pip:

```bash
pip install muffin-redis
```

Optionally with `redislite`:

```bash
pip install muffin-redis[redislite]
```

## Usage

Setup the plugin and connect it into your app:

```python
from muffin import Application
from muffin_redis import Plugin as Redis

app = Application('example')

# Initialize the plugin
redis = Redis(address='redis://localhost')
redis.setup(app)
```

You can now use Redis in your routes:

```python
@app.route('/some_url', methods=['POST'])
async def some_method(request):
    value = await redis.get('key')
    if value is None:
        value = ...  # Do some work
        await redis.set('key', value, expire=60)
    return value
```

Under the hood, **Muffin-Redis** uses [aioredis](https://github.com/aio-libs/aioredis) for asynchronous Redis support.

## Configuration Options

| Name               | Default               | Description                                                  |
| ------------------ | --------------------- | ------------------------------------------------------------ |
| `url`              | `"redis://localhost"` | Redis connection URL                                         |
| `db`               | `None`                | Redis DB index                                               |
| `password`         | `None`                | Redis password                                               |
| `encoding`         | `"utf-8"`             | Encoding used by the client                                  |
| `poolsize`         | `10`                  | Max pool size (set `0` to disable pooling)                   |
| `decode_responses` | `True`                | Whether to decode binary responses                           |
| `jsonify`          | `False`               | Automatically encode/decode JSON with get/set                |
| `blocking`         | `True`                | Use a blocking connection pool                               |
| `timeout`          | `20`                  | Timeout in seconds for getting a connection                  |
| `redislite`        | `False`               | Enable [redislite](https://github.com/yahoo/redislite) usage |

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
