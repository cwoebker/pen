"""The note store: lists are directories, notes are ``.md`` files under them.

Plain files rather than a database because the store is meant to live in a sync
folder, where SQLite is a corruption hazard: clients copy the database out from
under an open connection and do not understand WAL sidecars.
"""

from __future__ import annotations

import json
import os
import zlib
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

from . import frontmatter
from .errors import (
    InvalidNameError,
    ListExistsError,
    ListNotFoundError,
    MigrationError,
    NoteNotFoundError,
    StorageError,
)
from .models import MigrationReport, Note, WriteOutcome
from .names import MAX_NAME_LENGTH, validate_list_name, validate_note_name

NOTE_SUFFIX = ".md"
LEGACY_BLOB_NAME = "pen"
BACKUP_SUFFIX = ".bak"

_CREATED_KEY = "created"
_MODIFIED_KEY = "modified"

_CRUFT = frozenset({".DS_Store", "Thumbs.db", ".localized"})


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _from_timestamp(value: float) -> datetime:
    return datetime.fromtimestamp(value, tz=UTC).replace(microsecond=0)


def _parse_datetime(value: str | None, fallback: datetime) -> datetime:
    """Parse an ISO 8601 stamp, tolerating anything a human may have typed."""
    if not value:
        return fallback
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return fallback
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _atomic_write(path: Path, text: str) -> None:
    """Write via a temp file and ``os.replace``, so a reader sees old or new.

    The temp file is a sibling because ``os.replace`` is only atomic within one
    filesystem.
    """
    temporary = path.with_name(f".{path.name}.tmp{os.getpid()}")
    try:
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise StorageError(f"could not write {path}: {error}") from error


