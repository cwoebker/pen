"""The note store."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pen import frontmatter
from pen.errors import (
    InvalidNameError,
    ListExistsError,
    ListNotFoundError,
    NoteNotFoundError,
    ReservedNameError,
    StorageError,
)
from pen.models import WriteOutcome
from pen.storage import NoteStore, open_store

from .conftest import ago


def test_empty_store_has_no_lists(store: NoteStore) -> None:
    assert store.lists() == []


def test_create_and_list(store: NoteStore) -> None:
    store.create_list("work")
    store.create_list("Personal")
    # Sorted case-insensitively so 'Personal' does not jump ahead of 'work'.
    assert store.lists() == ["Personal", "work"]
    assert (store.root / "work").is_dir()


def test_create_duplicate_list(store: NoteStore) -> None:
    store.create_list("work")
    with pytest.raises(ListExistsError):
        store.create_list("work")


def test_create_reserved_list(store: NoteStore) -> None:
    with pytest.raises(ReservedNameError):
        store.create_list("all")


def test_hidden_directories_are_not_lists(store: NoteStore) -> None:
    (store.root / ".git").mkdir()
    (store.root / ".obsidian").mkdir()
    assert store.lists() == []


def test_stray_files_in_the_root_are_not_lists(store: NoteStore) -> None:
    (store.root / "README.md").write_text("hi", encoding="utf-8")
    assert store.lists() == []


def test_require_missing_list(store: NoteStore) -> None:
    with pytest.raises(ListNotFoundError, match="no such list: ghost"):
        store.require_list("ghost")


def test_write_then_read(store: NoteStore) -> None:
    store.create_list("work")
    assert store.write_note("work", "todo", "buy milk") is WriteOutcome.CREATED

    note = store.read_note("work", "todo")
    assert note.body == "buy milk"
    assert note.list_name == "work"
    assert note.name == "todo"
    assert note.title == "work/todo"
    assert not note.is_empty


def test_written_file_is_markdown_with_frontmatter(store: NoteStore) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "buy milk")
    text = (store.root / "work" / "todo.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert text.endswith("buy milk\n")
    document = frontmatter.parse(text)
    assert set(document.metadata) == {"created", "modified"}


def test_timestamps_are_timezone_aware_utc(store: NoteStore) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "x")
    note = store.read_note("work", "todo")
    assert note.created.tzinfo is not None
    assert note.created.utcoffset() == UTC.utcoffset(None)
    assert ago(seconds=30) <= note.created <= datetime.now(UTC)


def test_update_preserves_created_and_bumps_modified(store: NoteStore) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "first")
    original = store.read_note("work", "todo")

    # Backdate on disk so the bump is observable without sleeping.
    _backdate(
        store.root / "work" / "todo.md", created=ago(days=3), modified=ago(days=3)
    )

    assert store.write_note("work", "todo", "second") is WriteOutcome.UPDATED
    updated = store.read_note("work", "todo")
    assert updated.body == "second"
    assert updated.created == ago(days=3)
    assert updated.modified > updated.created
    assert updated.created < original.modified


def test_unchanged_write_is_a_no_op(store: NoteStore) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "same")
    path = store.root / "work" / "todo.md"
    before = path.read_bytes()

    assert store.write_note("work", "todo", "same") is WriteOutcome.UNCHANGED
    assert path.read_bytes() == before, "an unchanged write must not touch the file"


@pytest.mark.parametrize("body", ["same", "same\n", "same\n\n\n"])
def test_trailing_newlines_do_not_count_as_a_change(
    store: NoteStore, body: str
) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "same")
    assert store.write_note("work", "todo", body) is WriteOutcome.UNCHANGED


def test_unknown_frontmatter_keys_round_trip(store: NoteStore) -> None:
    """Obsidian's `tags:` must survive a pen write."""
    store.create_list("work")
    path = store.root / "work" / "todo.md"
    path.write_text(
        "---\n"
        "created: 2020-01-01T00:00:00+00:00\n"
        "modified: 2020-01-01T00:00:00+00:00\n"
        "tags: obsidian, important\n"
        "aliases: my-note\n"
        "---\n\noriginal\n",
        encoding="utf-8",
    )

    store.write_note("work", "todo", "rewritten")
    note = store.read_note("work", "todo")
    assert note.extra == {"tags": "obsidian, important", "aliases": "my-note"}
    assert note.created == datetime(2020, 1, 1, tzinfo=UTC)
    assert "tags: obsidian, important" in path.read_text(encoding="utf-8")


