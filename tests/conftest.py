"""Shared fixtures.

No test may touch the real environment. The ``isolated_environment`` fixture is
autouse and redirects ``$HOME`` and both XDG roots into ``tmp_path``, clears
``$PEN_PATH``/``$EDITOR``/``$VISUAL``, and pins ``$COLUMNS`` so rich's wrapping
does not depend on the terminal the suite happens to run in.
"""

from __future__ import annotations

import json
import zlib
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner

from pen.cli import main
from pen.storage import NoteStore, open_store

#: Wide enough that no message under test wraps. rich wraps at the terminal
#: width, which would otherwise make assertions depend on the dev's window.
TEST_COLUMNS = "200"


@pytest.fixture(autouse=True)
def isolated_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    home = tmp_path / "home"
    (home / ".config").mkdir(parents=True)
    (home / ".local" / "share").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
    monkeypatch.setenv("COLUMNS", TEST_COLUMNS)
    for variable in ("PEN_PATH", "EDITOR", "VISUAL"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    yield home


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty store root, wired up as the configured one."""
    path = tmp_path / "store"
    monkeypatch.setenv("PEN_PATH", str(path))
    return path


@pytest.fixture
def store(root: Path) -> NoteStore:
    return open_store(root)


@dataclass(frozen=True)
class Result:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        return self.stdout + self.stderr


@pytest.fixture
def run() -> Callable[..., Result]:
    """Invoke the real entry point and capture streams and exit code.

    Goes through ``pen.cli.main`` rather than ``CliRunner.invoke(cli)`` on
    purpose: main() is where domain errors are mapped onto exit codes, and that
    mapping is the thing most worth asserting.
    """
    runner = CliRunner()

    def invoke(*args: str, input: str | None = None) -> Result:
        with runner.isolation(input=input) as streams:
            code = main(list(args))
        stdout, stderr = streams[0], streams[1]
        return Result(
            exit_code=code,
            stdout=stdout.getvalue().decode("utf-8", "replace"),
            stderr=stderr.getvalue().decode("utf-8", "replace"),
        )

    return invoke


def make_legacy_blob(data: Mapping[str, object]) -> bytes:
    """Build a store in the legacy on-disk format."""
    return zlib.compress(json.dumps(data).encode("utf-8"))


@pytest.fixture
def legacy_blob() -> bytes:
    return make_legacy_blob(
        {
            "work": {"todo": "buy milk", "standup": "notes\nover\nlines"},
            "ideas": {"app": "a pen"},
        }
    )


def ago(**kwargs: float) -> datetime:
    """A timestamp relative to now.

    Every time-sensitive assertion is built from this rather than a literal
    date, so the suite cannot start failing on a particular calendar day.
    """
    return datetime.now(UTC).replace(microsecond=0) - timedelta(**kwargs)
