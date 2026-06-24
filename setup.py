from setuptools import setup, find_packages  # type: ignore[import]

setup(
    name="HJwebserver",
    version="0.1.1",
    # find_packages() automatically looks for any folders with an __init__.py file
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "WebServer": ["public/*"],
    },
)