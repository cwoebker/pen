# -*- coding: utf-8 -*-
"""
pen.settings - some global variables
"""

import os

from clint import resources

resources.init('cwoebker', 'pen')


PEN_FILE = resources.user.read('path.ini')
if not PEN_FILE:
    PEN_FILE = os.path.expanduser('~/.pen')
