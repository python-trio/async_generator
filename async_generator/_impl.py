import sys
from functools import wraps
from types import coroutine, CodeType
import inspect
from inspect import (
    getcoroutinestate, CORO_CREATED, CORO_CLOSED, CORO_SUSPENDED
)
import collections.abc

# An async generator object (whether native in 3.6+ or the pure-Python
# version implemented below) is basically an async function with some
# extra wrapping logic. As an async function, it can call other async
# functions, which will probably at some point call a function that uses
# 'yield' to send traps to the event loop. Async generators also need
# to be able to send values to the context in which the generator is
# being iterated, and it's awfully convenient to be able to do that
# using 'yield' too. To distinguish between these two streams of
# yielded objects, the traps intended for the event loop are yielded
# as-is, and the values intended for the context that's iterating the
# generator are wrapped in some wrapper object (YieldWrapper here, or
# an internal Python type called AsyncGenWrappedValue in the native
# async generator implementation) before being yielded.
# The __anext__(), asend(), and athrow() methods of an async generator
# iterate the underlying async function until a wrapped value is received,
# and any unwrapped values are passed through to the event loop.

# These functions are syntactically valid only on 3.6+, so we conditionally
# exec() the code defining them.
_native_asyncgen_helpers = """
async def _wrapper():
    holder = [None]
    while True:
        # The simpler "value = None; while True: value = yield value"
        # would hold a reference to the most recently wrapped value
        # after it has been yielded out (until the next value to wrap
        # comes in), so we use a one-element list instead.
        holder.append((yield holder.pop()))
_wrapper = _wrapper()

async def _unwrapper():
    @coroutine
    def inner():
        holder = [None]
        while True:
            holder.append((yield holder.pop()))
    await inner()
    yield None
_unwrapper = _unwrapper()
"""

if sys.implementation.name == "cpython" and sys.version_info >= (3, 6):
    # On 3.6, with native async generators, we want to use the same
    # wrapper type that native generators use. This lets @async_generators
    # yield_from_ native async generators and vice versa.

    import ctypes
    from types import AsyncGeneratorType, GeneratorType
    exec(_native_asyncgen_helpers)

    # Transmute _wrapper to a regular generator object by modifying the
    # ob_type field. The code object inside _wrapper will still think it's
    # associated with an async generator, so it will yield out
    # AsyncGenWrappedValues when it encounters a 'yield' statement;
    # but the generator object will think it's a normal non-async
    # generator, so it won't unwrap them. This way, we can obtain
    # AsyncGenWrappedValues as normal manipulable Python objects.
    #
    # This sort of object type transmutation is categorically a Sketchy
    # Thing To Do, because the functions associated with the new type
    # (including tp_dealloc and so forth) will be operating on a
    # structure whose in-memory layout matches that of the old type.
    # In this case, it's OK, because async generator objects are just
    # generator objects plus a few extra fields at the end; and these
    # fields are two integers and a NULL-until-first-iteration object
    # pointer, so they don't hold any resources that need to be cleaned up.
    # We have a unit test that verifies that __sizeof__() for generators
    # and async generators continues to follow this pattern in future
    # Python versions.

    _type_p = ctypes.c_size_t.from_address(
        id(_wrapper) + ctypes.sizeof(ctypes.c_size_t)
    )
    assert _type_p.value == id(AsyncGeneratorType)
    _type_p.value = id(GeneratorType)

    supports_native_asyncgens = True

    # Now _wrapper.send(x) returns an AsyncGenWrappedValue of x.
    # We have to initially send(None) since the generator was just constructed;
    # we look at the type of the return value (which is AsyncGenWrappedValue(None))
    # to help with _is_wrapped.
    YieldWrapper = type(_wrapper.send(None))

    # Advance _unwrapper to its first yield statement, for use by _unwrap().
    _unwrapper.asend(None).send(None)

    # Performance note: compared to the non-native-supporting implementation below,
    # this _wrap() is about the same speed (434 +- 16 nsec here, 456 +- 24 nsec below)
    # but this _unwrap() is much slower (1.17 usec vs 167 nsec). Since _unwrap is only
    # needed on non-native generators, and we plan to have most @async_generators use
    # native generators on 3.6+, this seems acceptable.

    _wrap = _wrapper.send

    def _is_wrapped(box):
        return isinstance(box, YieldWrapper)

    def _unwrap(box):
        try:
            _unwrapper.asend(box).send(None)
        except StopIteration as e:
            return e.value
        else:
            raise TypeError("not wrapped")
else:
    supports_native_asyncgens = False

    class YieldWrapper:
        __slots__ = ("payload",)

        def __init__(self, payload):
            self.payload = payload

    def _wrap(value):
        return YieldWrapper(value)

    def _is_wrapped(box):
        return isinstance(box, YieldWrapper)

    def _unwrap(box):
        return box.payload


# The magic @coroutine decorator is how you write the bottom level of
# coroutine stacks -- 'async def' can only use 'await' = yield from; but
# eventually we must bottom out in a @coroutine that calls plain 'yield'.
@coroutine
def _yield_(value):
    return (yield _wrap(value))


