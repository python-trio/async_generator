import asyncio
import pytest

from async_generator import async_generator, yield_

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

# like list(it) but works on async iterators
async def collect(ait):
    items = []
    async for value in ait:
        items.append(value)
    return items

@pytest.mark.asyncio
async def test_async_generator():
    assert await collect(async_range(10)) == list(range(10))
    assert (await collect(double(async_range(5)))
            == [0, 2, 4, 6, 8])

    tripler = HasAsyncGenMethod(3)
    assert (await collect(tripler.async_multiplied(async_range(5)))
            == [0, 3, 6, 9, 12])

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
