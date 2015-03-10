# -*- coding: utf-8 -*-
"""
pen.core - the basic ingredients to a great battery
"""

import os

from paxo.command import cmd
from paxo.util import ExitStatus

from clint.textui import puts, indent, colored
from clint import resources

from pen.storage import penStore


@cmd(usage='path (<pen_file_path>)', help='Read or set “pen“ storage path')
def cmd_path(args):
    path = args.get(0)
    if path:
        if path == "default":
            resources.user.write('path.ini', os.path.expanduser('~/.pen'))
        elif os.path.exists(path) or os.access(os.path.dirname(path), os.W_OK):
            resources.user.write('path.ini', path)
        else:
            puts(colored.red("Not a valid Path."))
    else:
        print penStore.path


@cmd(help='List elements.')
def cmd_list(args):
    """List all element in pen"""
    for penlist in penStore.data:
        puts(penlist + " (" + str(len(penStore.data[penlist])) + ")")


@cmd(help='List all notes.')
def cmd_all(args):
    """List everything recursively"""
    for penlist in penStore.data:
        puts(penlist)
        with indent(4, '  -'):
            for penfile in penStore.data[penlist]:
                puts(penfile)


@cmd(usage='create <list>', help='Create a list.')
def cmd_create(args):
    """Creates a list"""
    name = args.get(0)
    if name:
        penStore.createList(name)
    else:
        puts("not valid")


def cmd_touch_note(args):
    """Create a note"""
    major = args.get(0)
    minor = args.get(1)
    if major in penStore.data:
        if minor is None:  # show items in list
            for note in penStore.data[major]:
                puts(note)
        elif minor in penStore.data[major]:
            penStore.openNote(major, minor)
        else:
            penStore.createNote(major, minor)
            penStore.openNote(major, minor)
    else:
        puts("No list of that name.")


@cmd(usage='delete <list> (<note>)', help='Delete a list or note.')
def cmd_delete(args):
    """Deletes a node"""
    major = args.get(0)
    minor = args.get(1)
    if major is not None:
        if major in penStore.data:
            if minor is None:
                if len(penStore.data[major]) > 0:
                    if raw_input("are you sure (y/n)? ") not in ['y', 'Y', 'yes', 'Yes']:
                        return ExitStatus.ABORT
                penStore.deleteList(major)
                puts("list deleted")
            elif minor in penStore.data[major]:
                penStore.deleteNote(major, minor)
                puts("note deleted")
            else:
                puts("no such note, sorry! (%s)" % minor)
        else:
            puts("no such list, sorry! (%s)" % major)
    else:
        print """
- pen: delete help ------------------------------------------------------------

pen delete <list>                 deletes list and all of its notes
pen delete <list> <note>          deletes note
"""
