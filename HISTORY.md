# History #

## 0.6.1 ##

*August 15th 2026*

Release tooling only; no user-facing changes.

- The bump workflow derives the version from this file. Its `auto` default
  releases the top section, so the next version no longer has to be predicted
  and written in before the bump runs.
- Picking patch/minor/major instead generates the section from commit subjects
  since the last tag, behind an approval gate that shows the notes before
  anything is tagged or pushed.
- The release trigger matches `v*.*.*` only, so a stray or prerelease tag
  cannot start a publish.
- ty type-checks against Python 3.11, pen's actual floor, rather than whatever
  interpreter runs it, and coverage settings moved into `pyproject.toml` so a
  direct `coverage` run behaves like pytest's.

## 0.6.0 ##

*August 9th 2026*

**Storage**

- Notes are stored as `<store>/<list>/<note>.md` with YAML frontmatter, instead
  of one zlib-compressed JSON blob. Lists are directories, so the store can be
  grepped, synced and opened in any editor.
- Migration is automatic on first run. **Your old file is kept as `pen.bak` and
  never deleted.** Migrated notes get `created`/`modified` backfilled from the
  old file's modification time, since the old format stored no timestamps.
- A write touches one file, atomically. The old store rewrote every note on
  every command, including read-only ones like `pen all`, with no
  temp-file-and-rename, so an interrupt mid-write could lose everything.
- Notes carry `created` and `modified` timestamps, shown by `pen all` and the
  new `pen show`.
- Frontmatter keys pen does not own, such as `tags` or `aliases`, are preserved
  when pen rewrites a note. Anything pen cannot parse as a flat scalar (block
  lists, nested mappings, flow collections, anchors) is written back byte for
  byte.
- A plain `.md` file dropped into a list directory is picked up as a note, no
  frontmatter required.
- Migration reads and validates the old file before moving anything, so a path
  that turns out not to be a pen store is left exactly as it was. A second
  migration never overwrites the first one's `.bak`.
- Legacy names this version would refuse are imported under a numbered
  variant. A list called `all` becomes `all-1`, since `pen all` would otherwise
  never reach it.
- A file or directory whose name pen would not create is reported as ignored.
  It used to fail whichever command happened to enumerate it.
- `pen delete <list>` refuses, before removing anything, if the directory holds
  files pen did not create.
- Tabs in a note are left as tabs. The built-in editor displays them expanded,
  since urwid and the terminal measure a tab differently, and writes back any
  line you did not edit exactly as it was.

**Fixed**

- `pen delete <list>` crashed with `NameError` on any non-empty list. The
  confirmation prompt called `raw_input()`, which is Python 2 only.
- Every command exited `0`, including errors and crashes. Failures now exit
  non-zero, so `pen` composes with `&&` and `set -e`.
- Note names were not validated and were joined onto `/var/tmp`, so a name like
  `../../etc/passwd` wrote there and then deleted it. Notes also never touch a
  shared temp directory now, so they are no longer briefly world-readable.
- `pen create all` succeeded and left the list permanently unreachable, because
  `pen all` resolved to the built-in command. List names that would shadow a
  command are now rejected.
- The editor silently collapsed runs of spaces into tab characters on save.
- `pen --help` and `pen --version` exited `3` and `4`. They exit `0`.
- `pen path` no longer opens the store it is about to replace, and records a
  new location only once it opens. A typo used to be saved anyway, after which
  every command including `pen path default` failed and there was no way back.
- `pen path <relative>` stores an absolute path. It used to be saved verbatim,
  so the store moved with the shell's working directory.
- A list or note name containing `[` is printed literally instead of being read
  as terminal markup and swallowed, or aborting the command outright.
- On macOS, a custom store location set by 0.4.x is found again. clint wrote it
  under `~/Library/Application Support`, which was not being looked at.

**Added**

- `pen show <list> <note>` prints a note with its metadata.
- `--external` opens a note in `$VISUAL`/`$EDITOR` instead of the built-in
  editor.
- `-y`/`--yes` skips the delete confirmation, for scripts.
- `--path` and `$PEN_PATH` override the store location for one invocation.

**Internals**

- Replaced the `clint` (unmaintained since 2015) and `paxo` (2020)
  dependencies with `click` and `rich`. No YAML dependency was added.
- Requires Python 3.11 or newer.
- Relicensed from BSD-3-Clause to MIT.
- Packaging moved to hatchling + uv; `setup.py`, `Pipfile`, `.travis.yml` and
  the `pen_run` wrapper are gone.
- Added a test suite (304 tests, 100% branch coverage), CI on 3.11 to 3.13,
  ruff, ty, pre-commit, Dependabot, and automated releases with PyPI trusted
  publishing.

## 0.4.2 ##

*November 15th 2018*

- Require new paxo version (0.2.2) in order to create directory for data file automatically

## 0.4.1 ##

*August 28th 2018*

- Using XDG_DATA_HOME as default for pen data file

## 0.4 ##

*March 23rd 2015*

- Some bug fixes
- Using my "paxo" cli library

## 0.3 ##

*October 17th 2013*

- Adds support for custom storage location
- Can also be stored in Dropbox & co
- Simplified usage
- First official release

## 0.1 ##

*January 20th 2013*

- First proof-of-concept version
- Minimalistic and simple note editor.
- Auto save on close. No accidental closing anymore.
- Create lists to group notes.
- All the data is compressed.
