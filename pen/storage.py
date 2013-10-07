#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

import json
import zlib
from collections import OrderedDict

from . import edit
from .settings import PEN_FILE


class Storage(object):
    def __init__(self):
        self.data = {}

    def init(self):
        self.bootstrap()

    def bootstrap(self):
        if not os.path.exists(PEN_FILE):
            open(PEN_FILE, 'w').write(zlib.compress(json.dumps(self.data)))
        else:
            with open(PEN_FILE, 'r') as pen:
                path = json.loads(zlib.decompress(pen.read()), object_pairs_hook=OrderedDict).get("__PATH__")
                if path:
                    self.path = path
                    open(self.path, 'w').write(zlib.compress(json.dumps(self.data)))

    def read(self):
        with open(PEN_FILE, 'r') as pen:
            self.data = json.loads(zlib.decompress(pen.read()), object_pairs_hook=OrderedDict)

    def save(self):
        with open(PEN_FILE, 'w') as pen:
            pen.write(zlib.compress(json.dumps(self.data)))

    def createList(self, listname):
        if not listname in self.data:
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

store = Storage()
store.init()
