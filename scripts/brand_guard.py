#!/usr/bin/env python3
"""Brand CI-guard — fails a PR that reintroduces a brand-rule violation.

Rules spec (the contract): trovex doc 1dcec9e95e064b27bf4625cc0ec8d1ac
("Brand CI-guard — rules spec (program P3: enforce) v2", design-lead, locked).
Update THAT doc (not this script) on any rule change.

Scope = PUBLIC product surfaces of THIS repo only. Internal docs (.claude, .agents,
docs, growth/process|method|launch) + the founder de-branded specs are EXCLUDED.
NOTE: growth/social/** is in the spec's scope but is NOT scanned yet — those specs
carry legitimate "No Synergix" rule mentions; needs a design-lead-vetted allowlist
first (tracked, task 35b0ea01).

Pure stdlib, not shipped in the wheel. Run: `python scripts/brand_guard.py`.
Exit 1 + `path:line — RULE n — <snippet>` per hit; exit 0 when clean.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Owner-ruled PRIVATE paths — must NEVER be tracked in this PUBLIC repo. growth/ (the
# marketing playbook) was purged from history twice; a stale-clone merge re-injected it
# via history (#637), which .gitignore cannot stop. This gate catches a tracked re-add
# regardless of .gitignore, so the regression is impossible to merge.
PRIVATE_PREFIXES = ("growth/",)

# Public product surfaces (relative to repo root).
SCOPE = ["README.md", "web/public", "web/src", "web/index.html", "src/trovex/templates"]
SCAN_EXT = {".md", ".html", ".txt", ".json", ".webmanifest", ".tsx", ".ts", ".jsx", ".js", ".css"}
# Copy rules (fabricated Nx, wordmark case) only apply to PROSE/rendered text, not code
# files — a wordmark in a code comment or a "2x" in CSS is not human-facing marketing copy.
PROSE_EXT = {".md", ".html", ".txt"}
SKIP_DIRS = {"node_modules", "dist", ".next"}

# Allowlist — functional identifiers stripped from a line BEFORE rule checks, so they
# never trip a rule (server.json name is CamelCase by design; install cmds; analytics).
ALLOW = re.compile(
    r"(io\.github\.TsukumoHQ/trovex"          # mcp-name marker + server.json name (correct case)
    r"|github\.com/TsukumoHQ[\w./-]*"          # repo URLs
    r"|TsukumoHQ/[\w.-]+"                       # org/repo identifiers
    r"|uvx?\s+trovex|uv\s+tool\s+install"      # install commands
    r"|data-domain|/api/event|/js/script\.js"  # Plausible
    r"|application/ld\+json"                    # JSON-LD block marker
    r")",
    re.IGNORECASE,
)

PRODUCT_HEX = "#c8ff00"  # acid-lime = Tsukumo STUDIO signature; a violation on a PRODUCT surface.


def _rule1_multiplier(line: str) -> bool:
    # Fabricated multiplier as a product claim (e.g. "10x", "ship ~10x"), unless the
    # line carries a source/citation. ~60% (a percentage) is fine; this is the Nx form.
    if re.search(r"source\s*[:=]|https?://|\bcite", line, re.IGNORECASE):
        return False
    return bool(re.search(r"\b\d+\s*[x×]\b", line))


def _rule2_legacy(line: str) -> bool:
    # synergix family + the old product/host form `ctx.prod`/`ctx.synergix`. Bare `ctx`
    # is NOT flagged — it's a ubiquitous code identifier (canvas getContext, etc.); the
    # old-product-name-in-copy case is too noisy to enforce mechanically (design-lead
    # can tighten via the spec doc if needed).
    return bool(re.search(r"synergix|Synergix-lab|ctx\.(prod|synergix)", line, re.IGNORECASE))


def _rule3_wordmark(line: str) -> bool:
    # Uppercased product wordmark MID-sentence (preceded by a lowercase word) — the
    # sentence-start / heading / URL forms are the justified exception, so only flag
    # `<lowercase> Trovex` etc.
    return bool(re.search(r"[a-z]\s+(Trovex|Tsukumo|Dokan|Yoru|Wrai\.th)\b", line))


def _rule4_acidlime(line: str) -> bool:
    # This IS a product repo, so acid-lime anywhere on a scanned surface is a violation.
    return PRODUCT_HEX in line.lower()


def _rule5_dokan(line: str) -> bool:
    if "dokan" not in line.lower():
        return False
    return bool(re.search(r"production-grade|enterprise-grade|infinite scale|multi-tenant", line, re.IGNORECASE))


# (n, description, fn, prose_only) — prose_only rules skip code files.
RULES = [
    (1, "fabricated multiplier (Nx) as a product claim", _rule1_multiplier, True),
    (2, "legacy/leak name (synergix / ctx.prod)", _rule2_legacy, False),
    (3, "uppercased product wordmark mid-sentence", _rule3_wordmark, True),
    (4, "acid-lime #c8ff00 on a product surface", _rule4_acidlime, False),
    (5, "dokan overpromise", _rule5_dokan, False),
]


def iter_files(roots: list[str]):
    for r in roots:
        p = ROOT / r
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file() and not (set(f.parts) & SKIP_DIRS) and f.suffix in SCAN_EXT:
                    yield f


def scan(roots: list[str] | None = None) -> list[str]:
    offenders: list[str] = []
    for f in iter_files(roots or SCOPE):
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        is_prose = f.suffix in PROSE_EXT
        for i, raw in enumerate(text.splitlines(), 1):
            line = ALLOW.sub("", raw)
            for n, _desc, fn, prose_only in RULES:
                if prose_only and not is_prose:
                    continue
                if fn(line):
                    rel = f.relative_to(ROOT)
                    offenders.append(f"{rel}:{i} — RULE {n} — {raw.strip()[:100]}")
    return offenders


def tracked_private_paths() -> list[str]:
    """Tracked files under any PRIVATE_PREFIXES (owner-ruled private, must not be public)."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z", "--", *PRIVATE_PREFIXES],
            cwd=ROOT, capture_output=True, text=True, check=False,
        ).stdout
    except OSError:
        return []
    return [p for p in out.split("\0") if p]


def main() -> int:
    private = tracked_private_paths()
    if private:
        print("✗ Brand guard FAILED — PRIVATE paths tracked in the PUBLIC repo:")
        print("  growth/ is owner-ruled PRIVÉ (purged from history). Never commit it to trovex.")
        print("  If your branch carries it, you have a stale clone — re-clone off current main.\n")
        for p in private[:20]:
            print("  " + p)
        if len(private) > 20:
            print(f"  … +{len(private) - 20} more")
        print("")

    offenders = scan()
    if offenders:
        print("✗ Brand guard FAILED — brand-rule violations on public surfaces:")
        print("  (rules spec: trovex doc 1dcec9e9; fix the surface, or update the doc if a rule is wrong)\n")
        for o in offenders:
            print("  " + o)
        print("")

    if private or offenders:
        return 1
    print("✓ Brand guard: no private paths tracked, no brand-rule violations on public surfaces.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
