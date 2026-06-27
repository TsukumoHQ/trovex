#!/usr/bin/env python3
"""Security CI-guard — fails a PR that introduces a new high/critical risk.

Slice of the suite security pass (CI-gate every product). Symmetric with
``scripts/brand_guard.py``: pure stdlib, no deps, runs on EVERY PR so it is safe
as a REQUIRED check. Catches the regex-detectable high/critical classes that a
deterministic pass can flag with low false-positive rate:

  R1  dangerous-call   — eval/exec/os.system/shell=True/pickle.load*/yaml.load
                         (non-safe)/__import__. Suppress a vetted use inline with
                         a trailing ``# nosec: <reason>``.
  R2  hardcoded-secret — a token/key/password assigned a literal, or an inline
                         sk-/ghp-/AKIA-style credential. Env/getenv/empty are fine.
  R3  raw-sql-interp   — an f-string / %-format / .format() spliced into an
                         execute()/executescript() SQL string. Parameterize (``?``)
                         instead; a vetted structural splice (column/where-clause,
                         never a value) is marked inline with ``# sql-safe: <reason>``.

Plus a tracked-secret-file check (git ls-files): a committed .env / *.pem / key /
.write_token is a credential-in-repo regression regardless of .gitignore.

Deeper SAST (taint/SSRF/authz) is out of mechanical scope — those need the
security-2026 review pass, not a regex gate. This gate stops the cheap, common,
high-severity regressions from merging silently.

Exit 1 + ``path:line — RULE n — <snippet>`` per hit; exit 0 when clean.
Run: ``python scripts/security_guard.py``.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Backend + ops surfaces of THIS repo. web/ JS is the site lane's gate; this guard
# owns the Python/ops backend so the two checks never collide.
SCOPE = ["src/trovex", "scripts", "deploy"]
SCAN_EXT = {".py", ".sh", ".mjs", ".js"}
SKIP_DIRS = {"node_modules", "dist", ".next", "__pycache__", ".venv", ".fastembed_cache"}
# This guard necessarily spells out the very patterns it hunts (eval(, shell=True…),
# so scanning itself would always self-trip. Its own tests cover its behaviour.
SKIP_FILES = {Path(__file__).resolve()}

# Tracked credential files must NEVER be committed (any of these path globs).
SECRET_FILE_GLOBS = ("*.pem", "*.key", "*.p12", "*.pfx", ".env", ".env.*", ".write_token")

# Suppression markers (stripped/checked per line, mirroring brand_guard's ALLOW).
_NOSEC = re.compile(r"#\s*nosec\b")
_SQL_SAFE = re.compile(r"#\s*sql-safe:")

# R1 — dangerous calls. A real CALL binds `(` directly (no space) — this skips a
# `def eval(` definition AND the word "eval (" in prose/help-strings/comments.
_DANGER = re.compile(
    r"(?<!def )(?<!\.)\b(eval|exec)\("  # eval()/exec() call, not a def/method/prose
    r"|\bos\.system\("
    r"|shell\s*=\s*True"
    r"|\bpickle\.loads?\("
    r"|\b__import__\("
)
# yaml.load without an explicit safe Loader is unsafe (arbitrary object construction).
_YAML_UNSAFE = re.compile(r"\byaml\.load\(")
_YAML_SAFE = re.compile(r"Loader\s*=\s*(yaml\.)?(Safe|CSafe)Loader|yaml\.safe_load")

# R2 — hardcoded secret. A token-ish name assigned a non-trivial literal, or an
# inline provider credential. Env reads / empty / type annotations are excluded.
_SECRET_ASSIGN = re.compile(
    r"(?i)\b(pass(word|wd)?|secret|api[_-]?key|access[_-]?key|auth[_-]?token|token)\b"
    r"\s*[:=]\s*[\"'][^\"'\n]{12,}[\"']"
)
_PROVIDER_CRED = re.compile(r"\b(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b")
_SECRET_EXCLUDE = re.compile(
    r"getenv|environ|os\.environ|Query\(|Field\(|field\(|Settings|BaseSettings"
    r"|TOKEN_FILE|_FILE\b|\.get\(|placeholder|example|EXAMPLE|<[^>]+>|\$\{"
)

# R3 — raw SQL interpolation in an execute() call.
_SQL_INTERP = re.compile(r"execute(script)?\s*\(\s*(f[\"']|.*%\s|.*\.format\s*\()")


def _rule1_danger(line: str) -> bool:
    if _NOSEC.search(line):
        return False
    if _YAML_UNSAFE.search(line) and not _YAML_SAFE.search(line):
        return True
    return bool(_DANGER.search(line))


def _rule2_secret(line: str) -> bool:
    if _SECRET_EXCLUDE.search(line):
        return False
    if _PROVIDER_CRED.search(line):
        return True
    return bool(_SECRET_ASSIGN.search(line))


def _rule3_sql(line: str) -> bool:
    if _SQL_SAFE.search(line):
        return False
    return bool(_SQL_INTERP.search(line))


# (n, description, fn)
RULES = [
    (
        1,
        "dangerous call (eval/exec/os.system/shell=True/pickle/yaml.load/__import__)",
        _rule1_danger,
    ),
    (2, "hardcoded secret literal", _rule2_secret),
    (3, "raw SQL interpolation in execute() — parameterize or mark # sql-safe:", _rule3_sql),
]


def iter_files(roots: list[str]):
    for r in roots:
        p = ROOT / r
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in p.rglob("*"):
                if (
                    f.is_file()
                    and not (set(f.parts) & SKIP_DIRS)
                    and f.suffix in SCAN_EXT
                    and f.resolve() not in SKIP_FILES
                ):
                    yield f


def scan(roots: list[str] | None = None) -> list[str]:
    offenders: list[str] = []
    for f in iter_files(roots or SCOPE):
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, raw in enumerate(text.splitlines(), 1):
            for n, _desc, fn in RULES:
                if fn(raw):
                    rel = f.relative_to(ROOT)
                    offenders.append(f"{rel}:{i} — RULE {n} — {raw.strip()[:100]}")
    return offenders


def tracked_secret_files() -> list[str]:
    """Tracked credential files (committed secrets) — caught regardless of .gitignore."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z", "--", *SECRET_FILE_GLOBS],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout
    except OSError:
        return []
    return [p for p in out.split("\0") if p]


def main() -> int:
    secrets = tracked_secret_files()
    if secrets:
        print("✗ Security guard FAILED — credential file(s) tracked in the repo:")
        print("  A committed secret is a leak even after deletion (it stays in history).")
        print(
            "  Remove it, rotate the credential, and load secrets from env / a gitignored file.\n"
        )
        for p in secrets[:20]:
            print("  " + p)
        if len(secrets) > 20:
            print(f"  … +{len(secrets) - 20} more")
        print("")

    offenders = scan()
    if offenders:
        print("✗ Security guard FAILED — high/critical risk introduced on a backend surface:")
        print("  (parameterize SQL, drop the dangerous call, or move the secret to env;")
        print("   a vetted use is suppressed inline with # nosec: / # sql-safe: <reason>)\n")
        for o in offenders:
            print("  " + o)
        print("")

    if secrets or offenders:
        return 1
    print("✓ Security guard: no tracked secrets, no high/critical risk on backend surfaces.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
