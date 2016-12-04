import types
import sys
import asyncio
import pytest
import collections.abc

from . import (
    async_generator, yield_, yield_from_, isasyncgen, isasyncgenfunction,
)

# like list(it) but works on async iterators
async def collect(ait):
    items = []
    async for value in ait:
        items.append(value)
    return items

################################################################
#
# Basic test
#
################################################################

@async_generator
async def async_range(count):
    for i in range(count):
        print("Calling yield_({})".format(i))
        await yield_(i)

@async_generator
async def double(ait):
    async for value in ait:
        await yield_(value * 2)
        await asyncio.sleep(0.001)

class HasAsyncGenMethod:
    def __init__(self, factor):
        self._factor = factor

    @async_generator
    async def async_multiplied(self, ait):
        async for value in ait:
            await yield_(value * self._factor)

@pytest.mark.asyncio
async def test_async_generator():
    assert await collect(async_range(10)) == list(range(10))
    assert (await collect(double(async_range(5)))
            == [0, 2, 4, 6, 8])

    tripler = HasAsyncGenMethod(3)
    assert (await collect(tripler.async_multiplied(async_range(5)))
            == [0, 3, 6, 9, 12])

@async_generator
async def agen_yield_no_arg():
    await yield_()

@pytest.mark.asyncio
async def test_yield_no_arg():
    assert await collect(agen_yield_no_arg()) == [None]

################################################################
#
# async_generators return value
#
################################################################

@async_generator
async def async_gen_with_non_None_return():
    await yield_(1)
    await yield_(2)
    return "hi"

@pytest.mark.asyncio
async def test_bad_return_value():
    gen = async_gen_with_non_None_return()
    async for item in gen:
        assert item == 1
        break
    async for item in gen:
        assert item == 2
        break
    try:
        await gen.__anext__()
    except StopAsyncIteration as e:
        assert e.args[0] == "hi"

################################################################
#
# Exhausitve tests of the different ways to re-enter a coroutine.
#
# It used to be that re-entering via send/__next__ would work, but throw()
# immediately followed by an await yield_(...)  wouldn't work, and the
# YieldWrapper object would propagate back out to the coroutine runner.
#
# Before I fixed this, the 'assert value is None' check below would fail
# (because of the YieldWrapper leaking out), and if you removed that
# assertion, then the code would appear to run successfully but the final list
# would just be [1, 3] instead of [1, 2, 3].
#
################################################################

class MyTestError(Exception):
    pass

# This unconditionally raises a MyTestError exception, so from the outside
# it's equivalent to a simple 'raise MyTestError`. But, for this test to check
# the thing we want it to check, the point is that the exception must be
# thrown in from the coroutine runner -- this simulates something like an
# 'await sock.recv(...) -> TimeoutError'.
@types.coroutine
def hit_me():
    yield "hit me"

@types.coroutine
def number_me():
    assert (yield "number me") == 1

@types.coroutine
def next_me():
    assert (yield "next me") is None

@async_generator
async def yield_after_different_entries():
    await yield_(1)
    try:
        await hit_me()
    except MyTestError:
        await yield_(2)
    await number_me()
    await yield_(3)
    await next_me()
    await yield_(4)

def hostile_coroutine_runner(coro):
    coro_iter = coro.__await__()
    value = None
    while True:
        try:
            if value == "hit me":
                value = coro_iter.throw(MyTestError())
            elif value == "number me":
                value = coro_iter.send(1)
            else:
                assert value in (None, "next me")
                value = coro_iter.__next__()
        except StopIteration as exc:
            return exc.value

def test_yield_different_entries():
    coro = collect(yield_after_different_entries())
    yielded = hostile_coroutine_runner(coro)
    assert yielded == [1, 2, 3, 4]

################################################################
#
# asend
#
################################################################

@async_generator
async def asend_me():
    assert (await yield_(1)) == 2
    assert (await yield_(3)) == 4

@pytest.mark.asyncio
async def test_asend():
    aiter = asend_me()
    assert (await aiter.__anext__()) == 1
    assert (await aiter.asend(2)) == 3
    with pytest.raises(StopAsyncIteration):
        await aiter.asend(4)


################################################################
#
# athrow
#
################################################################

@async_generator
async def athrow_me():
    with pytest.raises(KeyError):
        await yield_(1)
    with pytest.raises(ValueError):
        await yield_(2)
    await yield_(3)

@pytest.mark.asyncio
async def test_athrow():
    aiter = athrow_me()
    assert (await aiter.__anext__()) == 1
    assert (await aiter.athrow(KeyError("oops"))) == 2
    assert (await aiter.athrow(ValueError("oops"))) == 3
    with pytest.raises(OSError):
        await aiter.athrow(OSError("oops"))

