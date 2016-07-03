The async_generator library
===========================

Python's iterators are great to use -- but manually implementing the
iterator protocol (``__iter__``, ``__next__``) can be very
annoying. No-one wants to do that all the time.

Fortunately, Python has *generators*, which make it easy and
straightforward to create an *iterator* by writing a *function*. E.g.,
if you have a file where each line is a JSON document, you can make an
iterator over the decoded bodies with::

   def load_json_lines(fileobj):
       for line in fileobj:
           yield json.loads(line)

Starting in v3.5, Python has added `*async iterators* and *async
functions* <https://www.python.org/dev/peps/pep-0492/>`_. These are
like regular iterators and functions, except that they have magic
powers that let them do asynchronous I/O without twisting your control
flow into knots.

Asynchronous I/O code is all about incrementally processing streaming
data, so async iterators are super handy. But manually implementing
the async iterator protocol (``__aiter__``, ``__anext__``) can be very
annoying, which is why we want *async generators*, which make it easy
to create an *async iterator* by writing an *async function*. For
example, suppose that in our example above, we want to read the
documents from a network connection, instead of the local
filesystem. Using the `asyncio.StreamReader interface
<https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader>`_
we can write::

   async def load_json_lines(asyncio_stream_reader):
       async for line in asyncio_stream_reader:
           async yield json.loads(line)

BUT! the above DOESN'T WORK in Python 3.5 -- you just get a syntax
error. In 3.5, the only way to make an async generator is to manually
define ``__aiter__`` and ``__anext__``.

**Until now.**

This is a little library which implements async generators in Python
3.5, by emulating the above syntax. The two changes are that you have
to decorate your async generators with ``@async_generator``, and
instead of writing ``async yield x`` you write ``await yield_(x)``::

   # Same example as before, but works in Python 3.5
   from async_generator import async_generator, yield_

   @async_generator
   async def load_json_lines(asyncio_stream_reader):
       async for line in asyncio_stream_reader:
           await yield_(json.loads(line))


Semantics
=========

In addition to being *super handy*, this library is intended to help
us get some experience with writing and using async generators, so
that we can figure out exactly what semantics they should have, in
hopes of getting them added to the language properly in ~3.6/3.7. So
here are some notes on the exact design decisions taken (for now):


``send``, ``throw``, ``yield from``
-----------------------------------

We *do not* implement any async equivalent to regular generators'
  ``send`` and ``throw``. ``await yield_(...)`` always returns
  ``None``.

We *do not* implement any kind of ``async yield from ...``.

This isn't because these features are uninteresting. Recall that
``yield from`` isn't just useful as a trick for implementing async
coroutines -- it was `originally motivated
<https://www.python.org/dev/peps/pep-0380/>`_ as a way to allow
complex generators to be refactored into multiple pieces, and that
rationale applies equally for async generators. It's not as clear
whether asynchronous ``asend(...)`` and ``athrow(...)`` methods are
really compelling -- though one use case would be that if we start
implementing network protocols as async generators that do ``async for
...`` to read and ``async yield ...`` to write, then it is nice if the
write operation has a way to signal an error!

But, there are two reasons why we nonetheless leave these out (for
now): (a) It'd be easy for this library to implement either *one* of
these features, but implementing both of them is substantially more
difficult, and it isn't clear which is more useful. (b) It might be
extremely difficult for CPython to natively implement either of these
features at all, and we don't want that to block getting the basic
feature implemented. By leaving these features out we can get some
data on just how useful they really are.


Return values
-------------

Async generators must return ``None`` (for example, by falling off the
bottom of the function body). If they don't then we raise a
``RuntimeError``. (Rationale: it would be easy to put the return value
into the ``StopAsyncIteration`` exception, similar to how return
values in regular generators are carried in ``StopIteration``
exceptions. But there isn't much point, because generator return
values are really only useful with ``yield from``, and we don't
support ``yield from``. And making it an error lets us keep our
options open for the future.)


``close``
---------

We do not implement any equivalent to the generator ``close``
method. We are currently trying to figure out whether or not this is a
bug.


Changes
=======

0.0.2
-----

* Fixes a very nasty and hard-to-hit bug where ``await yield_(...)``
  calls could escape out to the top-level coroutine runner and get
  lost, if the last trap out to the coroutine runner before the
  ``await yield_(...)`` caused an exception to be injected.

0.0.1
-----

Initial release.
