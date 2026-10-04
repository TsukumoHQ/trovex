# Deploy / operator notes

How the live fleet host serves trovex, and how the private `/graph` view gets built.

## Serving (:8765 fleet host, macOS)

`deploy/serve-trovex.sh` refreshes a dedicated serve-worktree to `origin/main`,
runs `uv sync`, builds the `/graph` SPA, and (re)launches `trovex serve` under a
`com.tsukumo.trovex-serve` LaunchAgent. See the header of that script for env vars
and the `--install-launchd` / `--no-refresh` / `--dry-run` / `--exec` flags.

## The `/graph` view ("the codebase's brain")

`/graph` is a **private** React SPA (same contract as `/receipt`): `server.py`
mounts it **only when `web/dist-graph/` exists**. A build-less tree serves fine —
`/graph` just returns 404.

The deploy path builds it so prod actually mounts it:

- **macOS fleet host:** `deploy/serve-trovex.sh` calls `deploy/build-graph.sh`
  in its refresh block, best-effort (a web build hiccup never blocks the server).
- **Linux systemd (`deploy/trovex.service`):** the unit is hardened with
  `ProtectHome=read-only`, so it **cannot** build at start. Run the build as part
  of the update step, from the repo root, then restart:

  ```sh
  git pull && uv sync
  bash deploy/build-graph.sh      # → web/dist-graph/index.html
  systemctl restart trovex
  ```

`deploy/build-graph.sh` runs `npm ci && npm run build:graph` in `web/` (output
`web/dist-graph`, base `/graph/`). It skips cleanly when `web/` or `npm` is absent.

### Verify after deploy

```sh
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8765/graph/   # → 200
```
