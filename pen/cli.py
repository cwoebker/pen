# -*- coding: utf-8 -*-
"""
pen.cli - command line stuff
"""

from paxo.core import Paxo

from pen import __version__
from pen.core import cmd_touch_note, cmd_list
from pen.storage import penStore

app = Paxo('pen', 'by Cecil Wöbker', '<command> | <note>',
           __version__, default_action=cmd_list, dynamic_action=cmd_touch_note, store=penStore)


def main():
    app.go()
