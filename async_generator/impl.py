import sys
import warnings
from functools import wraps
from types import coroutine

class YieldWrapper:
    def __init__(self, payload):
        self.payload = payload

# The magic @coroutine decorator is how you write the bottom level of
# coroutine stacks -- 'async def' can only use 'await' = yield from; but
# eventually we must bottom out in a @coroutine that calls plain 'yield'.
@coroutine
def _yield_(value):
    return (yield YieldWrapper(value))

# But we wrap the bare @coroutine version in an async def, because async def
# has the magic feature that users can get warnings messages if they forget to
# use 'await'.
async def yield_(value):
    return await _yield_(value)

# class YieldFromWrapper:
#     def __init__(self, payload):
#         self.payload = payload
#
# @coroutine
# def _yield_from_(delegate):
#     return (yield YieldFromWrapper(delegate))
#
# async def yield_from_(delegate):
#     delegate = type(delegate).__aiter__()
#     if sys.version_info < (3, 5, 2):
#         delegate = await delegate
#     return await _yield_from_(delegate)

# This is the awaitable / iterator returned from asynciter.__anext__() and
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
            if e.value is not None:
                raise RuntimeError(
                    "@async_generator functions must return None")
            raise StopAsyncIteration
        if isinstance(result, YieldWrapper):
            raise StopIteration(result.payload)
        else:
            return result

class AsyncGenerator:
    def __init__(self, coroutine):
        self._coroutine = coroutine
        self._it = type(coroutine).__await__(coroutine)

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

    def __anext__(self):
        return ANextIter(self._it, self._it.__next__)

    def asend(self, value):
        return ANextIter(self._it, self._it.send, value)

    def athrow(self, *args):
        return ANextIter(self._it, self._it.throw, *args)

    def _coro_running(self):
        # This is a trick to tell whether the coroutine was left
        # partially-complete -- if it hasn't started yet, then it isn't
        # awaiting on anything; if it's finished, then it isn't awaiting on
        # anything; but if it's in the middle of running, then it's always
        # awaiting on something.
        return self._coroutine.cr_await is not None

    async def aclose(self):
        if not self._coro_running():
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
        if self._coro_running():
            # This exception will get swallowed because this is __del__, but
            # it's an easy way to trigger the print-to-console logic
            raise RuntimeError(
                "partially-exhausted async_generator garbage collected")

def async_generator(coroutine_maker):
    @wraps(coroutine_maker)
    def async_generator_maker(*args, **kwargs):
        return AsyncGenerator(coroutine_maker(*args, **kwargs))
    return async_generator_maker
