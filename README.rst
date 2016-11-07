The async_generator library
===========================

.. image:: https://travis-ci.org/njsmith/async_generator.svg?branch=master
   :target: https://travis-ci.org/njsmith/async_generator
   :alt: Automated test status

.. image:: https://codecov.io/gh/njsmith/async_generator/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/njsmith/async_generator
   :alt: Test coverage

This is a tiny library to add "async generators" to Python 3.5. What
are those?

Option 1: `my 5-minute lightning talk demo from PyCon 2016 <https://youtu.be/PulzIT8KYLk?t=24m30s>`_

Option 2: read on!

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
   from async_generator import async_generator, yield_, yield_from_

   @async_generator
   async def load_json_lines(asyncio_stream_reader):
       async for line in asyncio_stream_reader:
           await yield_(json.loads(line))

yield from
==========

Starting in 3.6, CPython has native support for async generators. But,
it still doesn't support ``yield from``. This library does. It looks
like::

   @async_generator
   async def wrap_load_json_lines(asyncio_stream_reader):
       await yield_from_(load_json_lines(asyncio_stream_reader))

The ``await yield_from_(...)`` construction can be applied to any
async iterator, including class-based iterators, native async
generators, and async generators created using this library, and fully
supports the classic ``yield from`` semantics.


Semantics
=========

This library generally follows `PEP 525
<https://www.python.org/dev/peps/pep-0525/>`__ semantics ("as seen in
Python 3.6!"), except that it adds ``yield from`` support, and it
doesn't currently support the ``sys.{get,set}_asyncgen_hooks`` garbage
collection API. There are two main reasons for this: (a) it doesn't
exist on Python 3.5, and (b) even on 3.6, only built-in generators are
supposed to use that API, and that's not us. In any case, you probably
shouldn't be relying on garbage collection for async generators – see
`this discussion
<https://vorpus.org/blog/some-thoughts-on-asynchronous-api-design-in-a-post-asyncawait-world/#cleanup-in-generators-and-async-generators>`__
and `PEP 533 <https://www.python.org/dev/peps/pep-0533/>`__ for more
details.


Changes
=======

1.1 (????-??-??)
----------------

* Support for ``asend``\/``athrow``\/``aclose``
* Support for ``yield from``
* Add a ``__del__`` method that complains about improperly cleaned up
  async generators.
* Adapt to `the change in Python 3.5.2
  <https://www.python.org/dev/peps/pep-0492/#api-design-and-implementation-revisions>`_
  where ``__aiter__`` should now be a regular method instead of an
  async method.


1.0 (2016-07-03)
----------------

* Fixes a very nasty and hard-to-hit bug where ``await yield_(...)``
  calls could escape out to the top-level coroutine runner and get
  lost, if the last trap out to the coroutine runner before the
  ``await yield_(...)`` caused an exception to be injected.
* Infinitesimally more efficient due to re-using internal
  ``ANextIter`` objects instead of recreating them on each call to
  ``__anext__``.
* 100% test coverage.


0.0.1 (2016-05-31)
------------------

Initial release.
