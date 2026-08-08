"""Store location resolution.

Each source in the priority chain is a separate branch, so each gets a test:
``$PEN_PATH``, the config file, the legacy ``path.ini``, and the XDG default.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pen import config


def test_default_is_under_xdg_data_home(isolated_environment: Path) -> None:
    expected = isolated_environment / ".local" / "share" / "pen"
    assert config.resolve_root() == expected
    assert config.default_root() == expected


def test_xdg_variables_are_honored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert config.resolve_root() == tmp_path / "data" / "pen"
    assert config.config_dir() == tmp_path / "cfg" / "pen"


def test_falls_back_to_home_when_xdg_is_unset(
    isolated_environment: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("XDG_DATA_HOME")
    monkeypatch.delenv("XDG_CONFIG_HOME")
    assert config.resolve_root() == isolated_environment / ".local/share/pen"
    assert config.config_dir() == isolated_environment / ".config/pen"


def test_env_var_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config.set_root(tmp_path / "configured")
    monkeypatch.setenv("PEN_PATH", str(tmp_path / "override"))
    assert config.resolve_root() == tmp_path / "override"


def test_config_file_beats_default(tmp_path: Path) -> None:
    config.set_root(tmp_path / "elsewhere")
    assert config.resolve_root() == tmp_path / "elsewhere"


def test_legacy_path_ini_is_still_read(tmp_path: Path) -> None:
    """A store configured by an older version keeps working untouched."""
    directory = config.config_dir()
    directory.mkdir(parents=True)
    (directory / "path.ini").write_text(str(tmp_path / "old"), encoding="utf-8")
    assert config.resolve_root() == tmp_path / "old"


def test_new_config_file_beats_legacy_path_ini(tmp_path: Path) -> None:
    directory = config.config_dir()
    directory.mkdir(parents=True)
    (directory / "path.ini").write_text(str(tmp_path / "old"), encoding="utf-8")
    (directory / "path").write_text(str(tmp_path / "new"), encoding="utf-8")
    assert config.resolve_root() == tmp_path / "new"


def test_set_root_removes_the_legacy_file(tmp_path: Path) -> None:
    directory = config.config_dir()
    directory.mkdir(parents=True)
    (directory / "path.ini").write_text(str(tmp_path / "old"), encoding="utf-8")

    config.set_root(tmp_path / "new")

    assert not (directory / "path.ini").exists()


def test_reset_root_really_resets(tmp_path: Path) -> None:
    """Leaving path.ini behind would resurrect that path on the next run."""
    directory = config.config_dir()
    directory.mkdir(parents=True)
    (directory / "path.ini").write_text(str(tmp_path / "old"), encoding="utf-8")
    config.set_root(tmp_path / "new")

    assert config.reset_root() == config.default_root()
    assert config.resolve_root() == config.default_root()


def test_reset_root_when_nothing_was_configured() -> None:
    assert config.reset_root() == config.default_root()


def test_tilde_is_expanded(isolated_environment: Path) -> None:
    config.set_root(Path("~/notes"))
    assert config.resolve_root() == isolated_environment / "notes"


def test_blank_config_file_is_ignored() -> None:
    directory = config.config_dir()
    directory.mkdir(parents=True)
    (directory / "path").write_text("   \n", encoding="utf-8")
    assert config.resolve_root() == config.default_root()


def test_unreadable_config_file_is_ignored() -> None:
    """A directory where the config file should be must not crash pen."""
    directory = config.config_dir()
    directory.mkdir(parents=True)
    (directory / "path").mkdir()
    assert config.resolve_root() == config.default_root()


def test_resolving_does_not_create_anything() -> None:
    root = config.resolve_root()
    assert not root.exists()
    assert not config.config_dir().exists()


def test_macos_reads_the_legacy_path_written_by_clint(
    isolated_environment: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """clint put path.ini under Application Support on darwin, not XDG."""
    monkeypatch.setattr(sys, "platform", "darwin")
    legacy = isolated_environment / "Library" / "Application Support" / "pen"
    legacy.mkdir(parents=True)
    (legacy / "path.ini").write_text("/somewhere/notes\n")

    assert config.resolve_root() == Path("/somewhere/notes")

    config.reset_root()
    assert not (legacy / "path.ini").exists()
    assert config.resolve_root() == config.default_root()
