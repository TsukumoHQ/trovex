# Deploying Acme Notes API

Acme Notes API is a single process with a local database, so deployment is
mostly about keeping that process running and its data directory backed up.

## Run under a process manager

A systemd unit is the simplest production setup:

```
[Service]
ExecStart=/usr/local/bin/acme-notes serve
Environment=ACME_HOST=0.0.0.0
Restart=on-failure
```

## Behind a reverse proxy

Terminate TLS at nginx or Caddy and forward to the local port. Acme Notes does
not terminate TLS itself.

## Backups

The entire state is the data directory. Stop the service (or use
`acme-notes backup` for a consistent online copy) and archive
`~/.acme-notes`. Restoring is a matter of putting the directory back and
starting the service.