class NoteStore:
    """Reads and writes notes under ``root``."""

    def __init__(self, root: Path) -> None:
        self.root = root

    # -- layout ---------------------------------------------------------

    def _list_dir(self, list_name: str) -> Path:
        return self.root / validate_list_name(list_name)

    def _note_path(self, list_name: str, note_name: str) -> Path:
        return (
            self._list_dir(list_name) / f"{validate_note_name(note_name)}{NOTE_SUFFIX}"
        )

    def ensure_root(self) -> None:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise StorageError(f"could not create {self.root}: {error}") from error

    # -- lists ----------------------------------------------------------

    def scan_lists(self) -> tuple[list[str], list[str]]:
        """Usable list names, and names present but unusable."""
        if not self.root.is_dir():
            return [], []
        usable: list[str] = []
        ignored: list[str] = []
        for entry in self.root.iterdir():
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            try:
                validate_list_name(entry.name)
            except InvalidNameError:
                ignored.append(entry.name)
            else:
                usable.append(entry.name)
        return sorted(usable, key=str.lower), sorted(ignored, key=str.lower)

    def lists(self) -> list[str]:
        return self.scan_lists()[0]

    def has_list(self, list_name: str) -> bool:
        return self._list_dir(list_name).is_dir()

    def require_list(self, list_name: str) -> Path:
        directory = self._list_dir(list_name)
        if not directory.is_dir():
            raise ListNotFoundError(f"no such list: {list_name}")
        return directory

    def create_list(self, list_name: str) -> None:
        directory = self._list_dir(list_name)
        if directory.is_dir():
            raise ListExistsError(f"list already exists: {list_name}")
        try:
            directory.mkdir(parents=True)
        except FileExistsError as error:
            raise ListExistsError(f"list already exists: {list_name}") from error
        except OSError as error:
            raise StorageError(f"could not create list {list_name}: {error}") from error

    def delete_list(self, list_name: str) -> int:
        """Delete a list and its notes, or refuse without removing any."""
        directory = self.require_list(list_name)
        notes = set(_note_files(directory))
        removable: list[Path] = []
        foreign: list[str] = []
        for entry in sorted(directory.iterdir()):
            if entry in notes or (entry.is_file() and _is_cruft(entry)):
                removable.append(entry)
            else:
                foreign.append(entry.name)
        if foreign:
            raise StorageError(
                f"list {list_name} also contains {', '.join(foreign)}, which pen "
                f"did not create. Nothing was deleted; remove them yourself first."
            )

        removed = 0
        try:
            for path in removable:
                path.unlink()
                if path in notes:
                    removed += 1
            directory.rmdir()
        except OSError as error:
            raise StorageError(
                f"could not delete list {list_name}: {error}. "
                f"{removed} note(s) were removed before the failure."
            ) from error
        return removed

    # -- notes ----------------------------------------------------------

    def scan_notes(self, list_name: str) -> tuple[list[str], list[str]]:
        """Usable note names in ``list_name``, and names present but unusable."""
        directory = self.require_list(list_name)
        usable: list[str] = []
        ignored: list[str] = []
        for path in _note_files(directory):
            try:
                validate_note_name(path.stem)
            except InvalidNameError:
                ignored.append(path.name)
            else:
                usable.append(path.stem)
        return sorted(usable, key=str.lower), sorted(ignored, key=str.lower)

    def note_names(self, list_name: str) -> list[str]:
        return self.scan_notes(list_name)[0]

    def has_note(self, list_name: str, note_name: str) -> bool:
        return self._note_path(list_name, note_name).is_file()

    def read_note(self, list_name: str, note_name: str) -> Note:
        self.require_list(list_name)
        path = self._note_path(list_name, note_name)
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise NoteNotFoundError(f"no such note: {list_name}/{note_name}") from error
        except OSError as error:
            raise StorageError(f"could not read {path}: {error}") from error

        document = frontmatter.parse(text)
        mtime = _from_timestamp(path.stat().st_mtime)
        metadata = dict(document.metadata)
        created = _parse_datetime(_scalar(metadata.pop(_CREATED_KEY, None)), mtime)
        modified = _parse_datetime(_scalar(metadata.pop(_MODIFIED_KEY, None)), mtime)
        return Note(
            list_name=list_name,
            name=note_name,
            body=document.body,
            created=created,
            modified=modified,
            extra=metadata,
        )

    def iter_notes(self, list_name: str) -> Iterator[Note]:
        for name in self.note_names(list_name):
            yield self.read_note(list_name, name)

    def write_note(self, list_name: str, note_name: str, body: str) -> WriteOutcome:
        """Create or update a note, reporting what actually changed."""
        self.require_list(list_name)
        path = self._note_path(list_name, note_name)
        now = _now()

        if path.is_file():
            existing = self.read_note(list_name, note_name)
            # Both sides in the form parse() returns.
            if existing.body == body.rstrip("\n"):
                return WriteOutcome.UNCHANGED
            note = Note(
                list_name=list_name,
                name=note_name,
                body=body,
                created=existing.created,
                modified=now,
                extra=existing.extra,
            )
            outcome = WriteOutcome.UPDATED
        else:
            note = Note(
                list_name=list_name,
                name=note_name,
                body=body,
                created=now,
                modified=now,
            )
            outcome = WriteOutcome.CREATED

        _atomic_write(path, _render(note))
        return outcome

    def delete_note(self, list_name: str, note_name: str) -> None:
        self.require_list(list_name)
        path = self._note_path(list_name, note_name)
        try:
            path.unlink()
        except FileNotFoundError as error:
            raise NoteNotFoundError(f"no such note: {list_name}/{note_name}") from error
        except OSError as error:
            raise StorageError(f"could not delete {path}: {error}") from error

    # -- migration ------------------------------------------------------

    def _legacy_blob(self) -> Path | None:
        """Either a blob inside the root, or a root that is itself the blob."""
        if self.root.is_file():
            return self.root
        candidate = self.root / LEGACY_BLOB_NAME
        return candidate if candidate.is_file() else None

    def migrate_legacy(self) -> MigrationReport | None:
        """Import a legacy zlib+JSON blob store into the file tree."""
        blob = self._legacy_blob()
        if blob is None:
            return None

        data = _read_legacy_blob(blob)
        stamp = _from_timestamp(blob.stat().st_mtime)
        backup = _backup_path(blob)
        blob.replace(backup)
        if blob == self.root:
            self.ensure_root()

        lists = notes = 0
        taken_lists: set[str] = set()
        for list_name, entries in data.items():
            if list_name == "__PATH__" or not isinstance(entries, dict):
                continue
            name = _sanitize(str(list_name), validate_list_name, taken_lists)
            directory = self.root / name
            directory.mkdir(parents=True, exist_ok=True)
            lists += 1
            taken_notes = {path.stem.lower() for path in _note_files(directory)}
            for note_name, body in entries.items():
                note = Note(
                    list_name=name,
                    name=_sanitize(str(note_name), validate_note_name, taken_notes),
                    body=body if isinstance(body, str) else "",
                    created=stamp,
                    modified=stamp,
                )
                _atomic_write(directory / f"{note.name}{NOTE_SUFFIX}", _render(note))
                notes += 1

        return MigrationReport(
            source=str(blob), backup=str(backup), lists=lists, notes=notes
        )


