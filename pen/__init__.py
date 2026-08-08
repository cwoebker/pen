"""pen: terminal notes."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("penpal")
except PackageNotFoundError:  # pragma: no cover - only hit when running from a
    # source tree that was never installed (e.g. `python -c "import pen"`).
    __version__ = "0.0.0.dev0"

__all__ = ["__version__"]
