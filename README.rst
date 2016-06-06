Muffin-Redis
############

.. _description:

Muffin-Redis -- Redis support for Muffin framework.

.. _badges:

.. image:: http://img.shields.io/travis/klen/muffin-redis.svg?style=flat-square
    :target: http://travis-ci.org/klen/muffin-redis
    :alt: Build Status

.. image:: http://img.shields.io/coveralls/klen/muffin-redis.svg?style=flat-square
    :target: https://coveralls.io/r/klen/muffin-redis
    :alt: Coverals

.. image:: http://img.shields.io/pypi/v/muffin-redis.svg?style=flat-square
    :target: https://pypi.python.org/pypi/muffin-redis

.. image:: http://img.shields.io/pypi/dm/muffin-redis.svg?style=flat-square
    :target: https://pypi.python.org/pypi/muffin-redis

.. _contents:

.. contents::

.. _requirements:

Requirements
=============

- python >= 3.3

.. _installation:

Installation
=============

**Muffin-Redis** should be installed using pip: ::

    pip install muffin-redis

.. _usage:

Usage
=====

Add `muffin_redis` to `PLUGINS` in your Muffin Application configuration.

Or install it manually like this: ::

    redis = muffin_redis.Plugin(**{'options': 'here'})

    app = muffin.Application('test')
    app.install(redis)


Appllication configuration options
----------------------------------

``REDIS_DB``       -- Number of Redis database (0)
``REDIS_HOST``     -- Connection IP address ("127.0.0.1")
``REDIS_PORT``     -- Connection port (6379)
``REDIS_PASSWORD`` -- Connection password (None)
``REDIS_POOLSIZE`` -- Connection pool size (1)
``REDIS_FAKE``     -- Use fake redis instead real one for tests proposals (False)

Queries
-------

::

    @app.register
    def view(request):
        value = yield from app.ps.redis.get('my_key')
        return value

Pub/Sub
-------

You need to have enabled `REDIS_PUBSUB = True` in your configuration for this functionality.

Publishing messages is as simple as this:

::

    @app.register
    def view(request):
        yield from app.ps.redis.publish('channel', 'message')

Receiving is more complex.
In order to start receiving messages from pubsub, you should create a subscription manager.
Then you open a separate connection within that manager,
after which you can subscribe and listen for messages:

::

    sub = app.ps.redis.start_subscribe()
    yield from sub.open() # this creates separate connection to redis
    # sub.open() returns that manager itself, so this can be written like this:
    # sub = yield from app.ps.redis.start_subscribe().open()
    sub.subscribe(['channel1'])
    sub.psubscribe(['channel.a.*', 'channel.b.*']) # you can use masks as well
    # now wait for new messages
    while True:
        msg = yield from sub.next_published()
        print('got message', msg)
        print('the message itself:', msg.value)
        if shall_stop:
            break
    yield from sub.close() # don't forget to close connection!

Subscription manager also implements PEP 0492 `async with` and `async for` interfaces,
so in Python 3.5+ that can be spelled in lighter way:

::

    async with app.ps.redis.start_subscribe() as sub:
        await sub.subscribe(['channel1'])
        await sub.psubscribe(['channel.a.*', 'channel.b.*']) # you can use masks as well
        async for msg in sub:
            print('got message', msg)
    # no need to close connection explicitly
    # as it will be done automatically by context manager.

It might be not very good to create separate Redis connection per each subscription manager
(e.g. per each websocket), so that could be improved by managing subscribed channel masks
and reusing the same single "pubsub-specific" redis connection.

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
=======

Licensed under a `MIT license`_.

If you wish to express your appreciation for the project, you are welcome to send
a postcard to: ::

    Kirill Klenov
    pos. Severny 8-3
    MO, Istra, 143500
    Russia

.. _links:


.. _klen: https://github.com/klen

.. _MIT license: http://opensource.org/licenses/MIT
