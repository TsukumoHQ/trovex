from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CTX_", extra="ignore")

    # Paths
    project_root: Path = Path.cwd()
    data_dir: Path = Path.home() / ".ctx-data"

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
