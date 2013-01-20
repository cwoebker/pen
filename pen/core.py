# -*- coding: utf-8 -*-
"""
pen.core - the basic ingredients to a great battery
"""

import sys

from clint.textui import puts, indent

from .storage import store


class ExitStatus:
    """Exit status code constants."""
    OK = 0
    ERROR = 1
    ABORT = 2


def show_error(msg):
    sys.stdout.flush()
    sys.stderr.write(msg + '\n')


def cmd_list(args):
    """List all element in pen"""
    for penlist in store.data:
        puts(penlist + " (" + str(len(store.data[penlist])) + ")")


def cmd_all(args):
    """List everything recursively"""
    for penlist in store.data:
        puts(penlist)
        with indent(4, '  -'):
            for penfile in store.data[penlist]:
                puts(penfile)


def cmd_create_list(args):
    """Creates a list"""
    name = args.get(0)
    if name:
        store.createList(name)
    else:
        puts("not valid")


def cmd_touch_note(args):
    """Create a note"""
    major = args.get(0)
    minor = args.get(1)
    if major in store.data:
        if minor == None:  # show items in list
            with indent(4, '  -'):
                for note in store.data[major]:
                    puts(note)
        elif minor in store.data[major]:
            store.openNote(major, minor)
        else:
            store.createNote(major, minor)
            store.openNote(major, minor)
    else:
        puts("No list of that name.")


def cmd_delete(args):
    """Deletes a node"""
    major = args.get(0)
    minor = args.get(1)
    if major != None:
        if major in store.data:
            if minor == None:
                if len(store.data[major]) > 0:
                    if raw_input("are you sure (y/n)? ") not in ['y', 'Y', 'yes', 'Yes']:
                        return ExitStatus.ABORT
                store.deleteList(major)
                puts("list deleted")
            elif minor in store.data[major]:
                store.deleteNote(major, minor)
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


class List(object):
    def __init__(self, name):
        self.notes = []
        self.name = name

    def add_note(self, note):
        if self.get_note(note.name):
            self.delete_note(note.name)
        self.notes.append(note)

    def delete_note(self, name):
        for note in self.notes:
            if name == note.name:
                self.notes.remove(note)
                return True
        return False

    def get_note(self, name):
        for note in self.notes:
            if name == note.name:
                return note
        return None


class Note(object):
    def __init__(self, name, content):
        self.name = name
        self.content = content

    def short_name(self):
        if len(self.name) > 15:
            return self.name[0:14]
        return self.name
