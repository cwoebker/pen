"""Every subcommand through the runner, asserting exit codes on both paths.

Exit codes are the point of this file: a command that prints an error and
returns 0 is a bug, and only an assertion catches it.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import click
import pytest

from pen import config, frontmatter
from pen.cli import cli, get_store
from pen.storage import NoteStore, open_store

from .conftest import Result, ago, make_legacy_blob

Run = Callable[..., Result]


# -- top level ----------------------------------------------------------


def test_bare_invocation_lists_lists(run: Run, store: NoteStore) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "x")
    result = run()
    assert result.exit_code == 0
    assert "work" in result.stdout
    assert "(1)" in result.stdout


def test_bare_invocation_on_an_empty_store(run: Run, root: Path) -> None:
    result = run()
    assert result.exit_code == 0
    assert "no lists yet" in result.stdout


def test_help_exits_zero(run: Run, root: Path) -> None:
    result = run("--help")
    assert result.exit_code == 0
    assert "terminal notes" in result.stdout


def test_help_documents_the_bare_list_and_note_form(run: Run, root: Path) -> None:
    """It is the headline feature and click cannot infer it from the group."""
    result = run("--help")

    assert "pen <list> <note>" in result.stdout
    assert "<list> [<note>]" in result.stdout, "the usage line should show it too"


def test_version_exits_zero(run: Run, root: Path) -> None:
    result = run("--version")
    assert result.exit_code == 0
    assert "pen, version" in result.stdout


def test_path_override_flag(run: Run, tmp_path: Path) -> None:
    elsewhere = tmp_path / "one-off"
    result = run("--path", str(elsewhere), "create", "work")
    assert result.exit_code == 0
    assert (elsewhere / "work").is_dir()


# -- list / all ---------------------------------------------------------


def test_list_command(run: Run, store: NoteStore) -> None:
    store.create_list("work")
    store.create_list("ideas")
    result = run("list")
    assert result.exit_code == 0
    assert result.stdout.index("ideas") < result.stdout.index("work")


def test_all_shows_notes_under_each_list(run: Run, store: NoteStore) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "x")
    result = run("all")
    assert result.exit_code == 0
    assert "work" in result.stdout
    assert "todo" in result.stdout


def test_all_marks_empty_lists(run: Run, store: NoteStore) -> None:
    store.create_list("work")
    result = run("all")
    assert result.exit_code == 0
    assert "empty" in result.stdout


def test_all_on_an_empty_store(run: Run, root: Path) -> None:
    result = run("all")
    assert result.exit_code == 0
    assert "no lists yet" in result.stdout


def test_all_shows_relative_ages(run: Run, store: NoteStore) -> None:
    """Built from a relative timestamp so this cannot rot on a given date."""
    store.create_list("work")
    store.write_note("work", "todo", "x")
    _backdate(store.root / "work" / "todo.md", ago(days=3))

    result = run("all")

    assert "3d ago" in result.stdout


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        ({"seconds": 5}, "just now"),
        ({"minutes": 5}, "5m ago"),
        ({"hours": 5}, "5h ago"),
        ({"days": 5}, "5d ago"),
        ({"days": 400}, "400d ago"),
    ],
)
def test_age_rendering(
    run: Run, store: NoteStore, delta: dict[str, int], expected: str
) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "x")
    _backdate(store.root / "work" / "todo.md", ago(**delta))
    assert expected in run("all").stdout


# -- create -------------------------------------------------------------


def test_create(run: Run, root: Path) -> None:
    result = run("create", "work")
    assert result.exit_code == 0
    assert (root / "work").is_dir()


def test_create_duplicate_fails(run: Run, store: NoteStore) -> None:
    store.create_list("work")
    result = run("create", "work")
    assert result.exit_code == 1
    assert "already exists" in result.stderr


def test_create_reserved_name_fails(run: Run, root: Path) -> None:
    """A list named after a command would be unreachable, so it is refused."""
    result = run("create", "all")
    assert result.exit_code == 1
    assert "pen command" in result.stderr
    assert not (root / "all").exists()


def test_create_traversal_fails(run: Run, root: Path) -> None:
    result = run("create", "../escape")
    assert result.exit_code == 1
    assert not (root.parent / "escape").exists()


def test_create_without_a_name_fails(run: Run, root: Path) -> None:
    result = run("create")
    assert result.exit_code == 2  # click usage error


# -- open ---------------------------------------------------------------


def test_bare_list_name_shows_its_notes(run: Run, store: NoteStore) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "x")
    result = run("work")
    assert result.exit_code == 0
    assert "todo" in result.stdout


def test_bare_list_name_when_empty(run: Run, store: NoteStore) -> None:
    store.create_list("work")
    result = run("work")
    assert result.exit_code == 0
    assert "is empty" in result.stdout


def test_unknown_list_fails(run: Run, root: Path) -> None:
    result = run("nosuchlist")
    assert result.exit_code == 1
    assert "no such list" in result.stderr


def test_opening_a_new_note_creates_it(
    run: Run, store: NoteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    store.create_list("work")
    monkeypatch.setattr("pen.cli.edit_text", lambda text, title: "written")

    result = run("work", "todo")

    assert result.exit_code == 0
    assert "created" in result.stdout
    assert store.read_note("work", "todo").body == "written"


def test_opening_an_existing_note_updates_it(
    run: Run, store: NoteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "before")
    monkeypatch.setattr("pen.cli.edit_text", lambda text, title: text + " after")

    result = run("work", "todo")

    assert result.exit_code == 0
    assert "updated" in result.stdout
    assert store.read_note("work", "todo").body == "before after"


def test_unchanged_edit_is_reported_as_such(
    run: Run, store: NoteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "same")
    monkeypatch.setattr("pen.cli.edit_text", lambda text, title: text)

    result = run("work", "todo")

    assert result.exit_code == 0
    assert "unchanged" in result.stdout


def test_explicit_open_command(
    run: Run, store: NoteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    store.create_list("work")
    monkeypatch.setattr("pen.cli.edit_text", lambda text, title: "x")
    assert run("open", "work", "todo").exit_code == 0


def test_open_in_a_missing_list_fails(
    run: Run, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("pen.cli.edit_text", lambda text, title: "x")
    result = run("ghost", "todo")
    assert result.exit_code == 1
    assert "no such list" in result.stderr


def test_external_editor(
    run: Run, store: NoteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    store.create_list("work")
    monkeypatch.setattr("pen.cli.click.edit", lambda text, extension: "from $EDITOR")

    result = run("work", "todo", "--external")

    assert result.exit_code == 0
    assert store.read_note("work", "todo").body == "from $EDITOR"


def test_external_editor_left_unmodified(
    run: Run, store: NoteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """click.edit returns None when the user saved nothing."""
    store.create_list("work")
    monkeypatch.setattr("pen.cli.click.edit", lambda text, extension: None)

    result = run("work", "todo", "--external")

    assert result.exit_code == 0
    assert "unchanged" in result.stdout
    assert not store.has_note("work", "todo")


def test_builtin_flag_uses_the_builtin_editor(
    run: Run, store: NoteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    store.create_list("work")
    monkeypatch.setattr("pen.cli.edit_text", lambda text, title: "builtin")
    monkeypatch.setattr(
        "pen.cli.click.edit",
        lambda *a, **k: pytest.fail("should not use the external editor"),
    )
    assert run("work", "todo", "--builtin").exit_code == 0
    assert store.read_note("work", "todo").body == "builtin"


# -- show ---------------------------------------------------------------


def test_show(run: Run, store: NoteStore) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "buy milk")
    result = run("show", "work", "todo")
    assert result.exit_code == 0
    assert "buy milk" in result.stdout
    assert "created" in result.stdout
    assert "modified" in result.stdout


def test_show_includes_foreign_frontmatter_keys(run: Run, store: NoteStore) -> None:
    store.create_list("work")
    (store.root / "work" / "todo.md").write_text(
        "---\ntags: important\n---\n\nbody\n", encoding="utf-8"
    )
    result = run("show", "work", "todo")
    assert "tags" in result.stdout
    assert "important" in result.stdout


def test_show_empty_note(run: Run, store: NoteStore) -> None:
    store.create_list("work")
    store.write_note("work", "blank", "")
    result = run("show", "work", "blank")
    assert result.exit_code == 0
    assert "(empty)" in result.stdout


def test_show_missing_note_fails(run: Run, store: NoteStore) -> None:
    store.create_list("work")
    result = run("show", "work", "ghost")
    assert result.exit_code == 1
    assert "no such note" in result.stderr


def test_show_missing_list_fails(run: Run, root: Path) -> None:
    result = run("show", "ghost", "todo")
    assert result.exit_code == 1
    assert "no such list" in result.stderr


# -- delete -------------------------------------------------------------


def test_delete_note(run: Run, store: NoteStore) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "x")
    result = run("delete", "work", "todo")
    assert result.exit_code == 0
    assert not store.has_note("work", "todo")


def test_delete_missing_note_fails(run: Run, store: NoteStore) -> None:
    store.create_list("work")
    result = run("delete", "work", "ghost")
    assert result.exit_code == 1
    assert "no such note" in result.stderr


def test_delete_missing_list_fails(run: Run, root: Path) -> None:
    result = run("delete", "ghost")
    assert result.exit_code == 1
    assert "no such list" in result.stderr


def test_delete_empty_list_needs_no_confirmation(run: Run, store: NoteStore) -> None:
    store.create_list("work")
    result = run("delete", "work")
    assert result.exit_code == 0
    assert not (store.root / "work").exists()


def test_delete_non_empty_list_prompts(run: Run, store: NoteStore) -> None:
    """Deleting a non-empty list must confirm before destroying anything."""
    store.create_list("work")
    store.write_note("work", "todo", "x")

    result = run("delete", "work", input="y\n")

    assert result.exit_code == 0
    assert "1 note(s)" in result.stdout
    assert not (store.root / "work").exists()


def test_declining_the_prompt_aborts_non_zero(run: Run, store: NoteStore) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "x")

    result = run("delete", "work", input="n\n")

    assert result.exit_code == 1
    assert "aborted" in result.output
    assert (store.root / "work").is_dir(), "the list must survive an abort"


def test_yes_flag_skips_the_prompt(run: Run, store: NoteStore) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "x")
    result = run("delete", "work", "--yes")
    assert result.exit_code == 0
    assert not (store.root / "work").exists()


# -- path ---------------------------------------------------------------


def test_path_prints_the_current_root(run: Run, root: Path) -> None:
    result = run("path")
    assert result.exit_code == 0
    assert str(root) in result.stdout


def test_path_sets_a_new_root(
    run: Run, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PEN_PATH", raising=False)
    target = tmp_path / "dropbox" / "pen"

    result = run("path", str(target))

    assert result.exit_code == 0
    assert target.is_dir()
    assert config.resolve_root() == target


def test_path_default_resets(
    run: Run, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PEN_PATH", raising=False)
    config.set_root(tmp_path / "elsewhere")

    result = run("path", "default")

    assert result.exit_code == 0
    assert config.resolve_root() == config.default_root()


def test_path_reports_the_env_override(
    run: Run, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PEN_PATH", str(tmp_path / "forced"))
    assert str(tmp_path / "forced") in run("path").stdout


# -- migration through the CLI -----------------------------------------


def test_legacy_store_is_migrated_on_first_command(run: Run, root: Path) -> None:
    root.mkdir(parents=True)
    (root / "pen").write_bytes(make_legacy_blob({"work": {"todo": "buy milk"}}))

    result = run("all")

    assert result.exit_code == 0
    assert "todo" in result.stdout
    assert (root / "pen.bak").is_file()


def test_corrupt_legacy_store_fails_loudly(run: Run, root: Path) -> None:
    root.mkdir(parents=True)
    (root / "pen").write_bytes(b"not zlib at all")

    result = run("all")

    assert result.exit_code == 1
    assert "not a readable pen store" in result.stderr


def _backdate(path: Path, moment: datetime) -> None:
    document = frontmatter.parse(path.read_text(encoding="utf-8"))
    metadata = dict(document.metadata)
    metadata["modified"] = moment.isoformat()
    path.write_text(frontmatter.render(metadata, document.body), encoding="utf-8")


def test_store_fixture_is_never_the_real_one(store: NoteStore, tmp_path: Path) -> None:
    """Guard against a future fixture change leaking onto a real machine."""
    assert tmp_path in store.root.parents or store.root == tmp_path / "store"
    assert open_store(store.root).root == store.root


def test_future_timestamp_reads_as_just_now(run: Run, store: NoteStore) -> None:
    """A synced store can carry a stamp ahead of this machine's clock."""
    store.create_list("work")
    store.write_note("work", "todo", "x")
    _backdate(store.root / "work" / "todo.md", ago(days=-2))
    assert "just now" in run("all").stdout


