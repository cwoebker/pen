# pen: notes on the command line

[`pen`](https://github.com/cwoebker/pen) is a minimalistic not taking app for the command line.

[![Status unavailable](https://secure.travis-ci.org/cwoebker/pen.png?branch=master)](http://travis-ci.org/cwoebker/pen)

---

## What is this? ##

With pen you can have notes everywhere. At least on every unix machine.
What makes it special is that it is a command line application only.
You can therefore even run it on a server without a gui.
Pen has a minimalistic interface and notes can be added and grouped in a simple manner.

## Installation

It's as simple as that:

`$ pip install pen`

## Usage

`pen <list> (<note>)` - Prints elements in list or opens note.

`pen all` - List all notes recursively.

`pen create <list>` - Create a list.

`pen delete <list> (<note>)` - Delete a list or note.

`pen list <list>` - List elements in a list.

`pen help <command>` - Displays help for a command.


## Advanced

`pen` stores all its data (with zlib compression) in the file `~/.pen`.
You are free to do whatever you want with the data in that file,
its yours after all.

So go out there and hack some code!

## Features ##

- Minimalistic and simple note editor.
- Auto save on close. No accidental closing anymore.
- Create lists to group notes.
- All the data is compressed.

## Contribute

[Fork and contribute!](http://github.com/cwoebker/pen)

---

For questions and suggestions, feel free to shoot me an email <me@cwoebker.com>

Follow [@cwoebker](http://twitter.com/cwoebker)

---

Copyright (c) 2013, Cecil Woebker.
License: BSD (see LICENSE for details)
