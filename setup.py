from setuptools import setup, find_packages

from async_generator import __version__

setup(
    name="async_generator",
    version=__version__,
    description="Async generators for Python 3.5",
    long_description=open("README.rst").read(),
    author="Nathaniel J. Smith",
    author_email="njs@pobox.com",
    license="MIT",
    packages=find_packages(),
    url="https://github.com/njsmith/async_generator",
    py_modules=["async_generator"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
    ])