# -- names are data, not markup ------------------------------------------


@pytest.mark.parametrize("name", ["[x]", "[bold]hi", "a[b]c", "[dim]"])
def test_a_name_that_looks_like_markup_is_shown_literally(
    run: Callable[..., Result], name: str
) -> None:
    """Unescaped, these vanished from every listing rich rendered."""
    created = run("create", name)
    assert created.exit_code == 0
    assert name in created.output

    listed = run("list")
    assert listed.exit_code == 0
    assert name in listed.output


def test_markup_in_a_rejected_name_fails_cleanly(run: Callable[..., Result]) -> None:
    """This aborted with an unhandled MarkupError from the error handler."""
    rejected = run("create", "[/bold]x")

    assert rejected.exit_code == 1
    assert "[/bold]x" in rejected.stderr


def test_markup_in_an_existing_name_fails_cleanly(run: Callable[..., Result]) -> None:
    assert run("create", "[dim]x").exit_code == 0
    duplicate = run("create", "[dim]x")

    assert duplicate.exit_code == 1
    assert "already exists" in duplicate.stderr
    assert "[dim]x" in duplicate.stderr


def test_markup_in_a_note_name_and_metadata_is_shown_literally(
    run: Callable[..., Result], store: NoteStore, root: Path
) -> None:
    store.create_list("work")
    (root / "work" / "[note].md").write_text("---\n[k]: '[v]'\n---\n\nbody\n")

    shown = run("show", "work", "[note]")

    assert shown.exit_code == 0
    assert "[note]" in shown.output
    assert "[k]" in shown.output and "[v]" in shown.output