# But we wrap the bare @coroutine version in an async def, because async def
# has the magic feature that users can get warnings messages if they forget to
# use 'await'.
async def yield_(value=None):
    return await _yield_(value)


async def yield_from_(delegate):
    # Transcribed with adaptations from:
    #
    #   https://www.python.org/dev/peps/pep-0380/#formal-semantics
    #
    # This takes advantage of a sneaky trick: if an @async_generator-wrapped
    # function calls another async function (like yield_from_), and that
    # second async function calls yield_, then because of the hack we use to
    # implement yield_, the yield_ will actually propagate through yield_from_
    # back to the @async_generator wrapper. So even though we're a regular
    # function, we can directly yield values out of the calling async
    # generator.
    def unpack_StopAsyncIteration(e):
        if e.args:
            return e.args[0]
        else:
            return None

    _i = type(delegate).__aiter__(delegate)
    if hasattr(_i, "__await__"):
        _i = await _i
    try:
        _y = await type(_i).__anext__(_i)
    except StopAsyncIteration as _e:
        _r = unpack_StopAsyncIteration(_e)
    else:
        while 1:
            try:
                _s = await yield_(_y)
            except GeneratorExit as _e:
                try:
                    _m = _i.aclose
                except AttributeError:
                    pass
                else:
                    await _m()
                raise _e
            except BaseException as _e:
                _x = sys.exc_info()
                try:
                    _m = _i.athrow
                except AttributeError:
                    raise _e
                else:
                    try:
                        _y = await _m(*_x)
                    except StopAsyncIteration as _e:
                        _r = unpack_StopAsyncIteration(_e)
                        break
            else:
                try:
                    if _s is None:
                        _y = await type(_i).__anext__(_i)
                    else:
                        _y = await _i.asend(_s)
                except StopAsyncIteration as _e:
                    _r = unpack_StopAsyncIteration(_e)
                    break
    return _r


# This is the awaitable / iterator that implements asynciter.__anext__() and
# friends.
#
# Note: we can be sloppy about the distinction between
#
#   type(self._it).__next__(self._it)
#
# and
#
#   self._it.__next__()
#
# because we happen to know that self._it is not a general iterator object,
# but specifically a coroutine iterator object where these are equivalent.
class ANextIter:
    def __init__(self, it, first_fn, *first_args):
        self._it = it
        self._first_fn = first_fn
        self._first_args = first_args

    def __await__(self):
        return self

    def __next__(self):
        if self._first_fn is not None:
            first_fn = self._first_fn
            first_args = self._first_args
            self._first_fn = self._first_args = None
            return self._invoke(first_fn, *first_args)
        else:
            return self._invoke(self._it.__next__)

    def send(self, value):
        return self._invoke(self._it.send, value)

    def throw(self, type, value=None, traceback=None):
        return self._invoke(self._it.throw, type, value, traceback)

    def _invoke(self, fn, *args):
        try:
            result = fn(*args)
        except StopIteration as e:
            # The underlying generator returned, so we should signal the end
            # of iteration.
            raise StopAsyncIteration(e.value)
        except StopAsyncIteration as e:
            # PEP 479 says: if a generator raises Stop(Async)Iteration, then
            # it should be wrapped into a RuntimeError. Python automatically
            # enforces this for StopIteration; for StopAsyncIteration we need
            # to it ourselves.
            raise RuntimeError(
                "async_generator raise StopAsyncIteration"
            ) from e
        if _is_wrapped(result):
            raise StopIteration(_unwrap(result))
        else:
            return result


UNSPECIFIED = object()
try:
    from sys import get_asyncgen_hooks, set_asyncgen_hooks

except ImportError:
    import threading

    asyncgen_hooks = collections.namedtuple(
        "asyncgen_hooks", ("firstiter", "finalizer")
    )

    class _hooks_storage(threading.local):
        def __init__(self):
            self.firstiter = None
            self.finalizer = None

    _hooks = _hooks_storage()

    def get_asyncgen_hooks():
        return asyncgen_hooks(
            firstiter=_hooks.firstiter, finalizer=_hooks.finalizer
        )

    def set_asyncgen_hooks(firstiter=UNSPECIFIED, finalizer=UNSPECIFIED):
        if firstiter is not UNSPECIFIED:
            if firstiter is None or callable(firstiter):
                _hooks.firstiter = firstiter
            else:
                raise TypeError(
                    "callable firstiter expected, got {}".format(
                        type(firstiter).__name__
                    )
                )

        if finalizer is not UNSPECIFIED:
            if finalizer is None or callable(finalizer):
                _hooks.finalizer = finalizer
            else:
                raise TypeError(
                    "callable finalizer expected, got {}".format(
                        type(finalizer).__name__
                    )
                )


