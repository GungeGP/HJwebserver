from setuptools import setup, find_packages  # type: ignore[import]

setup(
    name="HJwebserver",
    version="0.1.0",
    # find_packages() automatically looks for any folders with an __init__.py file
    packages=find_packages(), 
)