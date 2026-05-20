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
    model_config = SettingsConfigDict(env_prefix="CTX_", extra="ignore")

    # Paths
    project_root: Path = Path.cwd()  # legacy, kept for back-compat
    data_dir: Path = Path.home() / ".ctx-data"

    # Multi-source: file at sources_config_path takes precedence; otherwise
    # falls back to a single source built from project_root.
    sources_config_path: Path = Path.home() / ".ctx-data" / "sources.yaml"

    # Embedding (multilingual small, 384 dims, ~120MB)
    embed_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embed_dim: int = 384

    # Indexing
    max_file_size_bytes: int = 1_000_000
    ignore_dirs: list[str] = [
        "node_modules", ".venv", "venv", ".git", "dist", "build",
        ".next", ".nuxt", "target", "vendor", "__pycache__",
        ".pytest_cache", ".ruff_cache", "fastembed_cache", ".ctx-cache",
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

    # Ranking weights
    freshness_half_life_days: float = 90.0

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
