from pathlib import Path

from setuptools import setup, find_packages

from async_generator import __version__

setup(
    name="async_generator",
    version=__version__,
    description="Async generators for Python 3.5",
    # Just in case the cwd is not the root of the source tree, or python is
    # not set to use utf-8 by default:
    long_description=Path(__file__).with_name("README.rst").read_text('utf-8'),
    author="Nathaniel J. Smith",
    author_email="njs@pobox.com",
    license="MIT",
    packages=find_packages(),
    url="https://github.com/njsmith/async_generator",
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
    ])