def test_plain_markdown_file_is_adopted(store: NoteStore) -> None:
    """Dropping a file in from another tool just works."""
    store.create_list("work")
    path = store.root / "work" / "dropped.md"
    path.write_text("no frontmatter here\n", encoding="utf-8")

    assert store.note_names("work") == ["dropped"]
    note = store.read_note("work", "dropped")
    assert note.body == "no frontmatter here"
    assert note.extra == {}
    # Timestamps fall back to the file's mtime, the only honest signal.
    assert note.created == note.modified


def test_naive_timestamps_are_read_as_utc(store: NoteStore) -> None:
    store.create_list("work")
    (store.root / "work" / "todo.md").write_text(
        "---\ncreated: 2020-01-01T12:00:00\nmodified: 2020-01-01T12:00:00\n---\n\nx\n",
        encoding="utf-8",
    )
    note = store.read_note("work", "todo")
    assert note.created == datetime(2020, 1, 1, 12, tzinfo=UTC)


def test_offset_timestamps_are_normalized_to_utc(store: NoteStore) -> None:
    store.create_list("work")
    (store.root / "work" / "todo.md").write_text(
        "---\ncreated: 2020-01-01T12:00:00+02:00\n---\n\nx\n", encoding="utf-8"
    )
    assert store.read_note("work", "todo").created == datetime(
        2020, 1, 1, 10, tzinfo=UTC
    )


def test_unparseable_timestamp_falls_back_to_mtime(store: NoteStore) -> None:
    """A hand-edited stamp must not crash the tool."""
    store.create_list("work")
    (store.root / "work" / "todo.md").write_text(
        "---\ncreated: last tuesday\n---\n\nx\n", encoding="utf-8"
    )
    note = store.read_note("work", "todo")
    assert note.created.tzinfo is not None


def test_note_listing_ignores_non_markdown_and_hidden_files(store: NoteStore) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "x")
    (store.root / "work" / "notes.txt").write_text("x", encoding="utf-8")
    (store.root / "work" / ".hidden.md").write_text("x", encoding="utf-8")
    assert store.note_names("work") == ["todo"]


def test_read_missing_note(store: NoteStore) -> None:
    store.create_list("work")
    with pytest.raises(NoteNotFoundError, match="work/ghost"):
        store.read_note("work", "ghost")


def test_read_note_in_missing_list(store: NoteStore) -> None:
    with pytest.raises(ListNotFoundError):
        store.read_note("ghost", "todo")


def test_write_note_to_missing_list(store: NoteStore) -> None:
    with pytest.raises(ListNotFoundError):
        store.write_note("ghost", "todo", "x")


def test_delete_note(store: NoteStore) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "x")
    store.delete_note("work", "todo")
    assert store.note_names("work") == []
    with pytest.raises(NoteNotFoundError):
        store.delete_note("work", "todo")


def test_delete_list_reports_how_many_notes_went(store: NoteStore) -> None:
    store.create_list("work")
    for name in ("a", "b", "c"):
        store.write_note("work", name, "x")
    assert store.delete_list("work") == 3
    assert not (store.root / "work").exists()


def test_delete_empty_list(store: NoteStore) -> None:
    store.create_list("work")
    assert store.delete_list("work") == 0


def test_delete_missing_list(store: NoteStore) -> None:
    with pytest.raises(ListNotFoundError):
        store.delete_list("ghost")


