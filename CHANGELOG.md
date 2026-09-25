# Changelog

Format loosely follows [Keep a Changelog](https://keepachangelog.com/). trovex's
version is git-tag-derived (`hatch-vcs`, see `pyproject.toml`) — this file's
entries are what actually shipped in each tagged release, not a bump target.

## 0.13.4

### Fixed
- `trovex import` / `trovex onboard` crashed on every install (`ImportError:
  cannot import name 'onboarding' from 'trovex'`) — `src/trovex/onboarding.py`
  was never committed to git, so the module existed only on the original
  author's machine. Committed the module, with unit + CLI regression tests and
  a source guard that fails `make test` if any `src/trovex/*.py` relative
  import ever again points at a module that doesn't ship (task 7111f05a).
