"""Minimal YAML frontmatter, without a YAML dependency.

pen writes exactly two keys, so a full YAML parser would be a dependency earned
by two timestamps. What we emit is a strict subset -- flat ``key: value``
scalars between ``---`` fences -- that any real YAML parser reads correctly.

Two properties the rest of pen relies on:

* Anything we cannot represent as a flat scalar is captured as :class:`Raw` and
  written back byte for byte. Reformatting would mean reinterpreting YAML we
  never parsed: ``tags:`` with indented items became ``tags: ""``, which lost
  the list on the next write.
* A file with no frontmatter is valid, its whole content the body. That is what
  lets pen adopt a plain ``.md`` dropped into the store.
"""

from __future__ import annotations

from typing import NamedTuple

FENCE = "---"

#: Structural in YAML: quoting one would demote it to a plain string.
_STRUCTURAL_PREFIXES = ("[", "{", "&", "*", "!", "|", ">", "?")


class Raw(NamedTuple):
    """A frontmatter entry pen does not parse, kept exactly as written.

    ``head`` is the text after the colon on the key line, ``tail`` any
    continuation lines; with the key they reproduce the original byte for byte.
    """

    head: str
    tail: tuple[str, ...] = ()

    def __str__(self) -> str:
        return "\n".join([self.head.strip(), *self.tail]).strip()


#: A ``str`` value is a flat scalar pen may rewrite; a :class:`Raw` value is
#: round-tripped untouched.
Metadata = dict[str, "str | Raw"]


class Document(NamedTuple):
    """A parsed note file."""

    metadata: Metadata
    """Frontmatter entries, in file order."""

    body: str
    """Everything after the closing fence."""


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        inner = value[1:-1]
        if value[0] == '"':
            return _unescape(inner)
        return inner.replace("''", "'")
    return value


def _escaped(inner: str) -> list[str]:
    """The character following each backslash, scanning left to right."""
    found: list[str] = []
    index = 0
    while index < len(inner):
        if inner[index] == "\\":
            found.append(inner[index + 1] if index + 1 < len(inner) else "")
            index += 2
            continue
        index += 1
    return found


def _unescape(inner: str) -> str:
    """Undo the two escapes :func:`_quote` produces, scanning left to right."""
    out: list[str] = []
    index = 0
    while index < len(inner):
        character = inner[index]
        if character == "\\" and index + 1 < len(inner):
            out.append(inner[index + 1])
            index += 2
            continue
        out.append(character)
        index += 1
    return "".join(out)


def _quote(value: str) -> str:
    """Quote only when a bare scalar would be ambiguous to a real YAML parser."""
    if _needs_quoting(value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _needs_quoting(value: str) -> bool:
    if value == "" or value != value.strip():
        return True
    if value[0] in "\"'#,%@`]}" or value.startswith(_STRUCTURAL_PREFIXES):
        return True
    if "\\" in value:
        return True
    if value.startswith("- ") or value == "-":
        return True
    return ": " in value or value.endswith(":")


def _is_continuation(line: str) -> bool:
    """Does ``line`` belong to the entry above rather than start a new one?

    A ``- `` item at column zero counts: YAML permits a block sequence at the
    same indentation as its key.
    """
    if not line.strip():
        return False
    if line[0] in " \t":
        return True
    stripped = line.strip()
    return stripped == "-" or stripped.startswith("- ")


def _is_scalar(head: str) -> bool:
    """Can ``head`` be re-emitted from a plain string without changing meaning?"""
    value = head.strip()
    if value.startswith(_STRUCTURAL_PREFIXES):
        return False
    if "\\" not in value:
        return True
    if len(value) < 2 or value[0] != '"' or value[-1] != '"':
        return False
    # Tuple, not substring: a dangling backslash yields "".
    return all(character in ('"', "\\") for character in _escaped(value[1:-1]))


def parse(text: str) -> Document:
    """Split ``text`` into frontmatter metadata and body."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != FENCE:
        return Document({}, _join(lines))

    for index in range(1, len(lines)):
        if lines[index].strip() == FENCE:
            break
    else:
        return Document({}, _join(lines))

    metadata: Metadata = {}
    position = 1
    while position < index:
        line = lines[position]
        position += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, head = line.partition(":")
        if not separator:
            continue

        start = position
        while position < index and _is_continuation(lines[position]):
            position += 1
        tail = tuple(lines[start:position])

        if not tail and _is_scalar(head):
            metadata[key.strip()] = _unquote(head.strip())
        else:
            metadata[key.strip()] = Raw(head, tail)

    return Document(metadata, _join(_strip_separator(lines[index + 1 :])))


def render(metadata: Metadata, body: str) -> str:
    """Inverse of :func:`parse`. Empty metadata means no fences at all."""
    if not metadata:
        return normalize_body(body)

    lines = [FENCE]
    for key, value in metadata.items():
        if isinstance(value, Raw):
            lines.append(f"{key}:{value.head}")
            lines.extend(value.tail)
        else:
            lines.append(f"{key}: {_quote(value)}")
    lines.append(FENCE)
    lines.append("")
    return "\n".join(lines) + "\n" + normalize_body(body)


def _strip_separator(lines: list[str]) -> list[str]:
    """Drop the single blank line :func:`render` puts after the closing fence."""
    if lines and lines[0] == "":
        return lines[1:]
    return lines


def _join(lines: list[str]) -> str:
    """Canonical body form, which every branch of :func:`parse` must return."""
    return "\n".join(lines)


def normalize_body(body: str) -> str:
    """Exactly one trailing newline, so rewrites are byte-stable."""
    stripped = body.rstrip("\n")
    return f"{stripped}\n" if stripped else ""