def test_iter_notes_is_sorted(store: NoteStore) -> None:
    store.create_list("work")
    for name in ("zebra", "Apple", "mango"):
        store.write_note("work", name, name)
    assert [note.name for note in store.iter_notes("work")] == [
        "Apple",
        "mango",
        "zebra",
    ]


@pytest.mark.parametrize("name", ["../escape", "a/b", ".hidden", ""])
def test_invalid_names_never_reach_the_filesystem(store: NoteStore, name: str) -> None:
    store.create_list("work")
    with pytest.raises(InvalidNameError):
        store.write_note("work", name, "x")


def test_atomic_write_leaves_no_temp_file_behind(store: NoteStore) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "x")
    assert [p.name for p in (store.root / "work").iterdir()] == ["todo.md"]


def test_write_failure_is_reported_not_swallowed(
    store: NoteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    store.create_list("work")

    def explode(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", explode)
    with pytest.raises(StorageError, match="disk full"):
        store.write_note("work", "todo", "x")


def test_empty_note_is_flagged(store: NoteStore) -> None:
    store.create_list("work")
    store.write_note("work", "blank", "   \n\n")
    assert store.read_note("work", "blank").is_empty


def test_open_store_creates_the_root(tmp_path: Path) -> None:
    root = tmp_path / "deep" / "nested" / "store"
    open_store(root)
    assert root.is_dir()


def _backdate(path: Path, *, created: datetime, modified: datetime) -> None:
    document = frontmatter.parse(path.read_text(encoding="utf-8"))
    metadata = dict(document.metadata)
    metadata["created"] = created.isoformat()
    metadata["modified"] = modified.isoformat()
    path.write_text(frontmatter.render(metadata, document.body), encoding="utf-8")


# -- failure branches ---------------------------------------------------


def test_lists_on_a_root_that_does_not_exist(tmp_path: Path) -> None:
    assert NoteStore(tmp_path / "missing").lists() == []


def test_has_list_and_has_note(store: NoteStore) -> None:
    assert not store.has_list("work")
    store.create_list("work")
    assert store.has_list("work")
    assert not store.has_note("work", "todo")
    store.write_note("work", "todo", "x")
    assert store.has_note("work", "todo")


def test_ensure_root_failure_is_reported(
    store: NoteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "mkdir", _raiser(OSError("read-only file system")))
    with pytest.raises(StorageError, match="read-only file system"):
        store.ensure_root()


def test_create_list_failure_is_reported(
    store: NoteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "mkdir", _raiser(OSError("permission denied")))
    with pytest.raises(StorageError, match="permission denied"):
        store.create_list("work")


def test_create_list_losing_a_race_is_reported_as_exists(
    store: NoteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another process can win between the is_dir() check and mkdir()."""
    monkeypatch.setattr(Path, "mkdir", _raiser(FileExistsError()))
    with pytest.raises(ListExistsError):
        store.create_list("work")


def test_delete_list_failure_says_how_far_it_got(
    store: NoteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "x")
    monkeypatch.setattr(Path, "unlink", _raiser(OSError("busy")))
    with pytest.raises(StorageError, match="0 note\\(s\\) were removed"):
        store.delete_list("work")


def test_read_failure_is_reported(
    store: NoteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "x")
    monkeypatch.setattr(Path, "read_text", _raiser(OSError("I/O error")))
    with pytest.raises(StorageError, match="I/O error"):
        store.read_note("work", "todo")


def test_delete_note_failure_is_reported(
    store: NoteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "x")
    monkeypatch.setattr(Path, "unlink", _raiser(OSError("busy")))
    with pytest.raises(StorageError, match="busy"):
        store.delete_note("work", "todo")


def _raiser(error: Exception) -> object:
    def raise_it(*args: object, **kwargs: object) -> None:
        raise error

    return raise_it


# -- enumeration is defensive --------------------------------------------


def test_a_directory_pen_could_not_have_created_is_reported_not_raised(
    store: NoteStore, root: Path
) -> None:
    """A list named after a command used to make `pen list` fail forever."""
    store.create_list("work")
    (root / "all").mkdir()
    (root / "trailing ").mkdir()

    usable, ignored = store.scan_lists()
    assert usable == ["work"]
    assert ignored == ["all", "trailing "]


def test_a_dropped_in_file_pen_could_not_have_named_is_skipped(
    store: NoteStore, root: Path
) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "buy milk")
    (root / "work" / "meeting notes .md").write_text("hi\n")

    usable, ignored = store.scan_notes("work")
    assert usable == ["todo"]
    assert ignored == ["meeting notes .md"]
    # iter_notes must not trip over the file it just decided to skip.
    assert [note.name for note in store.iter_notes("work")] == ["todo"]


# -- delete_list is all or nothing ---------------------------------------


def test_delete_list_refuses_before_touching_anything(
    store: NoteStore, root: Path
) -> None:
    store.create_list("docs")
    store.write_note("docs", "keep", "important")
    (root / "docs" / "cover.png").write_bytes(b"\x89PNG")

    with pytest.raises(StorageError, match="Nothing was deleted"):
        store.delete_list("docs")

    assert (root / "docs" / "keep.md").is_file()


def test_delete_list_sweeps_sync_client_cruft(store: NoteStore, root: Path) -> None:
    store.create_list("docs")
    store.write_note("docs", "keep", "important")
    (root / "docs" / ".DS_Store").write_bytes(b"\x00")

    assert store.delete_list("docs") == 1
    assert not (root / "docs").exists()


def test_delete_list_refuses_on_a_subdirectory(store: NoteStore, root: Path) -> None:
    store.create_list("docs")
    (root / "docs" / "attachments").mkdir()

    with pytest.raises(StorageError, match="attachments"):
        store.delete_list("docs")


# -- writes stay stable --------------------------------------------------


def test_a_body_with_leading_blank_lines_does_not_churn(store: NoteStore) -> None:
    """It reported `updated` on every write and bumped `modified` forever."""
    store.create_list("work")
    assert store.write_note("work", "n", "\n\nhello") is WriteOutcome.CREATED
    assert store.write_note("work", "n", "\n\nhello") is WriteOutcome.UNCHANGED
    assert store.read_note("work", "n").body == "\n\nhello"


def test_frontmatter_pen_cannot_parse_survives_a_write(
    store: NoteStore, root: Path
) -> None:
    store.create_list("work")
    (root / "work" / "todo.md").write_text(
        "---\ntags:\n  - work\n  - urgent\n---\n\nbuy milk\n"
    )

    store.write_note("work", "todo", "buy bread")

    written = (root / "work" / "todo.md").read_text()
    assert "tags:\n  - work\n  - urgent" in written
    assert "buy bread" in written


def test_a_created_stamp_pen_cannot_read_falls_back(
    store: NoteStore, root: Path
) -> None:
    store.create_list("work")
    (root / "work" / "todo.md").write_text("---\ncreated:\n  - odd\n---\n\nbody\n")

    note = store.read_note("work", "todo")
    assert note.created.tzinfo is not None
    assert "created" not in note.extra


def test_delete_list_counts_and_removes_the_same_files(
    store: NoteStore, root: Path
) -> None:
    """The prompt count and the delete must not disagree about what a note is."""
    store.create_list("work")
    store.write_note("work", "todo", "x")
    (root / "work" / "meeting notes .md").write_text("real content\n")

    usable, ignored = store.scan_notes("work")
    assert len(usable) + len(ignored) == store.delete_list("work")


def test_a_note_pen_cannot_name_is_still_deleted_with_its_list(
    store: NoteStore, root: Path
) -> None:
    store.create_list("work")
    (root / "work" / "meeting notes .md").write_text("real content\n")

    assert store.delete_list("work") == 1
    assert not (root / "work").exists()
