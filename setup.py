#!/usr/bin/env python
# encoding: utf-8

# setup.py

from setuptools import setup, find_packages

setup(
    name='PyTP',
    version='0.1',
    packages=find_packages(),
    description='Python Tape Backup Utility',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Matthias Nott',
    author_email='mnott@mnott.de',
    url='https://github.com/mnott/pytp',
    install_requires=[
        'sqlalchemy',
        'rich',
        'typer',
    ],
    entry_points={
        'console_scripts': [
            'pytp = pytp.cli:app',
        ],
    },
    classifiers=[
        # Classifiers help users find your project by categorizing it.
        # For a list of valid classifiers, see https://pypi.org/classifiers/
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: WTFPL License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)

