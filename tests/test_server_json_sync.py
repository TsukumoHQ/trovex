"""server.json is the MCP registry manifest — a human bumps it by hand at release time
(see .github/workflows/publish-mcp.yml). This only pins its INTERNAL consistency (the
top-level version and both packages[].version entries agree), which must hold at every
commit — unlike an exact match against the installed dist version, which legitimately
drifts between a tag and the next release and would make the test flaky.
"""

import json
from pathlib import Path

SERVER_JSON = Path(__file__).parent.parent / "server.json"


def test_server_json_package_versions_match_top_level():
    manifest = json.loads(SERVER_JSON.read_text())
    top = manifest["version"]
    pkg_versions = {pkg["version"] for pkg in manifest["packages"]}
    assert pkg_versions == {top}, (
        f"server.json packages[].version {pkg_versions} != top-level version {top!r} "
        "— a partial hand-edit at release time desynced them"
    )
