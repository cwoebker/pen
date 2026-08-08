"""Domain errors.

Everything pen raises for a *user-facing* problem derives from :class:`PenError`.
``pen.cli.main`` catches it and exits non-zero, so pen composes with ``&&`` and
``set -e``.
"""

from __future__ import annotations


class PenError(Exception):
    """Base class for every expected, user-facing failure."""


class InvalidNameError(PenError):
    """A list or note name is not usable as a path component."""


class ReservedNameError(InvalidNameError):
    """A list name would shadow a pen subcommand."""


class ListNotFoundError(PenError):
    """No list of that name exists."""


class NoteNotFoundError(PenError):
    """No note of that name exists in the given list."""


class ListExistsError(PenError):
    """A list of that name already exists."""


class StorageError(PenError):
    """The store could not be read or written."""


class MigrationError(StorageError):
    """A legacy store was found but could not be migrated."""
