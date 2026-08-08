"""The built-in urwid note editor.

Takes and returns a ``str`` and never touches the filesystem: the store owns
reading and writing, so no note is spilled to a temp directory and the editor
can be driven headlessly in tests.
"""

from __future__ import annotations

import urwid

PALETTE: list[tuple[str, str, str] | tuple[str, str, str, str]] = [
    ("body", "default", "default"),
    ("foot", "dark cyan", "dark blue", "bold"),
    ("key", "light cyan", "dark blue", "underline"),
]

#: urwid needs a size to route a synthetic keypress. Arbitrary for the two
#: navigation keys we send, but it has to be non-degenerate.
_SYNTHETIC_SIZE = (80, 24)


class Line(urwid.Edit):
    """One line of the note, displayed with its tabs expanded.

    urwid measures a tab as one column while the terminal expands it, so a raw
    tab desynchronises the cursor and every line after it. The unexpanded text
    is kept so an untouched line is written back as it was.
    """

    def __init__(self, line: str) -> None:
        super().__init__("", line.expandtabs(), allow_tab=True)
        self.source = line
        self.set_edit_pos(0)

    @property
    def value(self) -> str:
        """What to save: the original line unless it was actually edited."""
        if self.edit_text == self.source.expandtabs():
            return self.source
        return self.edit_text


class LineWalker(urwid.ListWalker):
    """One :class:`Line` per line of the note."""

    def __init__(self, text: str) -> None:
        lines = text.split("\n") or [""]
        self.lines: list[Line] = [Line(line) for line in lines]
        self.focus = 0

    def get_focus(self) -> tuple[Line | None, int | None]:
        return self._get_at_pos(self.focus)

    def set_focus(self, focus: int) -> None:
        self.focus = focus
        self._modified()

    def get_next(self, position: int) -> tuple[Line | None, int | None]:
        return self._get_at_pos(position + 1)

    def get_prev(self, position: int) -> tuple[Line | None, int | None]:
        return self._get_at_pos(position - 1)

    def _get_at_pos(self, pos: int) -> tuple[Line | None, int | None]:
        if pos < 0 or pos >= len(self.lines):
            return None, None
        return self.lines[pos], pos

    def split_focus(self) -> None:
        """Divide the focused edit widget at the cursor."""
        focus = self.lines[self.focus]
        pos = focus.edit_pos
        tail = Line(focus.edit_text[pos:])
        focus.set_edit_text(focus.edit_text[:pos])
        self.lines.insert(self.focus + 1, tail)

    def combine_focus_with_prev(self) -> None:
        """Join the focused line onto the one above."""
        if self.focus == 0:
            return
        above = self.lines[self.focus - 1]
        focus = self.lines[self.focus]
        above.set_edit_pos(len(above.edit_text))
        above.set_edit_text(above.edit_text + focus.edit_text)
        del self.lines[self.focus]
        self.focus -= 1

    def combine_focus_with_next(self) -> None:
        """Join the line below onto the focused one."""
        if self.focus + 1 >= len(self.lines):
            return
        below = self.lines[self.focus + 1]
        focus = self.lines[self.focus]
        focus.set_edit_text(focus.edit_text + below.edit_text)
        del self.lines[self.focus + 1]

    @property
    def text(self) -> str:
        return "\n".join(line.value for line in self.lines)


class EditDisplay:
    """The editor screen. ``esc`` saves and exits."""

    def __init__(self, text: str, title: str = "pen") -> None:
        self.walker = LineWalker(text)
        self.listbox = urwid.ListBox(self.walker)
        footer_markup: list[str | tuple[str, str]] = [
            ("foot", f"{title} | "),
            ("key", "esc"),
            ("foot", " save & close"),
        ]
        self.footer = urwid.AttrMap(urwid.Text(footer_markup), "foot")
        self.view = urwid.Frame(urwid.AttrMap(self.listbox, "body"), footer=self.footer)
        self.loop: urwid.MainLoop | None = None

    @property
    def text(self) -> str:
        return self.walker.text

    def main(self) -> str:
        """Run the editor and return the edited text."""
        self.loop = urwid.MainLoop(
            self.view, PALETTE, unhandled_input=self.handle_keypress
        )
        self.loop.run()
        return self.text

    def handle_keypress(self, key: str | tuple[str, int, int, int]) -> None:
        """Last resort for keys the widgets did not consume.

        urwid passes mouse events through this callback too, as a 4-tuple,
        so the signature has to admit them even though we ignore them.
        """
        if key == "esc":
            raise urwid.ExitMainLoop()
        if key == "delete":
            self.walker.combine_focus_with_next()
        elif key == "backspace":
            self.walker.combine_focus_with_prev()
        elif key == "enter":
            self.walker.split_focus()
            self.view.keypress(_SYNTHETIC_SIZE, "down")
            self.view.keypress(_SYNTHETIC_SIZE, "home")


def edit_text(text: str, title: str = "pen") -> str:
    """Open the built-in editor on ``text`` and return the result."""
    return EditDisplay(text, title=title).main()
