"""Name validation.

Names become path components, so this is a security boundary and the rejection
cases matter more than the acceptance ones.
"""

from __future__ import annotations

import pytest

from pen.errors import InvalidNameError, ReservedNameError
from pen.names import (
    MAX_NAME_LENGTH,
    RESERVED_NAMES,
    validate_list_name,
    validate_note_name,
)


@pytest.mark.parametrize(
    "name",
    ["todo", "my-note", "my_note", "note.txt", "2026 plans", "ünïcödé", "a" * 128],
)
def test_accepts_reasonable_names(name: str) -> None:
    assert validate_note_name(name) == name


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("", "empty"),
        ("   ", "empty"),
        (" leading", "whitespace"),
        ("trailing ", "whitespace"),
        ("a" * (MAX_NAME_LENGTH + 1), "longer"),
        ("../escape", "path separator"),
        ("a/b", "path separator"),
        ("a\\b", "path separator"),
        (".", "may not be"),
        ("..", "may not be"),
        (".hidden", "start with a dot"),
        ("trailing.", "end with a dot"),
        ("nul\x00byte", "control characters"),
        ("tab\there", "control characters"),
        ("new\nline", "control characters"),
    ],
)
def test_rejects_dangerous_names(name: str, reason: str) -> None:
    with pytest.raises(InvalidNameError, match=reason):
        validate_note_name(name)


def test_traversal_cannot_escape_the_store() -> None:
    """A note name must never resolve outside the store root."""
    with pytest.raises(InvalidNameError):
        validate_note_name("../../etc/passwd")


@pytest.mark.parametrize(
    "name", ["con", "CON", "nul", "aux", "prn", "com1", "LPT9", "con.md"]
)
def test_rejects_windows_device_names(name: str) -> None:
    """Valid on POSIX, but the resulting store cannot be synced to Windows."""
    with pytest.raises(InvalidNameError, match="device name"):
        validate_note_name(name)


@pytest.mark.parametrize("name", sorted(RESERVED_NAMES))
def test_list_names_may_not_shadow_a_command(name: str) -> None:
    with pytest.raises(ReservedNameError, match="pen command"):
        validate_list_name(name)


@pytest.mark.parametrize("name", ["ALL", "Create", "Delete"])
def test_command_shadowing_check_is_case_insensitive(name: str) -> None:
    with pytest.raises(ReservedNameError):
        validate_list_name(name)


@pytest.mark.parametrize("name", sorted(RESERVED_NAMES))
def test_note_names_may_shadow_commands(name: str) -> None:
    """A note is always addressed via its list, so it cannot become orphaned."""
    assert validate_note_name(name) == name
