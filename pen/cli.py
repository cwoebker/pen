"""The command line interface.

Not stock click:

* ``pen <list> [<note>]`` opens a note without naming a subcommand, via
  :class:`PenGroup`. Names that would shadow a command are refused at creation.
* :func:`main` runs click with ``standalone_mode=False`` so it can map
  :class:`~pen.errors.PenError` onto an exit code itself.

Everything user-supplied reaching the console goes through :func:`escape` --
names and store paths alike. rich reads ``[...]`` as markup, so an unescaped
one either vanishes from the output or aborts with a ``MarkupError``.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.markup import escape
from rich.table import Table
from rich.text import Text

from . import __version__, config
from .editor import edit_text
from .errors import NoteNotFoundError, PenError
from .models import WriteOutcome
from .storage import NoteStore, open_store

console = Console()
error_console = Console(stderr=True)


class PenGroup(click.Group):
    """A group that routes unknown first arguments to ``open``."""

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        if args and args[0] not in self.commands and not args[0].startswith("-"):
            open_command = self.commands["open"]
            return open_command.name, open_command, args
        return super().resolve_command(ctx, args)


def get_store(ctx: click.Context) -> NoteStore:
    """Open the store on first use, so `pen path` survives an unopenable root."""
    store = ctx.obj["store"]
    if store is None:
        store = ctx.obj["store"] = open_store(ctx.obj["root"])
    return store


def _report_ignored(kind: str, names: list[str]) -> None:
    if names:
        listed = ", ".join(escape(name) for name in names)
        console.print(f"[dim]ignoring {len(names)} unusable {kind}: {listed}[/dim]")


def _humanize(moment: datetime) -> str:
    """Render a timestamp as a compact age, e.g. ``3d`` or ``just now``."""
    seconds = int((datetime.now(UTC) - moment).total_seconds())
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size:
            return f"{seconds // size}{unit} ago"
    return "just now"  # negative deltas land here too


@click.group(
    cls=PenGroup,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    subcommand_metavar="[COMMAND | <list> [<note>]] [ARGS]...",
)
@click.version_option(__version__, "-v", "--version", prog_name="pen")
@click.option(
    "--path",
    "root_override",
    type=click.Path(file_okay=False, path_type=Path),
    help="Use this store for one invocation instead of the configured one.",
)
@click.pass_context
def cli(ctx: click.Context, root_override: Path | None) -> None:
    """pen: terminal notes.

    A list or note can be named directly, without a command:

    \b
      pen                list every list, with note counts
      pen <list>         list the notes in one list
      pen <list> <note>  open a note in the editor, creating it if new
    """
    root = root_override or config.resolve_root()
    ctx.obj = {"store": None, "root": root}
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_lists)


@cli.command("list")
@click.pass_context
def list_lists(ctx: click.Context) -> None:
    """List every list with its note count."""
    store = get_store(ctx)
    names, ignored = store.scan_lists()
    if not names:
        console.print("[dim]no lists yet - try [/dim]pen create <list>")
    for name in names:
        count = len(store.note_names(name))
        console.print(f"{escape(name)} [dim]({count})[/dim]")
    _report_ignored("list(s)", ignored)


@cli.command("all")
@click.pass_context
def list_all(ctx: click.Context) -> None:
    """List every note in every list."""
    store = get_store(ctx)
    names = store.lists()
    if not names:
        console.print("[dim]no lists yet - try [/dim]pen create <list>")
        return
    for name in names:
        console.print(f"[bold]{escape(name)}[/bold]")
        notes = list(store.iter_notes(name))
        if not notes:
            console.print("  [dim]- empty[/dim]")
        for note in notes:
            console.print(
                f"  [dim]-[/dim] {escape(note.name)} "
                f"[dim]{_humanize(note.modified)}[/dim]"
            )


@cli.command("create")
@click.argument("name")
@click.pass_context
def create_list(ctx: click.Context, name: str) -> None:
    """Create a list."""
    store = get_store(ctx)
    store.create_list(name)
    console.print(f"created list [bold]{escape(name)}[/bold]")


@cli.command("open")
@click.argument("list_name", metavar="<list>")
@click.argument("note_name", metavar="[<note>]", required=False)
@click.option(
    "--external/--builtin",
    default=False,
    help="Edit in $VISUAL/$EDITOR instead of the built-in editor.",
)
@click.pass_context
def open_note(
    ctx: click.Context,
    list_name: str,
    note_name: str | None,
    external: bool,
) -> None:
    """Show a list, or open one of its notes for editing.

    This is the command `pen <list> [<note>]` runs.
    """
    store = get_store(ctx)
    if note_name is None:
        names, ignored = store.scan_notes(list_name)
        if not names:
            console.print(f"[dim]{escape(list_name)} is empty[/dim]")
        for name in names:
            console.print(escape(name))
        _report_ignored("note(s)", ignored)
        return

    store.require_list(list_name)
    try:
        original = store.read_note(list_name, note_name).body
    except NoteNotFoundError:
        original = ""

    title = f"{list_name}/{note_name}"
    if external:
        edited = click.edit(original, extension=".md")
        if edited is None:
            console.print("[dim]unchanged[/dim]")
            return
    else:
        edited = edit_text(original, title=title)

    outcome = store.write_note(list_name, note_name, edited)
    _report(outcome, title)


def _report(outcome: WriteOutcome, title: str) -> None:
    if outcome is WriteOutcome.UNCHANGED:
        console.print(f"[dim]{escape(title)} unchanged[/dim]")
    else:
        console.print(f"{outcome.value} [bold]{escape(title)}[/bold]")


@cli.command("show")
@click.argument("list_name", metavar="<list>")
@click.argument("note_name", metavar="<note>")
@click.pass_context
def show_note(ctx: click.Context, list_name: str, note_name: str) -> None:
    """Print a note and its metadata."""
    store = get_store(ctx)
    note = store.read_note(list_name, note_name)
    table = Table.grid(padding=(0, 2))
    table.add_row("[dim]created[/dim]", note.created.isoformat())
    table.add_row("[dim]modified[/dim]", note.modified.isoformat())
    for key, value in note.extra.items():
        table.add_row(f"[dim]{escape(key)}[/dim]", escape(str(value)))
    console.print(f"[bold]{escape(note.title)}[/bold]")
    console.print(table)
    if note.is_empty:
        console.print("[dim](empty)[/dim]")
    else:
        console.print(Text(note.body))


@cli.command("delete")
@click.argument("list_name", metavar="<list>")
@click.argument("note_name", metavar="[<note>]", required=False)
@click.option("-y", "--yes", is_flag=True, help="Do not prompt for confirmation.")
@click.pass_context
def delete(
    ctx: click.Context, list_name: str, note_name: str | None, yes: bool
) -> None:
    """Delete a list and all of its notes, or a single note."""
    store = get_store(ctx)
    if note_name is not None:
        store.delete_note(list_name, note_name)
        console.print(f"deleted [bold]{escape(f'{list_name}/{note_name}')}[/bold]")
        return

    store.require_list(list_name)
    # Every note file delete_list will remove, not just the nameable ones.
    usable, ignored = store.scan_notes(list_name)
    count = len(usable) + len(ignored)
    if count and not yes:
        click.confirm(f"delete list {list_name!r} and its {count} note(s)?", abort=True)
    removed = store.delete_list(list_name)
    console.print(f"deleted list [bold]{escape(list_name)}[/bold] ({removed} note(s))")


@cli.command("path")
@click.argument("new_path", metavar="[<path>|default]", required=False)
@click.pass_context
def path_command(ctx: click.Context, new_path: str | None) -> None:
    """Print the store location, or point pen at a different one."""
    if new_path is None:
        console.print(escape(str(ctx.obj["root"])))
        return

    # Open before recording.
    if new_path == "default":
        root = config.default_root()
        open_store(root)
        config.reset_root()
    else:
        root = config.absolute(Path(new_path))
        open_store(root)
        config.set_root(root)
    console.print(escape(str(root)))


def main(argv: list[str] | None = None, **kwargs: Any) -> int:
    """Entry point. Maps domain errors onto a non-zero exit code."""
    try:
        return (
            cli.main(args=argv, prog_name="pen", standalone_mode=False, **kwargs) or 0
        )
    except PenError as error:
        error_console.print(f"[red]error:[/red] {escape(str(error))}")
        return 1
    except click.Abort:
        error_console.print("[dim]aborted[/dim]")
        return 1
    except click.ClickException as error:
        error.show()
        return error.exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
