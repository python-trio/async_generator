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
iterator over the decoded bodies with:

.. code-block:: python3

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
we can write:

.. code-block:: python3

   async def load_json_lines(asyncio_stream_reader):
       async for line in asyncio_stream_reader:
           yield json.loads(line)

BUT! the above DOESN'T WORK in Python 3.5 -- you just get a syntax
error. In 3.5, the only way to make an async generator is to manually
define ``__aiter__`` and ``__anext__``.

**Until now.**

This is a little library which implements async generators in Python
3.5, by emulating the above syntax. The two changes are that you have
to decorate your async generators with ``@async_generator``, and
instead of writing ``yield x`` you write ``await yield_(x)``:

.. code-block:: python3

   # Same example as before, but works in Python 3.5
   from async_generator import async_generator, yield_, yield_from_

   @async_generator
   async def load_json_lines(asyncio_stream_reader):
       async for line in asyncio_stream_reader:
           await yield_(json.loads(line))


Semantics
=========

This library generally tries hard to match the semantics of Python
3.6's native async generators in every detail (`PEP 525
<https://www.python.org/dev/peps/pep-0525/>`__), except that it adds
``yield from`` support, and it doesn't currently support the
``sys.{get,set}_asyncgen_hooks`` garbage collection API. There are two
main reasons for this: (a) it doesn't exist on Python 3.5, and (b)
even on 3.6, only built-in generators are supposed to use that API,
and that's not us. In any case, you probably shouldn't be relying on
garbage collection for async generators – see `this discussion
<https://vorpus.org/blog/some-thoughts-on-asynchronous-api-design-in-a-post-asyncawait-world/#cleanup-in-generators-and-async-generators>`__
and `PEP 533 <https://www.python.org/dev/peps/pep-0533/>`__ for more
details.


aclosing
========

As discussed above, you should always explicitly call ``aclose`` on
async generators. To make this more convenient, this library also
includes an ``aclosing`` async context manager. It acts just like the
``closing`` context manager included in the stdlib ``contextlib``
module, but does ``await obj.aclose()`` instead of
``obj.close()``. Use it like this:

.. code-block:: python3

   from async_generator import aclosing

   async with aclosing(load_json_lines(asyncio_stream_reader)) as agen:
       async for json_obj in agen:
           ...


yield from
==========

Starting in 3.6, CPython has native support for async generators. But,
native async generators still don't support ``yield from``. This
library does. It looks like:

.. code-block:: python3

   @async_generator
   async def wrap_load_json_lines(asyncio_stream_reader):
       await yield_from_(load_json_lines(asyncio_stream_reader))

The ``await yield_from_(...)`` construction can be applied to any
async iterator, including class-based iterators, native async
generators, and async generators created using this library, and fully
supports the classic ``yield from`` semantics.