################################################################
#
# aclose
#
################################################################

@async_generator
async def close_me_aiter(track):
    try:
        await yield_(1)
    except GeneratorExit:
        track[0] = "closed"
        raise
    else:  # pragma: no cover
        track[0] = "wtf"

@pytest.mark.asyncio
async def test_aclose():
    track = [None]
    aiter = close_me_aiter(track)
    async for obj in aiter:
        assert obj == 1
        break
    assert track[0] is None
    await aiter.aclose()
    assert track[0] == "closed"

@pytest.mark.asyncio
async def test_aclose_on_unstarted_generator():
    aiter = close_me_aiter([None])
    await aiter.aclose()
    async for obj in aiter:
        assert False  # pragma: no cover

@pytest.mark.asyncio
async def test_aclose_on_finished_generator():
    aiter = async_range(3)
    async for obj in aiter:
        pass  # pragma: no cover
    await aiter.aclose()

@async_generator
async def sync_yield_during_aclose():
    try:
        await yield_(1)
    finally:
        await asyncio.sleep(0)

@async_generator
async def async_yield_during_aclose():
    try:
        await yield_(1)
    finally:
        await yield_(2)

@pytest.mark.asyncio
async def test_aclose_yielding():
    aiter = sync_yield_during_aclose()
    assert (await aiter.__anext__()) == 1
    # Doesn't raise:
    await aiter.aclose()

    aiter = async_yield_during_aclose()
    assert (await aiter.__anext__()) == 1
    with pytest.raises(RuntimeError):
        await aiter.aclose()

################################################################
#
# yield from
#
################################################################

@async_generator
async def async_range_twice(count):
    await yield_from_(async_range(count))
    await yield_(None)
    await yield_from_(async_range(count))

if sys.version_info >= (3, 6):
    exec("""
async def native_async_range(count):
    for i in range(count):
        yield i

async def native_async_range_twice(count):
    # make sure yield_from_ works inside a native async generator
    await yield_from_(async_range(count))
    yield None
    # make sure we can yield_from_ a native async generator
    await yield_from_(native_async_range(count))
    """)

@pytest.mark.asyncio
async def test_async_yield_from_():
    assert await collect(async_range_twice(3)) == [
        0, 1, 2, None, 0, 1, 2,
    ]

    if sys.version_info >= (3, 6):
        assert await collect(native_async_range_twice(3)) == [
            0, 1, 2, None, 0, 1, 2,
        ]

@async_generator
async def doubles_sends(value):
    while True:
        value = await yield_(2 * value)

@async_generator
async def wraps_doubles_sends(value):
    await yield_from_(doubles_sends(value))

@pytest.mark.asyncio
async def test_async_yield_from_asend():
    gen = wraps_doubles_sends(10)
    await gen.__anext__() == 20
    assert (await gen.asend(2)) == 4
    assert (await gen.asend(5)) == 10
    assert (await gen.asend(0)) == 0
    await gen.aclose()

@pytest.mark.asyncio
async def test_async_yield_from_athrow():
    gen = async_range_twice(2)
    assert (await gen.__anext__()) == 0
    with pytest.raises(ValueError):
        await gen.athrow(ValueError)

@async_generator
async def returns_1():
    await yield_(0)
    return 1

@async_generator
async def yields_from_returns_1():
    await yield_(await yield_from_(returns_1()))

@pytest.mark.asyncio
async def test_async_yield_from_return_value():
    assert await collect(yields_from_returns_1()) == [0, 1]

# Special cases to get coverage
@pytest.mark.asyncio
async def test_yield_from_empty():
    @async_generator
    async def empty():
        return "done"

    @async_generator
    async def yield_from_empty():
        assert (await yield_from_(empty())) == "done"

    assert await collect(yield_from_empty()) == []

