API documentation
=================

Async generators
----------------

In Python 3.6+, you can write a native async generator like this::

    async def load_json_lines(stream_reader):
        async for line in stream_reader:
            yield json.loads(line)

Here's the same thing written with this library, which works on Python 3.5+::

    from async_generator import async_generator, yield

    @async_generator
    async def load_json_lines(stream_reader):
        async for line in stream_reader:
            await yield_(json.loads(line))

Basically:

* decorate your function with ``@async_generator``
* replace ``yield`` with ``await yield_()``
* replace ``yield X`` with ``await yield_(X)``

That's it!


Yield from
~~~~~~~~~~

Native async generators don't support ``yield from``::

    # Doesn't work!
    async def wrap_load_json_lines(stream_reader):
        # This is a SyntaxError
        yield from load_json_lines(stream_reader)

But we do::

    from async_generator import async_generator, yield_from_

    # This works!
    @async_generator
    async def wrap_load_json_lines(stream_reader):
        await yield_from_(load_json_lines(stream_reader))

You can only use ``yield_from_`` inside an ``@async_generator``
function, BUT the thing you PASS to ``yield_from_`` can be any kind of
async iterator, including native async generators.

Our ``yield_from_`` fully supports the classic ``yield from``
semantics, including forwarding ``asend`` and ``athrow`` calls into
the delegated async generator, and returning values::

    from async_generator import async_generator, yield_, yield_from_

    @async_generator
    async def agen1():
        await yield_(1)
        await yield_(2)
        return "great!"

    @async_generator
    async def agen2():
        value = await yield_from_(agen1())
        assert value == "great!"


Introspection
~~~~~~~~~~~~~

For introspection purposes, we also export the following functions:

.. function:: isasyncgen(agen_obj)

   Returns true if passed either an async generator object created by
   this library, or a native Python 3.6+ async generator object.
   Analogous to :func:`inspect.isasyncgen` in 3.6+.

.. function:: isasyncgenfunction(agen_func)

   Returns true if passed either an async generator function created
   by this library, or a native Python 3.6+ async generator function.
   Analogous to :func:`inspect.isasyncgenfunction` in 3.6+.

Example::

   >>> isasyncgenfunction(load_json_lines)
   True
   >>> gen_object = load_json_lines(asyncio_stream_reader)
   >>> isasyncgen(gen_object)
   True

In addition, this library's async generator objects are registered
with the ``collections.abc.AsyncGenerator`` abstract base class (if
available)::

   >>> isinstance(gen_object, collections.abc.AsyncGenerator)
   True


Semantics
~~~~~~~~~

This library generally tries hard to match the semantics of Python
3.6's native async generators in every detail (`PEP 525
<https://www.python.org/dev/peps/pep-0525/>`__), with additional
support for ``yield from`` and for returning non-None values from
an async generator (under the theory that these may well be added
to native async generators one day).


Garbage collection hooks
~~~~~~~~~~~~~~~~~~~~~~~~

This library fully supports the native async generator
`finalization semantics <https://www.python.org/dev/peps/pep-0525/#finalization>`__,
including the per-thread ``firstiter`` and ``finalizer`` hooks.
You can use ``async_generator.set_asyncgen_hooks()`` exactly
like you would use ``sys.set_asyncgen_hooks()`` with native
generators. On Python 3.6+, the former is an alias for the latter,
so libraries that use the native mechanism should work seamlessly
with ``@async_generator`` functions.

While finishing cleanup of an async generator is better than dropping
it on the floor at the first ``await``, it's still not a perfect solution;
in addition to the unpredictability of GC timing, the ``finalizer`` hook
has no practical way to determine the context in which the generator was
being iterated, so an exception thrown from the generator during ``aclose()``
must either crash the program or get discarded. It's much better to close
your generators explicitly when you're done with them, perhaps using the
:ref:`aclosing context manager <contextmanagers>`. See `this discussion
<https://vorpus.org/blog/some-thoughts-on-asynchronous-api-design-in-a-post-asyncawait-world/#cleanup-in-generators-and-async-generators>`__
and `PEP 533 <https://www.python.org/dev/peps/pep-0533/>`__ for more
details.


.. _contextmanagers:

Context managers
----------------

As discussed above, you should always explicitly call ``aclose`` on
async generators. To make this more convenient, this library also
includes an ``aclosing`` async context manager. It acts just like the
``closing`` context manager included in the stdlib ``contextlib``
module, but does ``await obj.aclose()`` instead of
``obj.close()``. Use it like this::

   from async_generator import aclosing

   async with aclosing(load_json_lines(asyncio_stream_reader)) as agen:
       async for json_obj in agen:
           ...

Or if you want to write your own async context managers, we've got you
covered:

.. function:: asynccontextmanager
   :decorator:

   This is a backport of :func:`contextlib.asynccontextmanager`, which
   wasn't added to the standard library until Python 3.7.

You can use ``@asynccontextmanager`` with either native async
generators, or the ones from this package. If you use it with the ones
from this package, remember that ``@asynccontextmanager`` goes *on
top* of ``@async_generator``::

   # Correct!
   @asynccontextmanager
   @async_generator
   async def my_async_context_manager():
       ...

   # This won't work :-(
   @async_generator
   @asynccontextmanager
   async def my_async_context_manager():
       ...
