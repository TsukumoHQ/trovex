from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Shared write token (env TROVEX_WRITE_TOKEN). Empty = open (no gate).
    # Gates trovex_write / trovex_tag / trovex_delete + the /api write endpoints.
    write_token: str = ""

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

    def load_sources(self) -> list[Source]:
        """Resolve sources from config file, fall back to single source.

        File format (YAML):
          sources:
            - id: code
              label: synergix_prod
              root: /home/synxadmin/synergix_prod
            - id: vault-prod
              label: Obsidian — prod
              root: /home/synxadmin/obsidian/synergix-prod
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
