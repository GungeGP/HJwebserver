from setuptools import setup, find_packages  # type: ignore[import]

setup(
    name="HJwebserver",
    version="0.1.3",
    # Explicitly package only the real source package to avoid accidentally
    # publishing stale build artifacts.
    packages=find_packages(include=["WebServer", "WebServer.*"]),
    package_dir={"WebServer": "WebServer"},
    include_package_data=True,
)