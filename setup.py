#!/usr/bin/env python3

"""Setup module."""
from setuptools import setup, find_packages
import os


def read(fname):
    """Read and return the contents of a file."""
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name='nite-stdcmd',
    version='0.0.1',
    description='NITE Standard Command module',
    long_description=read('README'),
    author='Kalman Olah',
    author_email='hello@kalmanolah.net',
    url='https://github.com/kalmanolah/nite-stdcmd',
    license='MIT',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'License :: OSI Approved :: MIT License',
    ],

    packages=find_packages(),
    entry_points={
        'nite.modules': ['stdcmd = nite_stdcmd:StdCmd']
    },

    install_requires=[
        'nite',
        'prettytable'
    ],
    dependency_links=[
        'git+https://github.com/kalmanolah/nite.git',
    ],
)
