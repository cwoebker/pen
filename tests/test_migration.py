"""Importing a legacy zlib+JSON blob store.

Both real-world layouts are covered:

* a blob file sitting inside the store root (``$XDG_DATA_HOME/pen/pen``);
* a configured store path that resolves to the blob file itself.

The fixtures are built with the genuine on-disk encoding rather than by calling
into pen, so a change to the writer cannot silently redefine what "legacy"
means.
"""

from __future__ import annotations

import json
import zlib
from pathlib import Path

import pytest

from pen.errors import MigrationError
from pen.names import MAX_NAME_LENGTH, validate_list_name, validate_note_name
from pen.storage import NoteStore, _clean, open_store

from .conftest import make_legacy_blob


def test_blob_inside_the_root_is_migrated(root: Path, legacy_blob: bytes) -> None:
    root.mkdir(parents=True)
    (root / "pen").write_bytes(legacy_blob)

    store = open_store(root)

    assert store.lists() == ["ideas", "work"]
    assert store.note_names("work") == ["standup", "todo"]
    assert store.read_note("work", "todo").body == "buy milk"
    assert store.read_note("work", "standup").body == "notes\nover\nlines"
    assert store.read_note("ideas", "app").body == "a pen"


def test_root_that_is_itself_a_blob_is_migrated(tmp_path: Path) -> None:
    """A configured path can resolve to the blob file rather than a directory."""
    root = tmp_path / "dropbox-pen"
    root.write_bytes(make_legacy_blob({"work": {"todo": "buy milk"}}))

    store = open_store(root)

    assert root.is_dir()
    assert store.read_note("work", "todo").body == "buy milk"
    assert (tmp_path / "dropbox-pen.bak").is_file()


def test_original_is_kept_as_bak(root: Path, legacy_blob: bytes) -> None:
    root.mkdir(parents=True)
    (root / "pen").write_bytes(legacy_blob)

    open_store(root)

    backup = root / "pen.bak"
    assert backup.is_file()
    assert backup.read_bytes() == legacy_blob, "the backup must be byte-identical"
    assert not (root / "pen").exists()


def test_migration_reports_what_it_moved(root: Path, legacy_blob: bytes) -> None:
    root.mkdir(parents=True)
    (root / "pen").write_bytes(legacy_blob)

    report = NoteStore(root).migrate_legacy()

    assert report is not None
    assert report.lists == 2
    assert report.notes == 3
    assert report.backup.endswith("pen.bak")


def test_migration_backfills_timestamps_from_the_blob_mtime(
    root: Path, legacy_blob: bytes
) -> None:
    """The blob format carries no timestamps; mtime is the only signal."""
    root.mkdir(parents=True)
    blob = root / "pen"
    blob.write_bytes(legacy_blob)
    mtime = blob.stat().st_mtime

    store = open_store(root)
    note = store.read_note("work", "todo")

    assert note.created == note.modified
    assert abs(note.created.timestamp() - mtime) < 2


def test_migration_is_idempotent(root: Path, legacy_blob: bytes) -> None:
    root.mkdir(parents=True)
    (root / "pen").write_bytes(legacy_blob)

    open_store(root)
    (root / "work" / "todo.md").write_text("edited since\n", encoding="utf-8")
    store = open_store(root)

    assert store.read_note("work", "todo").body == "edited since"
    assert NoteStore(root).migrate_legacy() is None


def test_path_redirect_key_is_dropped(root: Path) -> None:
    """__PATH__ is an in-blob store redirect and is not imported."""
    root.mkdir(parents=True)
    (root / "pen").write_bytes(
        make_legacy_blob({"__PATH__": "/elsewhere", "work": {"todo": "x"}})
    )

    store = open_store(root)

    assert store.lists() == ["work"]
    assert not (root / "__PATH__").exists()


def test_empty_legacy_store(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "pen").write_bytes(make_legacy_blob({}))
    assert open_store(root).lists() == []


@pytest.mark.parametrize(
    "name",
    ["../escape", "with/slash", "  padded  ", ".hidden", "", "..", "a" * 300],
)
def test_unsafe_legacy_names_are_sanitized_not_dropped(root: Path, name: str) -> None:
    """Importing under a changed name beats refusing to import a note."""
    root.mkdir(parents=True)
    (root / "pen").write_bytes(make_legacy_blob({name: {"note": "body"}}))

    store = open_store(root)

    assert len(store.lists()) == 1
    imported = store.lists()[0]
    assert "/" not in imported and "\\" not in imported
    assert imported == imported.strip()
    assert not imported.startswith(".")
    assert len(imported) <= 128
    assert store.read_note(imported, "note").body == "body"


def test_non_string_note_bodies_are_imported_as_empty(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "pen").write_bytes(make_legacy_blob({"work": {"todo": 42}}))
    assert open_store(root).read_note("work", "todo").body == ""


def test_non_dict_list_entries_are_skipped(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "pen").write_bytes(
        make_legacy_blob({"work": {"todo": "x"}, "junk": "not a dict"})
    )
    assert open_store(root).lists() == ["work"]


