"""Validation for list and note names.

Names become path components under the store root, so this is a security
boundary and not a cosmetic check: without it, ``pen work ../../etc/passwd``
would resolve outside the store entirely.

Names are rejected rather than slugified. Silently rewriting what the user
typed hides the mapping between the name they asked for and the file on disk,
and two different names can slugify onto the same file.
"""

from __future__ import annotations

from .errors import InvalidNameError, ReservedNameError

MAX_NAME_LENGTH = 128

#: A list called ``all`` would be unreachable: ``pen all`` resolves to the
#: built-in command.
RESERVED_NAMES = frozenset(
    {"all", "create", "delete", "help", "list", "open", "path", "show"}
)

#: Legal on POSIX, but the resulting store cannot be synced to Windows.
_WINDOWS_DEVICE_NAMES = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{digit}" for digit in range(1, 10)}
    | {f"lpt{digit}" for digit in range(1, 10)}
)


def validate_name(name: str, *, kind: str = "name") -> str:
    """Return ``name`` unchanged, or raise :class:`InvalidNameError`."""
    if not name or not name.strip():
        raise InvalidNameError(f"{kind} may not be empty")
    if name != name.strip():
        raise InvalidNameError(f"{kind} may not start or end with whitespace: {name!r}")
    if len(name) > MAX_NAME_LENGTH:
        raise InvalidNameError(
            f"{kind} is longer than {MAX_NAME_LENGTH} characters: {name[:32]!r}..."
        )
    if "/" in name or "\\" in name:
        raise InvalidNameError(f"{kind} may not contain a path separator: {name!r}")
    if name in (".", ".."):
        raise InvalidNameError(f"{kind} may not be {name!r}")
    if name.startswith("."):
        raise InvalidNameError(f"{kind} may not start with a dot: {name!r}")
    if name.endswith("."):
        raise InvalidNameError(f"{kind} may not end with a dot: {name!r}")
    if any(character < " " or character == "\x7f" for character in name):
        raise InvalidNameError(f"{kind} may not contain control characters: {name!r}")
    if name.split(".")[0].lower() in _WINDOWS_DEVICE_NAMES:
        raise InvalidNameError(f"{kind} is a reserved device name on Windows: {name!r}")
    return name


def validate_list_name(name: str) -> str:
    """Validate a list name, additionally rejecting subcommand names."""
    validate_name(name, kind="list name")
    if name.lower() in RESERVED_NAMES:
        raise ReservedNameError(
            f"{name!r} is a pen command, so a list of that name would be "
            f"unreachable. Pick another name."
        )
    return name


def validate_note_name(name: str) -> str:
    """Validate a note name. Note names may safely collide with commands."""
    return validate_name(name, kind="note name")
