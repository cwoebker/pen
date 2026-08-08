"""Domain objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .frontmatter import Metadata


class WriteOutcome(StrEnum):
    """What a write actually did.

    Reported rather than assumed, so "saved" means saved and an unchanged note
    does not bump its ``modified`` stamp.
    """

    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


@dataclass(slots=True)
class Note:
    """A single note, as stored in one markdown file."""

    list_name: str
    name: str
    body: str
    created: datetime
    modified: datetime
    extra: Metadata = field(default_factory=dict)
    """Frontmatter keys pen does not own, preserved verbatim across writes."""

    @property
    def title(self) -> str:
        return f"{self.list_name}/{self.name}"

    @property
    def is_empty(self) -> bool:
        return not self.body.strip()


@dataclass(frozen=True, slots=True)
class MigrationReport:
    """Result of importing a legacy blob store into the file tree."""

    source: str
    backup: str
    lists: int
    notes: int
