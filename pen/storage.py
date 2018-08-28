#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
pen.storage - some special storage things
"""

import os

from paxo.storage import SimpleStorage

from . import edit


class PenStorage(SimpleStorage):
    def createList(self, listname):
        if listname not in self.data:
            self.data[listname] = {}

    def createNote(self, listname, notename):
        self.data[listname][notename] = ""

    def openNote(self, listname, notename):
        notepath = os.path.join("/var/tmp", notename)
        with open(notepath, "w") as file:
            file.write(self.data[listname][notename])
        edit.EditDisplay(notepath).main()
        with open(notepath, "r") as file:
            self.data[listname][notename] = file.read()
        os.remove(notepath)

    def deleteList(self, listname):
        self.data.pop(listname, None)

    def deleteNote(self, listname, notename):
        self.data[listname].pop(notename, None)


penStore = PenStorage()
