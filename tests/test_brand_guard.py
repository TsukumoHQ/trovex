"""Brand guard (scripts/brand_guard.py) — each rule CATCHES a real violation, clean
lines pass, the allowlist protects functional identifiers, and the live repo scans
clean (no false positives). Rules spec = trovex doc 1dcec9e9.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "brand_guard", Path(__file__).resolve().parent.parent / "scripts" / "brand_guard.py"
)
bg = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bg)


def _stripped(line: str) -> str:
    return bg.ALLOW.sub("", line)


def test_rule1_fabricated_multiplier():
    assert bg._rule1_multiplier("trovex makes agents 10x cheaper")
    assert bg._rule1_multiplier("ship ~10x faster")
    assert not bg._rule1_multiplier("about 60% fewer tokens")  # a percentage, not Nx
    assert not bg._rule1_multiplier("10x improvement (source: our-benchmark)")  # cited
    assert not bg._rule1_multiplier("10x improvement, see https://trovex.dev/benchmark")


def test_rule2_legacy_leak():
    assert bg._rule2_legacy("clone github.com/Synergix-lab/trovex")
    assert bg._rule2_legacy("served at trovex.prod.synergix.ch/mcp")
    assert bg._rule2_legacy("the old ctx.prod host")
    assert not bg._rule2_legacy("const ctx = canvas.getContext('2d')")  # canvas var, not the brand
    # The correct registry name survives the allowlist → not flagged.
    assert not bg._rule2_legacy(_stripped("mcp-name: io.github.TsukumoHQ/trovex"))


def test_rule3_uppercased_wordmark():
    assert bg._rule3_wordmark("install the Trovex tool today")  # mid-sentence
    assert bg._rule3_wordmark("we built Tsukumo for teams")
    assert not bg._rule3_wordmark("Trovex is one canonical doc per query")  # sentence start = ok
    assert not bg._rule3_wordmark("# trovex")  # lowercase wordmark


def test_rule4_acidlime_on_product():
    assert bg._rule4_acidlime("--accent: #c8ff00;")
    assert not bg._rule4_acidlime("--accent: #22c55e;")  # trovex green = correct


def test_rule5_dokan_overpromise():
    assert bg._rule5_dokan("dokan is enterprise-grade and multi-tenant")
    assert not bg._rule5_dokan("dokan runs deterministic scripts in containers")
    assert not bg._rule5_dokan("our service is enterprise-grade")  # not a dokan line


def test_live_repo_scans_clean():
    """The guard must pass on the current public surfaces — zero false positives."""
    assert bg.scan() == []
