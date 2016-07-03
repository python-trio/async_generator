import types
import asyncio
import pytest

from . import async_generator, yield_

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

################################################################
#
# async_generators must return None
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
    with pytest.raises(RuntimeError):
        async for item in gen:
            assert False   # pragma: no cover

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
# close
#
################################################################

@async_generator
async def close_me_aiter(track):
    try:
        await yield_(1)
    except GeneratorExit:
        track[0] = True
        raise
    else:
        track[0] = False

def test_close():
    track = [None]
    aiter = close_me_aiter(track)
    coro = aiter.__anext__()
    try:
        next(coro)
    except StopIteration as exc:
        assert exc.value == 1
    coro.close()
    assert track[0]

################################################################
#
# yield from
#
################################################################

# XX disabled for now, see README
# # Test yield_from_
# @async_generator
# async def async_range_twice(count):
#     await yield_from_(async_range(count))
#     await yield_(None)
#     await yield_from_(async_range(count))
#
# @pytest.mark.asyncio
# async def test_async_yield_from_():
#     assert await collect(async_range_twice(3)) == [
#         0, 1, 2, None, 0, 1, 2,
#     ]