# -- `pen path` stays usable when the store does not ---------------------


def test_path_is_not_persisted_when_the_store_cannot_be_opened(
    run: Callable[..., Result], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PEN_PATH", raising=False)
    blocker = tmp_path / "a-file"
    blocker.write_text("x")

    failed = run("path", str(blocker / "store"))

    assert failed.exit_code == 1
    # The bad path must not have been recorded, or every later command,
    # `pen path` included, would start by failing on it.
    assert run("path").exit_code == 0
    assert str(blocker) not in run("path").stdout


def test_path_can_recover_from_a_configured_root_that_cannot_be_created(
    run: Callable[..., Result], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PEN_PATH", raising=False)
    blocker = tmp_path / "a-file"
    blocker.write_text("x")
    config.set_root(blocker / "store")

    assert run("list").exit_code == 1
    assert run("path").exit_code == 0, "reading the location must not open it"
    assert run("path", "default").exit_code == 0
    assert run("list").exit_code == 0


def test_a_relative_path_is_anchored_when_it_is_stored(
    run: Callable[..., Result], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stored relative, the store moved with the shell's directory."""
    monkeypatch.delenv("PEN_PATH", raising=False)
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    assert run("path", "notes").exit_code == 0
    assert run("create", "here").exit_code == 0

    monkeypatch.chdir(tmp_path)
    assert "here" in run("list").stdout
    assert str(workdir / "notes") == run("path").stdout.strip()


# -- unusable entries are reported, not fatal ----------------------------


def test_a_directory_pen_cannot_use_is_reported_rather_than_fatal(
    run: Callable[..., Result], store: NoteStore, root: Path
) -> None:
    store.create_list("work")
    (root / "all").mkdir()

    listed = run("list")

    assert listed.exit_code == 0
    assert "work" in listed.stdout
    assert "ignoring 1 unusable list(s): all" in listed.stdout


def test_a_file_pen_cannot_name_does_not_break_listing(
    run: Callable[..., Result], store: NoteStore, root: Path
) -> None:
    store.create_list("work")
    store.write_note("work", "todo", "buy milk")
    (root / "work" / "meeting notes .md").write_text("hi\n")

    assert run("all").exit_code == 0
    listed = run("work")
    assert listed.exit_code == 0
    assert "todo" in listed.stdout
    assert "ignoring 1 unusable note(s)" in listed.stdout


def test_the_store_is_opened_once_per_invocation() -> None:
    """Commands that never need the store must never open it."""
    sentinel = object()
    ctx = click.Context(cli)
    # A root that could never be opened: reaching for it would raise.
    ctx.obj = {"store": sentinel, "root": Path("/nowhere/at/all")}

    assert get_store(ctx) is sentinel


def test_deleting_a_list_of_unnameable_notes_still_prompts(
    run: Run, store: NoteStore, root: Path
) -> None:
    """Counting only usable names skipped the prompt and deleted them anyway."""
    store.create_list("work")
    (root / "work" / "meeting notes .md").write_text("real content\n")

    aborted = run("delete", "work", input="n\n")

    assert aborted.exit_code == 1
    assert "2 note(s)" not in aborted.output
    assert "1 note(s)" in aborted.output
    assert (root / "work" / "meeting notes .md").is_file()


@pytest.mark.parametrize("name", ["Notes [old]", "x[/x]y"])
def test_a_store_path_containing_markup_survives_being_printed(
    run: Run, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """`pen path` printed the root unescaped, which broke it permanently."""
    monkeypatch.delenv("PEN_PATH", raising=False)
    target = tmp_path / name

    assert run("path", str(target)).exit_code == 0

    shown = run("path")
    assert shown.exit_code == 0
    assert name in shown.stdout
