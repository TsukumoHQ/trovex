"""Regression guard (task 7111f05a): `trovex import` was dead on every install
because cli.py did `from . import onboarding` and src/trovex/onboarding.py was
never committed — the module existed only on the author's machine, so the
import silently worked in dev (site-packages editable install still saw the
untracked file) and broke for every real user/release/deploy.

This scans every src/trovex/*.py file for its relative imports (`from . import
X`, `from .X import Y`), including ones nested inside function bodies — cli.py's
onboarding import is exactly that shape, a lazy import inside _scan_dir — and
actually imports each target, so a missing module fails `make test` here
instead of a user's first CLI invocation.
"""

from __future__ import annotations

import ast
import importlib
import pathlib

import pytest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "trovex"


def _relative_import_targets(pyfile: pathlib.Path) -> list[tuple[str, str | None]]:
    """[(module_to_import, attr_to_check_or_None), ...] for every single-dot
    relative import in this file, at any nesting depth (ast.walk covers
    imports inside function/class bodies, not just module level)."""
    tree = ast.parse(pyfile.read_text(encoding="utf-8"))
    targets: list[tuple[str, str | None]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.level != 1:
            continue
        if node.module:
            # from .X import Y[, Z...]  ->  import trovex.X, check each Y/Z
            mod = f"trovex.{node.module}"
            for alias in node.names:
                if alias.name != "*":
                    targets.append((mod, alias.name))
        else:
            # from . import X[, Y...]  ->  import trovex.X directly
            for alias in node.names:
                targets.append((f"trovex.{alias.name}", None))
    return targets


def _all_targets() -> list[tuple[str, str, str | None]]:
    """[(source_file_display_name, module, attr), ...] across every module."""
    out = []
    for pyfile in sorted(SRC.glob("*.py")):
        for mod, attr in _relative_import_targets(pyfile):
            out.append((pyfile.name, mod, attr))
    return out


@pytest.mark.parametrize("source_file,module,attr", _all_targets())
def test_relative_import_resolves(source_file, module, attr):
    imported = importlib.import_module(module)
    if attr is not None:
        assert hasattr(imported, attr), (
            f"{source_file}: 'from .{module.removeprefix('trovex.')} import {attr}' "
            f"but {module} has no attribute {attr!r}"
        )
