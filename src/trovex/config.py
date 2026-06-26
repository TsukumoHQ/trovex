import logging
import secrets
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("trovex.config")

WRITE_TOKEN_FILE = ".write_token"


@dataclass(frozen=True)
class Source:
    """A corpus root with its own id + display label.

    The id is used as foreign key in docs.source_id and shown as a pill in UI.
    Should be short, kebab-case, stable (renaming = reindex).
    """
    id: str
    label: str
    root: Path

    @classmethod
    def from_dict(cls, d: dict) -> "Source":
        return cls(
            id=str(d["id"]).strip(),
            label=str(d.get("label") or d["id"]),
            root=Path(d["root"]).expanduser().resolve(),
        )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TROVEX_", extra="ignore")

    # Paths
    project_root: Path = Path.cwd()  # legacy, kept for back-compat
    data_dir: Path = Path.home() / ".trovex-data"

    # Shared write token (env TROVEX_WRITE_TOKEN). When empty, the effective token
    # is resolved at boot by `resolve_write_token()` — which, by default, auto-
    # generates and persists a per-instance token so writes are NOT open. Set this
    # explicitly to share one token across machines/agents.
    # Gates trovex_write / trovex_tag / trovex_delete + the /api write endpoints.
    write_token: str = ""

    # Escape hatch: when true (env TROVEX_ALLOW_UNAUTH_WRITES=1) and no write_token
    # is configured, writes run fully OPEN with no auth — only appropriate when the
    # instance is bound to localhost / a trusted network. Logged loudly at boot.
    allow_unauth_writes: bool = False

    # Where /hooks/<name> downloads are served from (env TROVEX_HOOKS_DIR). Default
    # is the per-user Claude hooks dir; no hardcoded username.
    hooks_dir: Path = Path.home() / ".claude" / "hooks"

    # Query-log retention (env TROVEX_QUERY_RETENTION_DAYS): mcp_queries rows older
    # than this are purged at startup. <= 0 disables purging (keep everything).
    query_retention_days: int = 90

    # Multi-source: file at sources_config_path takes precedence; otherwise
    # falls back to a single source built from project_root.
    sources_config_path: Path = Path.home() / ".trovex-data" / "sources.yaml"

    # Embedding — defaults to OpenAI text-embedding-3-large (3072 dims, top
    # MTEB retrieval). Override via TROVEX_EMBED_MODEL env var; fastembed models
    # (e.g. BAAI/bge-small-en-v1.5) work too but trail OpenAI on retrieval.
    embed_model: str = "text-embedding-3-large"
    embed_dim: int = 3072

    # Indexing
    max_file_size_bytes: int = 1_000_000
    ignore_dirs: list[str] = [
        "node_modules", ".venv", "venv", ".git", "dist", "build",
        ".next", ".nuxt", "target", "vendor", "__pycache__",
        ".pytest_cache", ".ruff_cache", "fastembed_cache", ".trovex-cache",
        ".tox", "site-packages", ".idea", ".vscode",
        # Agent workspaces — full repo copies per agent, all duplicates
        "worktrees",
    ]

    # Status heuristics
    stale_age_days: int = 90
    dup_cosine_threshold: float = 0.90
    plan_path_patterns: list[str] = [
        r"PLAN[_\-]", r"_PLAN\.md$", r"^plans/", r"DRAFT", r"WIP",
    ]

    # Server
    host: str = "0.0.0.0"
    port: int = 8765

    # Rate limiting (slowapi, keyed by client IP). Empty disables a class.
    # Format: "<count>/<period>" e.g. "30/minute". Applies to the HTTP API only;
    # the MCP transport is gated by write_token, not these.
    rate_limit_search: str = "30/minute"
    rate_limit_write: str = "10/minute"

    # UI / API page sizes + caps (were hardcoded; overridable via TROVEX_* env).
    search_page_size: int = 12      # results per page on /search
    store_page_size: int = 60       # cards per page on /store
    search_limit_max: int = 20      # /api/search & /api/boot `limit`/`k` ceiling
    sparkline_w: int = 100          # inline activity sparkline width (px)
    sparkline_h: int = 30           # inline activity sparkline height (px)

    # Ranking weights
    freshness_half_life_days: float = 90.0

    def resolved_embed_dim(self) -> int:
        """Return the dim matching embed_model, fall back to declared embed_dim."""
        from .embedder import model_dim
        return model_dim(self.embed_model) or self.embed_dim

    def resolve_write_token(self) -> str:
        """The effective write token. Fail-closed by default.

        Priority:
          1. An explicit ``TROVEX_WRITE_TOKEN`` (share one token across hosts).
          2. ``TROVEX_ALLOW_UNAUTH_WRITES=1`` → ``""`` (writes OPEN; caller warns).
          3. Default → a per-instance token auto-generated and persisted to
             ``<data_dir>/.write_token`` (chmod 600) and reused on later boots.

        The default means a freshly-started, network-exposed instance does NOT
        accept anonymous writes, while same-machine tooling (which can read the
        token file) keeps working without configuration.
        """
        if self.write_token:
            return self.write_token
        if self.allow_unauth_writes:
            return ""
        return _load_or_create_write_token(self.data_dir)

    def load_sources(self) -> list[Source]:
        """Resolve sources from config file, fall back to single source.

        File format (YAML):
          sources:
            - id: code
              label: my-app
              root: ~/code/my-app
            - id: vault
              label: Obsidian vault
              root: ~/obsidian/notes
        """
        if self.sources_config_path.exists():
            with self.sources_config_path.open() as f:
                data = yaml.safe_load(f) or {}
            raw = data.get("sources", [])
            sources = [Source.from_dict(d) for d in raw if d.get("root")]
            if sources:
                return sources
        # Single-source fallback (legacy behaviour).
        return [Source(id="code", label=self.project_root.name, root=self.project_root.resolve())]


def _load_or_create_write_token(data_dir: Path) -> str:
    """Return the persisted per-instance write token, creating it on first run.

    Stored at ``<data_dir>/.write_token`` with 0600 perms so only the running
    user can read it. If the file can't be persisted (e.g. a read-only data dir),
    fall back to an ephemeral in-process token — still closed, never open.
    """
    path = data_dir / WRITE_TOKEN_FILE
    try:
        if path.exists():
            tok = path.read_text(encoding="utf-8").strip()
            if tok:
                return tok
        data_dir.mkdir(parents=True, exist_ok=True)
        tok = secrets.token_urlsafe(32)
        path.write_text(tok, encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            log.warning("could not chmod 600 the write-token file at %s", path)
        return tok
    except OSError:
        log.warning(
            "could not persist a write token under %s — using an ephemeral one; "
            "set TROVEX_WRITE_TOKEN to a fixed value to write from other tools",
            data_dir,
        )
        return secrets.token_urlsafe(32)
