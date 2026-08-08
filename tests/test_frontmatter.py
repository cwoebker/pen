"""Frontmatter parsing and rendering, including round-trip guarantees."""

from __future__ import annotations

import pytest

from pen import frontmatter


def test_parses_metadata_and_body() -> None:
    document = frontmatter.parse(
        "---\ncreated: 2020-01-01T00:00:00+00:00\ntags: a, b\n---\n\nthe body\n"
    )
    assert document.metadata == {
        "created": "2020-01-01T00:00:00+00:00",
        "tags": "a, b",
    }
    assert document.body == "the body"


def test_file_without_frontmatter_is_all_body() -> None:
    document = frontmatter.parse("just markdown\nno fences\n")
    assert document.metadata == {}
    assert document.body == "just markdown\nno fences"


def test_empty_input() -> None:
    assert frontmatter.parse("") == frontmatter.Document({}, "")


def test_unterminated_fence_is_treated_as_body() -> None:
    """Guessing where the block ended would silently truncate the note."""
    text = "---\ncreated: 2020-01-01T00:00:00+00:00\nstill going\n"
    document = frontmatter.parse(text)
    assert document.metadata == {}
    assert document.body == text.rstrip("\n")


def test_body_containing_a_fence_is_not_re_split() -> None:
    document = frontmatter.parse("---\nkey: value\n---\n\nabove\n\n---\n\nbelow\n")
    assert document.metadata == {"key": "value"}
    assert "above" in document.body
    assert "below" in document.body


def test_blank_lines_and_comments_are_skipped() -> None:
    document = frontmatter.parse("---\n# a comment\n\nkey: value\n---\nbody\n")
    assert document.metadata == {"key": "value"}


def test_value_containing_a_colon_survives() -> None:
    document = frontmatter.parse("---\nurl: https://example.com/x\n---\nbody\n")
    assert document.metadata == {"url": "https://example.com/x"}


@pytest.mark.parametrize(
    "value",
    [
        "plain",
        "with: colon",
        "trailing space ",
        "",
        "#hash",
        "- dash",
        "*star",
        "[bracket]",
        "ends with colon:",
        "'quoted'",
    ],
)
def test_values_round_trip(value: str) -> None:
    rendered = frontmatter.render({"key": value}, "body")
    assert frontmatter.parse(rendered).metadata["key"] == value


def test_render_without_metadata_emits_no_fences() -> None:
    assert frontmatter.render({}, "body") == "body\n"


def test_render_preserves_key_order() -> None:
    rendered = frontmatter.render({"b": "1", "a": "2", "c": "3"}, "x")
    keys = [line.split(":")[0] for line in rendered.splitlines()[1:4]]
    assert keys == ["b", "a", "c"]


@pytest.mark.parametrize(
    "body",
    ["", "one line", "two\nlines", "trailing\n\n\n", "  leading space"],
)
def test_body_round_trips(body: str) -> None:
    rendered = frontmatter.render({"k": "v"}, body)
    assert frontmatter.parse(rendered).body == frontmatter.normalize_body(body).rstrip(
        "\n"
    )


def test_normalize_body_is_idempotent() -> None:
    once = frontmatter.normalize_body("text\n\n\n")
    assert once == "text\n"
    assert frontmatter.normalize_body(once) == once


def test_rendering_is_byte_stable() -> None:
    """Re-rendering an unchanged note must not churn the file."""
    first = frontmatter.render({"k": "v"}, "body")
    document = frontmatter.parse(first)
    assert frontmatter.render(document.metadata, document.body) == first


@pytest.mark.parametrize(
    "text",
    ["body\n", "---\nk: v\n---\n\nbody\n", "body", "line\nline\n"],
)
def test_body_form_is_independent_of_whether_frontmatter_is_present(
    text: str,
) -> None:
    """The two parse branches must agree, or write_note miscompares."""
    assert not frontmatter.parse(text).body.endswith("\n")


def test_frontmatter_line_without_a_colon_is_skipped() -> None:
    document = frontmatter.parse("---\nkey: value\njust a bare line\n---\nbody\n")
    assert document.metadata == {"key": "value"}


# -- structures pen does not parse ---------------------------------------


