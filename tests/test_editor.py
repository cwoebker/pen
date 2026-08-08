"""The built-in urwid editor, driven without a terminal.

The editor takes and returns a string and never touches the filesystem, so
every one of these runs headlessly -- no TTY, no temp files.
"""

from __future__ import annotations

import pytest
import urwid

from pen.editor import EditDisplay, LineWalker, edit_text


def test_text_round_trips_untouched() -> None:
    text = "first line\nsecond line\nthird"
    assert LineWalker(text).text == text


def test_empty_text_yields_one_empty_line() -> None:
    walker = LineWalker("")
    assert len(walker.lines) == 1
    assert walker.text == ""


def test_tabs_survive_a_round_trip() -> None:
    """Opening a note must not rewrite its indentation."""
    text = "def f():\n\treturn 1"
    assert LineWalker(text).text == text


def test_spaces_are_not_collapsed_back_into_tabs() -> None:
    """Whitespace is note content: the editor must not reformat it on save."""
    text = "def f():\n        return 1"
    assert LineWalker(text).text == text


def test_walker_navigation() -> None:
    walker = LineWalker("one\ntwo\nthree")
    assert walker.get_focus()[1] == 0
    assert walker.get_next(0)[0] is not None
    assert walker.get_next(0)[1] == 1
    assert walker.get_prev(0) == (None, None)
    assert walker.get_next(2) == (None, None)


def test_set_focus() -> None:
    walker = LineWalker("one\ntwo")
    walker.set_focus(1)
    assert walker.get_focus()[1] == 1


def test_split_focus() -> None:
    walker = LineWalker("hello world")
    walker.lines[0].set_edit_pos(5)
    walker.split_focus()
    assert walker.text == "hello\n world"


def test_split_at_end_of_line() -> None:
    walker = LineWalker("hello")
    walker.lines[0].set_edit_pos(5)
    walker.split_focus()
    assert walker.text == "hello\n"


def test_combine_with_prev() -> None:
    walker = LineWalker("one\ntwo")
    walker.set_focus(1)
    walker.combine_focus_with_prev()
    assert walker.text == "onetwo"
    assert walker.focus == 0


def test_combine_with_prev_at_top_is_a_no_op() -> None:
    walker = LineWalker("one\ntwo")
    walker.combine_focus_with_prev()
    assert walker.text == "one\ntwo"


def test_combine_with_next() -> None:
    walker = LineWalker("one\ntwo")
    walker.combine_focus_with_next()
    assert walker.text == "onetwo"


def test_combine_with_next_at_bottom_is_a_no_op() -> None:
    walker = LineWalker("one\ntwo")
    walker.set_focus(1)
    walker.combine_focus_with_next()
    assert walker.text == "one\ntwo"


def test_escape_exits_the_loop() -> None:
    display = EditDisplay("body")
    with pytest.raises(urwid.ExitMainLoop):
        display.handle_keypress("esc")


@pytest.mark.parametrize(
    ("key", "expected"),
    [("delete", "onetwo"), ("backspace", "one\ntwo")],
)
def test_keypresses_edit_the_buffer(key: str, expected: str) -> None:
    display = EditDisplay("one\ntwo")
    display.handle_keypress(key)
    assert display.text == expected


def test_enter_splits_the_focused_line() -> None:
    display = EditDisplay("hello world")
    display.walker.lines[0].set_edit_pos(5)
    display.handle_keypress("enter")
    assert display.text == "hello\n world"


def test_unknown_keys_are_ignored() -> None:
    display = EditDisplay("body")
    display.handle_keypress("f5")
    assert display.text == "body"


def test_mouse_events_do_not_crash() -> None:
    """urwid routes mouse events through unhandled_input as a 4-tuple."""
    display = EditDisplay("body")
    display.handle_keypress(("mouse press", 1, 10, 10))
    assert display.text == "body"


def test_main_returns_the_edited_text(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(self: urwid.MainLoop) -> None:
        # Stand in for the user typing and pressing esc.
        display.walker.lines[0].set_edit_text("changed")

    monkeypatch.setattr(urwid.MainLoop, "run", fake_run)
    display = EditDisplay("original")
    assert display.main() == "changed"


def test_edit_text_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urwid.MainLoop, "run", lambda self: None)
    assert edit_text("unchanged text") == "unchanged text"


def test_footer_shows_the_note_title(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urwid.MainLoop, "run", lambda self: None)
    display = EditDisplay("x", title="work/todo")
    assert "work/todo" in display.footer.base_widget.text


def test_an_edited_line_is_saved_as_it_was_typed() -> None:
    walker = LineWalker("a\tb")
    walker.lines[0].set_edit_text("edited")
    assert walker.text == "edited"


def test_tabs_are_expanded_for_display_only() -> None:
    """urwid counts a tab as one column; the terminal expands it."""
    walker = LineWalker("a\tb")
    assert walker.lines[0].edit_text == "a\tb".expandtabs()
    assert walker.text == "a\tb"


def test_a_typed_tab_indents_with_spaces() -> None:
    """urwid's allow_tab inserts spaces to the next stop, never a tab."""
    line = LineWalker("xy").lines[0]
    line.set_edit_pos(1)

    line.keypress((10,), "tab")

    assert line.edit_text == "x       y"