def _render(note: Note) -> str:
    metadata: frontmatter.Metadata = {
        _CREATED_KEY: note.created.isoformat(),
        _MODIFIED_KEY: note.modified.isoformat(),
        **note.extra,
    }
    return frontmatter.render(metadata, note.body)


def _scalar(value: str | frontmatter.Raw | None) -> str | None:
    """pen owns ``created``/``modified``; anything else it cannot read falls back."""
    return value if isinstance(value, str) else None


def _note_files(directory: Path) -> list[Path]:
    """The one definition of "a note file", shared by scan_notes and delete_list."""
    return sorted(
        path
        for path in directory.glob(f"*{NOTE_SUFFIX}")
        if path.is_file() and not path.name.startswith(".")
    )


def _is_cruft(path: Path) -> bool:
    """Left behind by a sync client or by pen itself, not user content."""
    return path.name in _CRUFT or (
        path.name.startswith(".") and ".tmp" in path.name and path.suffix != NOTE_SUFFIX
    )


def _read_legacy_blob(path: Path) -> dict[str, object]:
    try:
        data = json.loads(zlib.decompress(path.read_bytes()))
    except (OSError, zlib.error, ValueError) as error:
        raise MigrationError(
            f"{path} is not a readable pen store: {error}. "
            f"It has not been touched; nothing was imported."
        ) from error
    if not isinstance(data, dict):
        raise MigrationError(f"{path} does not contain a pen store")
    return data


def _backup_path(blob: Path) -> Path:
    """A backup name that never overwrites an existing one."""
    candidate = blob.with_name(blob.name + BACKUP_SUFFIX)
    counter = 2
    while candidate.exists():
        candidate = blob.with_name(f"{blob.name}{BACKUP_SUFFIX}.{counter}")
        counter += 1
    return candidate


#: Short of the limit so a numeric suffix always fits, which is what
#: guarantees :func:`_sanitize` terminates.
_IMPORT_NAME_LENGTH = MAX_NAME_LENGTH - 8


def _clean(name: str) -> str:
    cleaned = "".join("-" if character in "/\\" else character for character in name)
    cleaned = "".join(
        character for character in cleaned if character >= " " and character != "\x7f"
    )
    cleaned = cleaned[:_IMPORT_NAME_LENGTH].strip().strip(".").strip()
    return cleaned or "untitled"


def _sanitize(name: str, validate: Callable[[str], str], taken: set[str]) -> str:
    """Make an imported name usable as a path component, and unique.

    Import is the one place names are rewritten rather than rejected, but the
    result must still pass the validation a typed name would.
    """
    base = _clean(name)
    stem, dot, extension = base.partition(".")
    candidate = base
    counter = 1
    while candidate.lower() in taken or not _validates(candidate, validate):
        candidate = f"{stem}-{counter}{dot}{extension}"
        counter += 1
    taken.add(candidate.lower())
    return candidate


def _validates(name: str, validate: Callable[[str], str]) -> bool:
    try:
        validate(name)
    except InvalidNameError:
        return False
    return True


def open_store(root: Path) -> NoteStore:
    """Return a store at ``root``, migrating and creating it as needed."""
    store = NoteStore(root)
    store.migrate_legacy()
    store.ensure_root()
    return store