@pytest.mark.parametrize(
    "block",
    [
        "tags:\n  - work\n  - urgent",
        "tags:\n- work\n- urgent",
        "nested:\n  a: 1\n  b: 2",
        "aliases: [one, two]",
        "mapping: {a: 1}",
        "literal: |\n  line one\n  line two",
        "folded: >\n  wrapped\n  text",
        "anchored: &ref value",
        "tagged: !!str 7",
        # Escapes richer than the two _quote emits: re-quoting would mangle them.
        'escaped: "a \\n b"',
        'unicode: "\\u00e9"',
    ],
)
def test_structures_pen_cannot_parse_round_trip_byte_for_byte(block: str) -> None:
    """Anything not a flat scalar is preserved exactly, never reinterpreted."""
    original = f"---\n{block}\n---\n\nbody\n"
    document = frontmatter.parse(original)
    assert frontmatter.render(document.metadata, document.body) == original


def test_block_sequence_is_not_flattened_to_an_empty_string() -> None:
    """The bug this guards: `tags:\\n  - work` became `tags: ""`, losing both."""
    document = frontmatter.parse("---\ntags:\n  - work\n---\n\nbody\n")
    assert isinstance(document.metadata["tags"], frontmatter.Raw)
    assert str(document.metadata["tags"]) == "- work"


def test_raw_entries_survive_a_pen_write() -> None:
    """The keys pen owns are rewritten; everything else comes back untouched."""
    document = frontmatter.parse(
        "---\ncreated: 2020-01-01T00:00:00+00:00\ntags:\n  - work\n---\n\nbody\n"
    )
    extra = dict(document.metadata)
    extra.pop("created")
    rendered = frontmatter.render(
        {"created": "2021-01-01T00:00:00+00:00", **extra}, document.body
    )
    assert "created: 2021-01-01T00:00:00+00:00" in rendered
    assert "tags:\n  - work" in rendered


# -- quoting -------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        '"quoted" start',
        'a " b',
        "back\\slash",
        "trailing space ",
        " leading",
        "with: colon",
        "ends:",
        "",
        "#h",
    ],
)
def test_quoted_values_round_trip(value: str) -> None:
    document = frontmatter.parse(frontmatter.render({"k": value}, "b"))
    assert document.metadata == {"k": value}


def test_a_value_starting_with_a_quote_is_escaped() -> None:
    """Unescaped, this emitted `k: ""Q3" review"`, which no YAML parser reads."""
    rendered = frontmatter.render({"k": '"Q3" review'}, "b")
    assert 'k: "\\"Q3\\" review"' in rendered


def test_only_one_blank_line_after_the_fence_is_the_separator() -> None:
    """Stripping them all made a body with leading blanks churn on every write."""
    assert frontmatter.parse("---\nk: v\n---\n\n\n\nbody\n").body == "\n\nbody"
    assert frontmatter.parse("---\nk: v\n---\nbody\n").body == "body"


def test_a_blank_frontmatter_line_does_not_continue_the_entry_above() -> None:
    document = frontmatter.parse("---\na: 1\n\nb: 2\n---\nbody\n")
    assert document.metadata == {"a": "1", "b": "2"}


def test_a_bare_backslash_value_is_kept_raw() -> None:
    """Legal YAML we did not write: re-quoting could change what it means."""
    original = "---\npath: C:\\Users\\me\n---\n\nbody\n"
    document = frontmatter.parse(original)
    assert isinstance(document.metadata["path"], frontmatter.Raw)
    assert frontmatter.render(document.metadata, document.body) == original


def test_a_trailing_backslash_inside_quotes_is_kept_raw() -> None:
    original = '---\nk: "ends\\"\n---\n\nbody\n'
    document = frontmatter.parse(original)
    assert isinstance(document.metadata["k"], frontmatter.Raw)
    assert frontmatter.render(document.metadata, document.body) == original


def test_a_single_quoted_value_written_by_another_tool_is_read() -> None:
    """pen quotes with double quotes; Obsidian and Jekyll often use single."""
    document = frontmatter.parse("---\nk: 'it''s here'\n---\n\nbody\n")
    assert document.metadata == {"k": "it's here"}