class AsyncGenerator:
    def __init__(self, coroutine):
        self._coroutine = coroutine
        self._it = coroutine.__await__()
        self.ag_running = False
        self._finalizer = None
        self._closed = False

    # On python 3.5.0 and 3.5.1, __aiter__ must be awaitable.
    # Starting in 3.5.2, it should not be awaitable, and if it is, then it
    #   raises a PendingDeprecationWarning.
    # See:
    #   https://www.python.org/dev/peps/pep-0492/#api-design-and-implementation-revisions
    #   https://docs.python.org/3/reference/datamodel.html#async-iterators
    #   https://bugs.python.org/issue27243
    if sys.version_info < (3, 5, 2):

        async def __aiter__(self):
            return self
    else:

        def __aiter__(self):
            return self

    ################################################################
    # Introspection attributes
    ################################################################

    @property
    def ag_code(self):
        return self._coroutine.cr_code

    @property
    def ag_frame(self):
        return self._coroutine.cr_frame

    ################################################################
    # Core functionality
    ################################################################

    # These need to return awaitables, rather than being async functions,
    # to match the native behavior where the firstiter hook is called
    # immediately on asend()/etc, even if the coroutine that asend()
    # produces isn't awaited for a bit.

    def __anext__(self):
        return self._do_it(self._it.__next__)

    def asend(self, value):
        return self._do_it(self._it.send, value)

    def athrow(self, type, value=None, traceback=None):
        return self._do_it(self._it.throw, type, value, traceback)

    def _do_it(self, start_fn, *args):
        coro_state = getcoroutinestate(self._coroutine)
        if coro_state is CORO_CREATED:
            (firstiter, self._finalizer) = get_asyncgen_hooks()
            if firstiter is not None:
                firstiter(self)

        # On CPython 3.5.2 (but not 3.5.0), coroutines get cranky if you try
        # to iterate them after they're exhausted. Generators OTOH just raise
        # StopIteration. We want to convert the one into the other, so we need
        # to avoid iterating stopped coroutines.
        if getcoroutinestate(self._coroutine) is CORO_CLOSED:
            raise StopAsyncIteration()

        async def step():
            if self.ag_running:
                raise ValueError("async generator already executing")
            try:
                self.ag_running = True
                return await ANextIter(self._it, start_fn, *args)
            finally:
                self.ag_running = False

        return step()

    ################################################################
    # Cleanup
    ################################################################

    async def aclose(self):
        state = getcoroutinestate(self._coroutine)
        if state is CORO_CLOSED or self._closed:
            return
        self._closed = True
        if state is CORO_CREATED:
            # Make sure that aclose() on an unstarted generator returns
            # successfully and prevents future iteration.
            self._it.close()
            return
        try:
            await self.athrow(GeneratorExit)
        except (GeneratorExit, StopAsyncIteration):
            pass
        else:
            raise RuntimeError("async_generator ignored GeneratorExit")

    def __del__(self):
        if getcoroutinestate(self._coroutine) is CORO_CREATED:
            # Never started, nothing to clean up, just suppress the "coroutine
            # never awaited" message.
            self._coroutine.close()
        if getcoroutinestate(self._coroutine
                             ) is CORO_SUSPENDED and not self._closed:
            if sys.implementation.name == "pypy":
                # pypy segfaults if we resume the coroutine from our __del__
                # and it executes any more 'await' statements, so we use the
                # old async_generator behavior of "don't even try to finalize
                # correctly". https://bitbucket.org/pypy/pypy/issues/2786/
                raise RuntimeError(
                    "partially-exhausted async_generator {!r} garbage collected"
                    .format(self.ag_code.co_name)
                )
            elif self._finalizer is not None:
                self._finalizer(self)
            else:
                # Mimic the behavior of native generators on GC with no finalizer:
                # throw in GeneratorExit, run for one turn, and complain if it didn't
                # finish.
                thrower = self.athrow(GeneratorExit)
                try:
                    thrower.send(None)
                except (GeneratorExit, StopAsyncIteration):
                    pass
                except StopIteration:
                    raise RuntimeError("async_generator ignored GeneratorExit")
                else:
                    raise RuntimeError(
                        "async_generator {!r} awaited during finalization; install "
                        "a finalization hook to support this, or wrap it in "
                        "'async with aclosing(...):'"
                        .format(self.ag_code.co_name)
                    )
                finally:
                    thrower.close()


if hasattr(collections.abc, "AsyncGenerator"):
    collections.abc.AsyncGenerator.register(AsyncGenerator)


def async_generator(coroutine_maker):
    @wraps(coroutine_maker)
    def async_generator_maker(*args, **kwargs):
        return AsyncGenerator(coroutine_maker(*args, **kwargs))

    async_generator_maker._async_gen_function = id(async_generator_maker)
    return async_generator_maker


def isasyncgen(obj):
    if hasattr(inspect, "isasyncgen"):
        if inspect.isasyncgen(obj):
            return True
    return isinstance(obj, AsyncGenerator)


def isasyncgenfunction(obj):
    if hasattr(inspect, "isasyncgenfunction"):
        if inspect.isasyncgenfunction(obj):
            return True
    return getattr(obj, "_async_gen_function", -1) == id(obj)
