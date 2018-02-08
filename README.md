# pen: terminal notes

[`pen`](https://github.com/cwoebker/pen) is a minimalistic note taking app for the command line.

[![PyPI Version](https://img.shields.io/pypi/v/penpal.svg)](https://pypi.python.org/pypi/penpal)
[![Build Status](https://secure.travis-ci.org/cwoebker/pen.png?branch=master)](http://travis-ci.org/cwoebker/pen)
[![PyPI License](https://img.shields.io/pypi/l/penpal.svg)](https://pypi.python.org/pypi/penpal)
[![PyPI Python Versions](https://img.shields.io/pypi/pyversions/penpal.svg)](https://pypi.python.org/pypi/penpal)
[![Say Thanks!](https://img.shields.io/badge/Say%20Thanks-!-1EAEDB.svg)](https://saythanks.io/to/cwoebker)

---

## What is this? ##

With pen you can have notes everywhere. At least on every unix machine.
What makes it special is that it is “only“ a command line application.
Therefore you can even run it on your own server.
Pen has a minimalistic interface; notes can be added and grouped in a simple manner.

![Pen Terminal](https://cwoebker.com/assets/img/posts/pen.jpg)

## Installation

It's as simple as that:

`$ pip install penpal`

Unfortunately "pen" was already taken.

## Usage

`pen all` - List all notes recursively.

`pen create <list>` - Create a list.

`pen delete <list> (<note>)` - Delete a list or note.

`pen help` - Display help information.

`pen help <command>` - Displays help for a command.

## Advanced

`pen` stores all its data (with zlib compression) in the file `~/.pen`.
You are free to do whatever you want with this data, it is yours after all.
This is helpful, if you want to keep your notes synchronized over multiple computers.
Move the data file over to your Dropbox folder for example.

You can also change the path of the storage file:

`pen path <path>` - Either prints the current storage path or sets a new one.

So go out there and hack some code!

## Features ##

- Minimalistic and simple note editor.
- Automatic saving when closed.
- Create lists to group notes.
- Put the storage file wherever you want. (Supports Dropbox & co.)

## Contribute

[Fork and contribute!](https://github.com/cwoebker/pen)

---

For questions and suggestions, feel free to shoot me an email at <me@cwoebker.com>.

Also, follow or tweet [@cwoebker](https://twitter.com/cwoebker).

---

Copyright (c) 2013-2018, Cecil Woebker.
License: BSD (see LICENSE for details)
