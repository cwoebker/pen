#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

import pen
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


# Grab requirments.
with open('reqs.txt') as f:
    required = f.readlines()

tests_require = ['nose']

settings = dict()


# Publish Helper.
if sys.argv[-1] == 'publish':
    os.system('python setup.py sdist upload')
    sys.exit()


settings.update(
    name='pen',
    version=pen.__version__,
    description='pen: terminal notes',
    long_description=open('README.md').read(),
    author=pen.__author__,
    author_email='me@cwoebker.com',
    url='https://github.com/cwoebker/pen',
    download_url='https://github.com/cwoebker/pen',
    license=pen.__license__,
    packages=['pen'],
    install_requires=required,
    entry_points={
        'console_scripts': [
            'pen = pen.cli:main',
        ],
    },
    classifiers=(
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Natural Language :: English',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Topic :: Software Development',
        'Topic :: Terminals',
        'Topic :: Utilities',
        'Topic :: Text Processing',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'License :: OSI Approved :: BSD License',
    ),
)

setup(**settings)
