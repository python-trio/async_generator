Release history
===============

.. currentmodule:: async_generator

.. towncrier release notes start

1.9 (future)
------------

* Add :func:`asynccontextmanager`
* Move under the auspices of the Trio project
  * This includes a license change from MIT → dual MIT+Apache2
  * Various changes to project organization to match Trio project standard

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