@pytest.mark.asyncio
async def test_yield_from_non_generator():
    class Countdown:
        def __init__(self, count):
            self.count = count
            self.closed = False

        if sys.version_info < (3, 5, 2):
            async def __aiter__(self):
                return self
        else:
            def __aiter__(self):
                return self

        async def __anext__(self):
            self.count -= 1
            if self.count < 0:
                raise StopAsyncIteration("boom")
            return self.count

        async def aclose(self):
            self.closed = True

    @async_generator
    async def yield_from_countdown(count, happenings):
        try:
            c = Countdown(count)
            assert (await yield_from_(c)) == "boom"
        except BaseException as e:
            if c.closed:
                happenings.append("countdown closed")
            happenings.append("raise")
            return e
    h = []
    assert await collect(yield_from_countdown(3, h)) == [2, 1, 0]
    assert h == []

    # Throwing into a yield_from_(object with no athrow) just raises the
    # exception in the generator.
    h = []
    agen = yield_from_countdown(3, h)
    assert await agen.__anext__() == 2
    exc = ValueError("x")
    try:
        await agen.athrow(exc)
    except StopAsyncIteration as e:
        assert e.args[0] is exc
    assert h == ["raise"]

    # Calling aclose on the generator calls aclose on the iterator
    h = []
    agen = yield_from_countdown(3, h)
    assert await agen.__anext__() == 2
    await agen.aclose()
    assert h == ["countdown closed", "raise"]

    # Throwing GeneratorExit into the generator calls *aclose* on the iterator
    # (!)
    h = []
    agen = yield_from_countdown(3, h)
    assert await agen.__anext__() == 2
    exc = GeneratorExit()
    with pytest.raises(StopAsyncIteration):
        await agen.athrow(exc)
    assert h == ["countdown closed", "raise"]

@pytest.mark.asyncio
async def test_yield_from_non_generator_with_no_aclose():
    class Countdown:
        def __init__(self, count):
            self.count = count
            self.closed = False

        if sys.version_info < (3, 5, 2):
            async def __aiter__(self):
                return self
        else:
            def __aiter__(self):
                return self

        async def __anext__(self):
            self.count -= 1
            if self.count < 0:
                raise StopAsyncIteration("boom")
            return self.count

    @async_generator
    async def yield_from_countdown(count):
        return await yield_from_(Countdown(count))

    assert await collect(yield_from_countdown(3)) == [2, 1, 0]

    agen = yield_from_countdown(3)
    assert await agen.__anext__() == 2
    assert await agen.__anext__() == 1
    # It's OK that Countdown has no aclose
    await agen.aclose()

@pytest.mark.asyncio
async def test_yield_from_with_old_style_aiter():
    # old-style 'async def __aiter__' should still work even on newer pythons
    class Countdown:
        def __init__(self, count):
            self.count = count
            self.closed = False

        # This is wrong, that's the point
        async def __aiter__(self):
            return self

        async def __anext__(self):
            self.count -= 1
            if self.count < 0:
                raise StopAsyncIteration("boom")
            return self.count

    @async_generator
    async def yield_from_countdown(count):
        return await yield_from_(Countdown(count))

    assert await collect(yield_from_countdown(3)) == [2, 1, 0]

@pytest.mark.asyncio
async def test_yield_from_athrow_raises_StopAsyncIteration():
    @async_generator
    async def catch():
        try:
            while True:
                await yield_("hi")
        except Exception as exc:
            return ("bye", exc)

    @async_generator
    async def yield_from_catch():
        return await yield_from_(catch())

    agen = yield_from_catch()
    assert await agen.__anext__() == "hi"
    assert await agen.__anext__() == "hi"
    thrown = ValueError("oops")
    try:
        print(await agen.athrow(thrown))
    except StopAsyncIteration as caught:
        assert caught.args == (("bye", thrown),)
    else:
        raise AssertionError  # pragma: no cover

################################################################
# __del__
################################################################

@pytest.mark.asyncio
async def test___del__():
    gen = async_range(10)
    # Hasn't started yet, so no problem
    gen.__del__()

    gen = async_range(10)
    await collect(gen)
    # Exhausted, so no problem
    gen.__del__()

    gen = async_range(10)
    await gen.aclose()
    # Closed, so no problem
    gen.__del__()

    gen = async_range(10)
    await gen.__anext__()
    await gen.aclose()
    # Closed, so no problem
    gen.__del__()

    gen = async_range(10)
    await gen.__anext__()
    # Started, but not exhausted or closed -- big problem
    with pytest.raises(RuntimeError):
        gen.__del__()


################################################################
# introspection
################################################################

def test_isasyncgen():
    assert not isasyncgen(async_range)
    assert isasyncgen(async_range(10))

    if sys.version_info >= (3, 6):
        assert not isasyncgen(native_async_range)
        assert isasyncgen(native_async_range(10))

def test_isasyncgenfunction():
    assert isasyncgenfunction(async_range)
    assert not isasyncgenfunction(list)
    assert not isasyncgenfunction(async_range(10))

    if sys.version_info >= (3, 6):
        assert isasyncgenfunction(native_async_range)
        assert not isasyncgenfunction(native_async_range(10))

def test_collections_abc_AsyncGenerator():
    if hasattr(collections.abc, "AsyncGenerator"):
        assert isinstance(async_range(10), collections.abc.AsyncGenerator)
