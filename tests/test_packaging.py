"""Packaging metadata checks.

These assert the things that silently rot between releases: that the installed
distribution name still matches what ``pen`` reads at import time, and that the
console script entry point resolves to a real callable.
"""

from __future__ import annotations

from importlib.metadata import distribution, entry_points

import pen


def test_version_is_resolved_from_installed_metadata() -> None:
    assert pen.__version__ == distribution("penpal").version
    assert pen.__version__ != "0.0.0.dev0"


def test_console_script_entry_point_resolves() -> None:
    (script,) = [ep for ep in entry_points(group="console_scripts") if ep.name == "pen"]
    assert callable(script.load())


def test_license_is_declared_as_an_spdx_expression() -> None:
    metadata = distribution("penpal").metadata
    assert metadata["License-Expression"] == "MIT"
    # PEP 639 forbids pairing the expression with a license classifier.
    assert not [
        c for c in metadata.get_all("Classifier", []) if c.startswith("License")
    ]
