import pytest

from . import aclosing, async_generator, yield_

@async_generator
async def async_range(count, closed_slot):
    try:
        for i in range(count):  # pragma: no branch
            await yield_(i)
    except GeneratorExit:
        closed_slot[0] = True

@pytest.mark.asyncio
async def test_aclosing():
    closed_slot = [False]
    async with aclosing(async_range(10, closed_slot)) as gen:
        it = iter(range(10))
        async for item in gen:  # pragma: no branch
            assert item == next(it)
            if item == 4:
                break
    assert closed_slot[0]

    closed_slot = [False]
    try:
        async with aclosing(async_range(10, closed_slot)) as gen:
            it = iter(range(10))
            async for item in gen:  # pragma: no branch
                assert item == next(it)
                if item == 4:
                    raise ValueError()
    except ValueError:
        pass
    assert closed_slot[0]
