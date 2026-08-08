"""Where pen keeps things.

Resolution order for the store root, highest priority first: ``$PEN_PATH``,
``$XDG_CONFIG_HOME/pen/path``, a legacy ``path.ini`` (read only),
``$XDG_DATA_HOME/pen``.

Reads are pure. Only ``set_root``/``reset_root`` touch the filesystem.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "pen"
PATH_ENV_VAR = "PEN_PATH"

_CONFIG_FILENAME = "path"
_LEGACY_CONFIG_FILENAME = "path.ini"


def _xdg_dir(variable: str, default: str) -> Path:
    value = os.environ.get(variable)
    if value:
        return Path(value).expanduser()
    return Path.home() / default


def config_dir() -> Path:
    return _xdg_dir("XDG_CONFIG_HOME", ".config") / APP_NAME


def data_dir() -> Path:
    return _xdg_dir("XDG_DATA_HOME", ".local/share") / APP_NAME


def default_root() -> Path:
    return data_dir()


def _read_first_line(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    line = text.strip()
    return line or None


def _legacy_config_dirs() -> list[Path]:
    """Everywhere clint may have written ``path.ini``, in priority order."""
    directories = [config_dir()]
    if sys.platform == "darwin":
        directories.append(Path.home() / "Library" / "Application Support" / APP_NAME)
    return directories


def absolute(path: Path) -> Path:
    """Anchor ``path`` so it means the same thing from any directory.

    Not ``resolve()``: a store under a symlinked sync folder should keep
    following the symlink if it is re-pointed.
    """
    expanded = path.expanduser()
    if not expanded.is_absolute():
        expanded = Path.cwd() / expanded
    return Path(os.path.normpath(expanded))


def resolve_root() -> Path:
    """Return the configured store root. Does not create it."""
    override = os.environ.get(PATH_ENV_VAR)
    if override:
        return Path(override).expanduser()

    configured = _read_first_line(config_dir() / _CONFIG_FILENAME)
    if configured:
        return Path(configured).expanduser()

    for directory in _legacy_config_dirs():
        configured = _read_first_line(directory / _LEGACY_CONFIG_FILENAME)
        if configured:
            return Path(configured).expanduser()

    return default_root()


def set_root(path: Path) -> Path:
    """Persist ``path`` as the store root and return it."""
    resolved = absolute(path)
    directory = config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / _CONFIG_FILENAME).write_text(f"{resolved}\n", encoding="utf-8")
    _drop_legacy_config()
    return resolved


def reset_root() -> Path:
    """Forget any configured root and return the default."""
    (config_dir() / _CONFIG_FILENAME).unlink(missing_ok=True)
    _drop_legacy_config()
    return default_root()


def _drop_legacy_config() -> None:
    """Remove any legacy ``path.ini``; it outranks the default if left behind."""
    for directory in _legacy_config_dirs():
        (directory / _LEGACY_CONFIG_FILENAME).unlink(missing_ok=True)
