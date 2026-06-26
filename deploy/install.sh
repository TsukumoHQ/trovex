#!/usr/bin/env bash
# Install/update trovex as a systemd service on this host.
# Run with: sudo bash deploy/install.sh
set -euo pipefail

PROJECT_DIR="/home/trovex/trovex"
TRAEFIK_DIR="/home/trovex/docs-repo/docker/config/traefik/dynamic"
DATA_DIR="/home/trovex/.trovex-data"

if [ "$EUID" -ne 0 ]; then
    echo "Run with sudo: sudo bash deploy/install.sh"
    exit 1
fi

mkdir -p "$DATA_DIR"
chown -R trovex:trovex "$DATA_DIR"

# Sync deps + ensure venv is built
sudo -u trovex bash -c "cd $PROJECT_DIR && /home/trovex/.local/bin/uv sync"

# Install systemd units (project -> /etc/systemd/system via symlink)
install -m 644 "$PROJECT_DIR/deploy/trovex.service" /etc/systemd/system/trovex.service
install -m 644 "$PROJECT_DIR/deploy/trovex-reindex.service" /etc/systemd/system/trovex-reindex.service
install -m 644 "$PROJECT_DIR/deploy/trovex-reindex.timer" /etc/systemd/system/trovex-reindex.timer

# Install Traefik dynamic config
if [ -d "$TRAEFIK_DIR" ]; then
    install -m 644 "$PROJECT_DIR/deploy/traefik-trovex.yml" "$TRAEFIK_DIR/trovex.yml"
    echo "Traefik config installed at $TRAEFIK_DIR/trovex.yml"
else
    echo "WARN: Traefik dir not found at $TRAEFIK_DIR — skipping route install"
fi

systemctl daemon-reload
systemctl enable --now trovex.service
systemctl enable --now trovex-reindex.timer

echo
echo "Installed. Status:"
systemctl status trovex.service --no-pager | head -10 || true
echo
echo "Try: curl http://127.0.0.1:8770/healthz"
echo "Once Traefik reloads its dynamic config: https://trovex.example.com/"
