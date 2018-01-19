import pytest
from functools import wraps, partial
import inspect


# Wrap any 'async def' tests so that they get automatically iterated.
# We used to use pytest-asyncio as a convenient way to do this, but nowadays
# pytest-asyncio uses us! In addition to it being generally bad for our test
# infrastructure to depend on the code-under-test, this totally messes up
# coverage info because depending on pytest's plugin load order, we might get
# imported before pytest-cov can be loaded and start gathering coverage.
@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    if inspect.iscoroutinefunction(pyfuncitem.obj):
        fn = pyfuncitem.obj

        @wraps(fn)
        def wrapper(**kwargs):
            coro = fn(**kwargs)
            try:
                coro.send(None)
            except StopIteration:
                pass

        pyfuncitem.obj = wrapper
