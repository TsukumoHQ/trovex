# Installing Acme Notes API

Acme Notes API is a small self-hosted service for storing and searching notes.
This page covers installation on a fresh machine.

## Requirements

- Python 3.11 or newer
- 512 MB RAM and 200 MB of disk for the local index
- No external services — everything runs on one host

## Install from PyPI

```
pip install acme-notes
acme-notes --version
```

## Install from source

```
git clone https://example.invalid/acme/notes
cd notes
pip install -e .
```

## First run

Run `acme-notes init` once to create the data directory under `~/.acme-notes`.
The service is now ready; see the configuration page to point it at a custom
data directory or change the listen port.