def test_corrupt_blob_is_reported_and_left_alone(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "pen").write_bytes(b"this is not zlib")

    with pytest.raises(MigrationError, match="not a readable pen store"):
        open_store(root)

    # Not renamed. A rename would make the second run find no blob, report an
    # empty store and exit 0, hiding the failure completely.
    assert (root / "pen").read_bytes() == b"this is not zlib"
    assert not (root / "pen.bak").exists()

    with pytest.raises(MigrationError, match="not a readable pen store"):
        open_store(root)


def test_blob_containing_a_json_scalar_is_reported(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "pen").write_bytes(zlib.compress(json.dumps("just a string").encode()))

    with pytest.raises(MigrationError, match="does not contain a pen store"):
        open_store(root)


def test_no_legacy_blob_is_a_no_op(root: Path) -> None:
    root.mkdir(parents=True)
    assert NoteStore(root).migrate_legacy() is None


def test_a_list_named_pen_can_exist_after_migration(root: Path) -> None:
    """The blob's own filename is 'pen'; it must not block that list name."""
    root.mkdir(parents=True)
    (root / "pen").write_bytes(make_legacy_blob({"work": {"todo": "x"}}))

    store = open_store(root)
    store.create_list("pen")

    assert "pen" in store.lists()


# -- imported names must survive their own validation --------------------


def test_a_legacy_list_named_after_a_command_is_renamed(root: Path) -> None:
    """Imported as `all`, the store became permanently unreadable."""
    root.mkdir(parents=True)
    (root / "pen").write_bytes(make_legacy_blob({"all": {"a": "x"}}))

    store = open_store(root)

    assert store.lists() == ["all-1"]
    assert store.read_note("all-1", "a").body == "x"


def test_a_legacy_name_reserved_on_windows_is_renamed(root: Path) -> None:
    """The device-name rule reads the text before the first dot."""
    root.mkdir(parents=True)
    (root / "pen").write_bytes(make_legacy_blob({"work": {"con.txt": "x"}}))

    assert open_store(root).note_names("work") == ["con-1.txt"]


def test_names_that_sanitize_onto_each_other_do_not_merge(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "pen").write_bytes(
        make_legacy_blob({"a/b": {"n": "first"}, "a-b": {"n": "second"}})
    )

    store = open_store(root)

    assert store.lists() == ["a-b", "a-b-1"]
    bodies = {name: store.read_note(name, "n").body for name in store.lists()}
    assert sorted(bodies.values()) == ["first", "second"]


def test_an_overlong_legacy_name_leaves_room_for_its_suffix(root: Path) -> None:
    root.mkdir(parents=True)
    long = "x" * 400
    (root / "pen").write_bytes(make_legacy_blob({long: {"n": "a"}, long + "y": {}}))

    names = open_store(root).lists()
    assert all(len(name) <= MAX_NAME_LENGTH for name in names)
    assert len(names) == 2


def test_every_imported_name_is_one_pen_would_accept(root: Path) -> None:
    root.mkdir(parents=True)
    hostile = {
        "all": {"open": "a"},
        "..": {".": "b"},
        "con": {"lpt1.md": "c"},
        "   ": {"": "d"},
        "a\x00b": {"e/f": "e"},
    }
    (root / "pen").write_bytes(make_legacy_blob(hostile))

    store = open_store(root)

    for list_name in store.lists():
        validate_list_name(list_name)
        for note_name in store.note_names(list_name):
            validate_note_name(note_name)
    assert store.scan_lists()[1] == []


# -- nothing is moved before it is understood ----------------------------


def test_a_root_pointing_at_a_file_that_is_not_a_store_is_left_alone(
    root: Path,
) -> None:
    root.parent.mkdir(parents=True, exist_ok=True)
    root.write_text("a file that has nothing to do with pen\n")

    with pytest.raises(MigrationError, match="not a readable pen store"):
        open_store(root)

    assert root.is_file()
    assert root.read_text() == "a file that has nothing to do with pen\n"


def test_a_second_migration_never_overwrites_the_first_backup(
    root: Path, legacy_blob: bytes
) -> None:
    """The README promises the original is kept. Twice means two backups."""
    root.mkdir(parents=True)
    (root / "pen").write_bytes(legacy_blob)
    open_store(root)

    (root / "pen").write_bytes(make_legacy_blob({"later": {"n": "x"}}))
    open_store(root)

    assert (root / "pen.bak").read_bytes() == legacy_blob
    assert (root / "pen.bak.2").exists()


def test_a_second_migration_does_not_overwrite_edited_notes(root: Path) -> None:
    """The .bak naming supports a re-run, so a re-run must not clobber edits."""
    root.mkdir(parents=True)
    (root / "pen").write_bytes(make_legacy_blob({"work": {"todo": "legacy body"}}))
    store = open_store(root)
    store.write_note("work", "todo", "edited since migrating")

    (root / "pen").write_bytes(make_legacy_blob({"work": {"todo": "legacy body"}}))
    store = open_store(root)

    assert store.read_note("work", "todo").body == "edited since migrating"
    assert store.read_note("work", "todo-1").body == "legacy body"


def test_clean_trims_after_truncating_not_before() -> None:
    """Trimming first lets truncation put a dot back on the end.

    Asserted on the helper because the name then fails validation forever and
    _sanitize spins rather than returning something wrong.
    """
    cleaned = _clean("a" * (MAX_NAME_LENGTH - 9) + ".x")

    assert not cleaned.endswith((".", " "))
    assert cleaned == cleaned.strip()
