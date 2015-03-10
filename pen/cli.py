# -*- coding: utf-8 -*-
"""
pen.cli - command line stuff
"""

from paxo import Paxo

from pen import __version__
from pen.core import cmd_touch_note, cmd_list
from pen.storage import penStore

app = Paxo('pen', 'a Cecil Woebker project.', '<command> | <note>',
           __version__, default_action=cmd_list, dynamic_action=cmd_touch_note, store=penStore)


def main():
    app.go()
