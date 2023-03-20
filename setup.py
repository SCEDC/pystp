"""
Settings for installing pystp with pip.
"""
from setuptools import setup, find_packages

setup(
    name = "PySTP",
    version = "0.1",
    packages = find_packages(),
    setup_requires = ["wheel"],
    install_requires = ["obspy>=1.2.0"]
    )
