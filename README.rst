Muffin-Redis
############

.. _description:

Muffin-Redis -- Redis support for Muffin framework.

.. _badges:

.. image:: https://github.com/klen/muffin-redis/workflows/tests/badge.svg
    :target: https://github.com/klen/muffin-redis/actions
    :alt: Tests Status

.. image:: https://img.shields.io/pypi/v/muffin-redis
    :target: https://pypi.org/project/muffin-redis/
    :alt: PYPI Version

.. image:: https://img.shields.io/pypi/pyversions/muffin-redis
    :target: https://pypi.org/project/muffin-redis/
    :alt: Python Versions

.. _contents:

.. contents::

.. _requirements:

Requirements
=============

- python >= 3.7

.. _installation:

Installation
=============

**Muffin-Redis** should be installed using pip: ::

    pip install muffin-redis

To install ``fakeredis`` (for testing purposes): ::

    pip install muffin-redis[fake]

.. _usage:

Usage
=====

Setup the plugin and connect it into your app:

.. code-block:: python

    from muffin import Application
    from muffin_redis import Plugin as Redis

    # Create Muffin Application
    app = Application('example')

    # Initialize the plugin
    # As alternative: redis = Redis(app, **options)
    redis = Redis(address='redis://localhost')
    redis.setup(app)

That's it now you are able to use the plugin inside your views:

.. code-block:: python

    @app.route('/some_url', methods=['POST'])
    async def some_method(request):
        """Work with redis."""
        value = await redis.get('key')
        if value is None:
            value = ...  # Do some work
            await redis.set('key', value, expire=60)

        return value

For Asyncio_ the ``muffin-redis`` uses aioredis_ library. So check the
library's docs for futher reference.

.. _Asyncio: https://docs.python.org/3/library/asyncio.html
.. _aioredis: https://github.com/aio-libs/aioredis

Configuration options
----------------------

=========================== ======================================= =========================== 
Name                        Default value                           Description
--------------------------- --------------------------------------- ---------------------------
**address**                 ``"redis://localhost"``                 Redis connection URL
**db**                      ``None``                                Number of the Redis DB
**password**                ``None``                                Connection password
**encoding**                ``"utf-8"``                             Connection encoding
**poolsize**                ``10``                                  Connections pool size (set 0 to disable pooling)
**jsonify**                 ``False``                               Use json to store/read objects with get/set
**fake**                    ``False``                               Use ``fakeredis``. The option is convenient for testing
=========================== ======================================= =========================== 

.. _bugtracker:

Bug tracker
===========

If you have any suggestions, bug reports or
annoyances please report them to the issue tracker
at https://github.com/klen/muffin-redis/issues

.. _contributing:

Contributing
============

Development of Muffin-Redis happens at: https://github.com/klen/muffin-redis


Contributors
=============

* klen_ (Kirill Klenov)

.. _license:

License
========

Licensed under a `MIT license`_.

.. _links:

.. _klen: https://github.com/klen
.. _MIT license: http://opensource.org/licenses/MIT
