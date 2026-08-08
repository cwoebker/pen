# pen: terminal notes

[`pen`](https://github.com/cwoebker/pen) is a minimalistic note taking app for the command line.

[![CI](https://github.com/cwoebker/pen/actions/workflows/ci.yml/badge.svg)](https://github.com/cwoebker/pen/actions/workflows/ci.yml)
[![PyPI Version](https://img.shields.io/pypi/v/penpal.svg)](https://pypi.python.org/pypi/penpal)
[![PyPI Python Versions](https://img.shields.io/pypi/pyversions/penpal.svg)](https://pypi.python.org/pypi/penpal)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

---

## What is this?

With pen you can have notes everywhere. At least on every unix machine.
What makes it special is that it is "only" a command line application.
Therefore you can even run it on your own server.
Pen has a minimalistic interface; notes can be added and grouped in a simple manner.

Your notes are plain markdown files in plain directories. There is no database
and no index. You can read, grep and edit them with anything you already use.

![Pen Terminal](https://cwoebker.com/assets/img/posts/pen.jpg)

## Install

```sh
uv tool install penpal
```

Or with pipx or pip:

```sh
pipx install penpal
pip install penpal
```

Unfortunately "pen" was already taken on PyPI, so the distribution is `penpal`
while the command is `pen`.

Requires Python 3.11 or newer.

## Usage

```
pen                          list every list, with note counts
pen all                      list every note in every list
pen <list>                   list the notes in one list
pen <list> <note>            open a note in the editor (creates it if new)
pen create <list>            create a list
pen show <list> <note>       print a note and its metadata
pen delete <list>            delete a list and all of its notes
pen delete <list> <note>     delete a single note
pen path                     print where notes are stored
pen path <dir>               store notes somewhere else
pen path default             go back to the default location
pen --help                   full help; `pen <command> --help` for one command
```

### Flags

| Flag | Applies to | What it does |
| --- | --- | --- |
| `-v`, `--version` | | Print the version. |
| `-h`, `--help` | any command | Show help. |
| `--path DIRECTORY` | any command | Use a different store for one invocation, without changing the configured one. |
| `--external` | `pen <list> <note>` | Edit in `$VISUAL`/`$EDITOR` instead of the built-in editor. |
| `--builtin` | `pen <list> <note>` | Force the built-in editor. This is the default. |
| `-y`, `--yes` | `pen delete` | Skip the confirmation prompt. Useful in scripts. |

Every command exits `0` on success and non-zero on failure, so `pen` works in
scripts with `&&` and `set -e`.

### The editor

The built-in editor is a small urwid screen. `esc` saves and closes; `enter`,
`backspace` and `delete` edit the text. To use your own editor instead, pass
`--external` and pen hands the note to `$VISUAL` or `$EDITOR`.

## Where your notes live

By default, under `$XDG_DATA_HOME/pen` (`~/.local/share/pen` unless you have
set `XDG_DATA_HOME`):

```
~/.local/share/pen/
├── work/
│   ├── todo.md
│   └── standup.md
└── personal/
    └── groceries.md
```

Lists are directories. Notes are markdown files with YAML frontmatter:

```markdown
---
created: 2026-08-06T09:12:44+00:00
modified: 2026-08-06T11:03:07+00:00
---

buy milk
```

Since it is only files, the data is yours to do what you like with. Point
`pen path` at a Dropbox or Syncthing folder to keep notes in sync across
machines; a sync conflict there costs you one note, not the whole store.
Search them with `rg TODO ~/.local/share/pen`. Drop a plain `.md` file into a
list directory and pen picks it up, no frontmatter required.

Frontmatter keys pen does not own, such as `tags` or `aliases`, are written
back byte for byte, including block lists and nested mappings. pen only ever
rewrites `created` and `modified`.

Names pen would refuse to create, such as one named after a command or one
ending in a space, are listed as ignored. Rename the file and pen picks it up.

To move the store:

```sh
pen path ~/Dropbox/pen
```

You can also set `PEN_PATH` to override the location for a single command, or
pass `--path`.

### Upgrading from 0.5.x and earlier

Older versions kept everything in one zlib-compressed JSON blob. The first time
you run `pen` after upgrading, that blob is unpacked into the directory layout
above automatically. **The original file is kept as `pen.bak` and never
deleted**, so nothing is lost if you want to go back or check the conversion.

Notes migrated this way get `created` and `modified` backfilled from the old
file's modification time, since the old format stored no timestamps at all.

Names the old format allowed but this one does not are imported under a
numbered variant. A list called `all` becomes `all-1`, since `pen all` would
otherwise never reach it.

## Development

pen uses [mise](https://mise.jdx.dev/) to pin the toolchain and
[uv](https://docs.astral.sh/uv/) for everything else.

```sh
git clone https://github.com/cwoebker/pen
cd pen

mise install          # python 3.11 + uv, as pinned in mise.toml
uv sync               # create .venv and install everything

uv run pen --help     # run it
```

The same checks CI runs:

```sh
uv run ruff check .            # lint
uv run ruff format --check .   # formatting
uv run ty check                # types
uv run pytest                  # tests, with branch coverage
```

`uv run ruff check --fix .` and `uv run ruff format .` fix most of what those
report.

Install the git hooks so the same checks run before each commit:

```sh
uv run pre-commit install
uv run pre-commit run --all-files
```

The test suite never touches a real store, a real home directory or the
network.

### Releasing

1. Add a `## <version> ##` section to `HISTORY.md`.
2. Run the **Bump version** workflow and pick `patch`, `minor` or `major`.

That bumps `pyproject.toml`, refreshes `uv.lock`, tags the commit and starts
the release workflow. The release workflow checks the tag against the project
version and checks the version is not on PyPI already, then builds, runs the
suite on 3.11 to 3.13, publishes with trusted publishing and creates the GitHub
release from the changelog section. If a step fails nothing is published.

## Contribute

[Fork and contribute!](https://github.com/cwoebker/pen)

---

For questions and suggestions, feel free to shoot me an email at <me@cwoebker.com>.

---

Copyright (c) 2013-2026 Cecil Wöbker.
License: MIT (see [LICENSE](LICENSE) for details)