..
   In fact, if you're using CPython 3.6 native generators, you can even
   use this library's ``yield_from_`` *directly inside a native
   generator*. For example, this totally works (if you're on 3.6):

   .. code-block:: python3

      async def f():
          yield 2
          yield 3

      async def g():
          yield 1
          await yield_from_(f())
          yield 4

   There are two limitations to watch out for, though:

   * You can't write a native async generator that *only* contains
     ``yield_from_`` calls; it has to contain at least one real ``yield``
     or else the Python compiler won't know that you're trying to write
     an async generator and you'll get extremely weird results. For
     example, this won't work:

     .. code-block:: python3

        async def wrap_load_json_lines(asyncio_stream_reader):
            await yield_from_(load_json_lines(asyncio_stream_reader))

     The solution is either to convert it into an ``@async_generator``,
     or else add a ``yield`` expression somewhere.

   * You can't return values from native async generators. So this
     doesn't work:

     .. code-block:: python3

        async def yield_and_return():
            yield 1
            yield 2
            # "SyntaxError: 'return' with value in async generator"
            return "all done"

        async def wrapper():
            yield "in wrapper"
            result = await yield_from_(yield_and_return())
            assert result == "all done"

     The solution is to convert ``yield_and_return`` to an
     ``@async_generator``::

        @async_generator
        async def yield_and_return():
            await yield_(1)
            await yield_(2)
            return "all done"


Introspection
=============

For introspection purposes, we also export the following functions:

* ``async_generator.isasyncgen``: Returns true if passed either an async
  generator object created by this library, or a native Python 3.6+
  async generator object. Analogous to ``inspect.isasyncgen`` in 3.6+.

* ``async_generator.isasyncgenfunction``: Returns true if passed
  either an async generator function created by this library, or a
  native Python 3.6+ async generator function. Analogous to
  ``inspect.isasyncgenfunction`` in 3.6+.

Example:

.. code-block:: python3

   >>> isasyncgenfunction(load_json_lines)
   True
   >>> gen_object = load_json_lines(asyncio_stream_reader)
   >>> isasyncgen(gen_object)
   True

In addition, this library's async generator objects are registered
with the ``collections.abc.AsyncGenerator`` abstract base class:

.. code-block:: python3

   >>> isinstance(gen_object, collections.abc.AsyncGenerator)
   True


Changes
=======

1.8 (2017-06-17)
----------------

* Implement PEP 479: if a ``StopAsyncIteration`` leaks out of an async
  generator body, wrap it into a ``RuntimeError``.
* If an async generator was instantiated but never iterated, then we
  used to issue a spurious "RuntimeWarning: coroutine '...' was never
  awaited" warning. This is now fixed.
* Add PyPy3 to our test matrix.
* 100% test coverage.


1.7 (2017-05-13)
----------------

* Fix a subtle bug where if you wrapped an async generator using
  ``functools.wraps``, then ``isasyncgenfunction`` would return True
  for the wrapper. This isn't how ``inspect.isasyncgenfunction``
  works, and it broke ``sphinxcontrib_trio``.


1.6 (2017-02-17)
----------------

* Add support for async generator introspection attributes
  ``ag_running``, ``ag_code``, ``ag_frame``.
* Attempting to re-enter a running async_generator now raises
  ``ValueError``, just like for native async generators.
* 100% test coverage.


1.5 (2017-01-15)
----------------

* Remove (temporarily?) the hacks that let ``yield_`` and
  ``yield_from_`` work with native async generators. It turns out that
  due to obscure linking issues this was causing the library to be
  entirely broken on Python 3.6 on Windows (but not Linux or
  MacOS). It's probably fixable, but needs some fiddling with ctypes
  to get the refcounting right, and I couldn't figure it out in the
  time I had available to spend.

  So in this version, everything that worked before still works with
  ``@async_generator``-style generators, but uniformly, on all
  platforms, ``yield_`` and ``yield_from_`` now do *not* work inside
  native-style async generators.
* Now running CI testing on Windows as well as Linux.
* 100% test coverage.


1.4 (2016-12-05)
----------------

* Allow ``await yield_()`` as an shorthand for ``await yield_(None)``
  (thanks to Alex Grönholm for the suggestion+patch).
* Small cleanups to setup.py and test infrastructure.
* 100% test coverage (now including branch coverage!)


1.3 (2016-11-24)
----------------

* Added ``isasyncgen`` and ``isasyncgenfunction``.
* On 3.6+, register our async generators with
  ``collections.abc.AsyncGenerator``.
* 100% test coverage.


1.2 (2016-11-14)
----------------

* Rewrote ``yield from`` support; now has much more accurate handling
  of edge cases.
* ``yield_from_`` now works inside CPython 3.6's native async
  generators.
* Added ``aclosing`` context manager; it's pretty trivial, but if
  we're going to recommend it be used everywhere then it seems polite
  to include it.
* 100% test coverage.


1.1 (2016-11-06)
----------------

* Support for ``asend``\/``athrow``\/``aclose``
* Support for ``yield from``
* Add a ``__del__`` method that complains about improperly cleaned up
  async generators.
* Adapt to `the change in Python 3.5.2
  <https://www.python.org/dev/peps/pep-0492/#api-design-and-implementation-revisions>`_
  where ``__aiter__`` should now be a regular method instead of an
  async method.
* Adapt to Python 3.5.2's pickiness about iterating over
  already-exhausted coroutines.
* 100% test coverage.


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
