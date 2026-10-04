"""Deploy-path wiring for the private /graph SPA.

server.py mounts /graph only when web/dist-graph/ exists; before this, no deploy
path built it, so prod /graph never mounted. These tests lock the wiring so the
regression can't come back silently: the deploy scripts must call the canonical
build step, and it must drive `build:graph`.

The server side (mount-when-built, 404-safe when missing) is already covered by
tests/test_server.py::test_graph_mount_*.
"""

import stat
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEPLOY = REPO / "deploy"


def test_build_graph_script_exists_and_is_executable():
    script = DEPLOY / "build-graph.sh"
    assert script.is_file(), "deploy/build-graph.sh missing"
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR, "deploy/build-graph.sh must be executable"


def test_build_graph_runs_build_graph_npm_script():
    body = (DEPLOY / "build-graph.sh").read_text(encoding="utf-8")
    assert "build:graph" in body, "build-graph.sh must run the build:graph npm script"
    assert "dist-graph" in body, "build-graph.sh must produce web/dist-graph"


def test_build_graph_is_a_real_npm_script():
    import json

    pkg = json.loads((REPO / "web" / "package.json").read_text(encoding="utf-8"))
    assert "build:graph" in pkg.get("scripts", {}), "web/package.json lost build:graph"


def test_serve_trovex_refresh_builds_graph():
    body = (DEPLOY / "serve-trovex.sh").read_text(encoding="utf-8")
    assert "build-graph.sh" in body, (
        "serve-trovex.sh must call build-graph.sh so the fleet host mounts /graph"
    )


def test_systemd_unit_documents_graph_build():
    body = (DEPLOY / "trovex.service").read_text(encoding="utf-8")
    assert "build-graph.sh" in body, (
        "trovex.service must document build-graph.sh (ProtectHome blocks build-at-start)"
    )


def test_deploy_readme_documents_graph():
    body = (DEPLOY / "README.md").read_text(encoding="utf-8")
    assert "build-graph.sh" in body and "/graph" in body, (
        "deploy/README.md must document the /graph build step"
    )
