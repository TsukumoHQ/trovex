#!/usr/bin/env bash
# Install/update ctx as a systemd service on this host.
# Run with: sudo bash deploy/install.sh
set -euo pipefail

PROJECT_DIR="/home/synxadmin/Exposemd"
TRAEFIK_DIR="/home/synxadmin/synergix_prod/docker/config/traefik/dynamic"
DATA_DIR="/home/synxadmin/.ctx-data"

if [ "$EUID" -ne 0 ]; then
    echo "Run with sudo: sudo bash deploy/install.sh"
    exit 1
fi

mkdir -p "$DATA_DIR"
chown -R synxadmin:synxadmin "$DATA_DIR"

# Sync deps + ensure venv is built
sudo -u synxadmin bash -c "cd $PROJECT_DIR && /home/synxadmin/.local/bin/uv sync"

# Install systemd units (project -> /etc/systemd/system via symlink)
install -m 644 "$PROJECT_DIR/deploy/ctx.service" /etc/systemd/system/ctx.service
install -m 644 "$PROJECT_DIR/deploy/ctx-reindex.service" /etc/systemd/system/ctx-reindex.service
install -m 644 "$PROJECT_DIR/deploy/ctx-reindex.timer" /etc/systemd/system/ctx-reindex.timer

# Install Traefik dynamic config
if [ -d "$TRAEFIK_DIR" ]; then
    install -m 644 "$PROJECT_DIR/deploy/traefik-ctx.yml" "$TRAEFIK_DIR/ctx.yml"
    echo "Traefik config installed at $TRAEFIK_DIR/ctx.yml"
else
    echo "WARN: Traefik dir not found at $TRAEFIK_DIR — skipping route install"
fi

systemctl daemon-reload
systemctl enable --now ctx.service
systemctl enable --now ctx-reindex.timer

echo
echo "Installed. Status:"
systemctl status ctx.service --no-pager | head -10 || true
echo
echo "Try: curl http://127.0.0.1:8770/healthz"
echo "Once Traefik reloads its dynamic config: https://ctx.prod.synergix.ch/"
