#!/bin/sh
# Gate check for task 819445bf: no GitHub Actions workflow other than the
# tag-triggered OIDC publish survives on this private repo.
set -eu
n=$(ls .github/workflows 2>/dev/null | grep -vc '^publish-mcp\.yml$' || true)
if [ "$n" -eq 0 ]; then
  echo no-extra-workflows
else
  echo "unexpected workflow files present:" >&2
  ls .github/workflows >&2
  exit 1
fi
