# pen: terminal notes

[`pen`](https://github.com/cwoebker/pen) is a minimalistic note taking app for the command line.

[![Status unavailable](https://secure.travis-ci.org/cwoebker/pen.png?branch=master)](http://travis-ci.org/cwoebker/pen)

[![Code Issues](http://www.quantifiedcode.com/project/1ada6ecdf18548e08cf90fee32d28b93/badge.svg)](http://www.quantifiedcode.com/app#/project/1ada6ecdf18548e08cf90fee32d28b93)

---

## What is this? ##

With pen you can have notes everywhere. At least on every unix machine.
What makes it special is that it is “only“ a command line application.
Therefore you can even run it on your own server.
Pen has a minimalistic interface; notes can be added and grouped in a simple manner.

![Pen Terminal](http://cwoebker.com/assets/img/posts/pen.jpg)

## Installation

It's as simple as that:

`$ pip install penpal`

Unfortunately pen was already taken.

## Usage

`pen all` - List all notes recursively.

`pen create <list>` - Create a list.

`pen delete <list> (<note>)` - Delete a list or note.

`pen help` - Displays pen help

`pen help <command>` - Displays help for a command.

## Advanced

`pen` stores all its data (with zlib compression) in the file `~/.pen`.
You are free to do whatever you want with the data in that file, it is yours after all.

You can also change the path of the storage file:

`pen path <new_path>` - Either prints the current storage path or sets a new one.

So go out there and hack some code!

## Features ##

- Minimalistic and simple note editor.
- Automatic saving when closed.
- Create lists to group notes.
- Put the storage file wherever you want. (Supports Dropbox & co)

## Contribute

[Fork and contribute!](http://github.com/cwoebker/pen)

---

For questions and suggestions, feel free to shoot me an email <me@cwoebker.com>

Follow [@cwoebker](http://twitter.com/cwoebker)

---

Copyright (c) 2013-2018, Cecil Woebker.
License: BSD (see LICENSE for details)
