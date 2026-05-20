import time
from pathlib import Path

import typer
from rich.console import Console

from .config import Settings
from .indexer import Indexer
from .search import Searcher

app = typer.Typer(no_args_is_help=True, help="ctx — token-efficient .md routing")
console = Console()


@app.command()
def index(
    root: Path | None = typer.Argument(None, help="Single root override (else uses sources.yaml)"),
) -> None:
    """Scan and index all .md files. If root is given, indexes only that path.
    Otherwise reads sources from sources.yaml (or single project_root fallback)."""
    settings = Settings()
    indexer = Indexer(settings)
    if root is not None:
        settings = Settings(project_root=root.resolve())
        indexer = Indexer(settings)
        sources = [None]
        console.print(f"[bold]Indexing[/bold] {root.resolve()}")
        stats = indexer.reindex(root=root.resolve())
    else:
        sources = settings.load_sources()
        console.print(f"[bold]Indexing[/bold] {len(sources)} sources:")
        for s in sources:
            exists = "✓" if s.root.exists() else "✗"
            console.print(f"  {exists} [cyan]{s.id}[/cyan]  {s.root}")
        stats = indexer.reindex(sources=sources)

    console.print(f"[dim]Model: {settings.embed_model}[/dim]")
    console.print(
        f"[green]Done in {stats['duration_sec']:.1f}s[/green]  "
        f"added={stats['added']} updated={stats['updated']} "
        f"unchanged={stats['unchanged']} removed={stats['removed']}"
    )
    if stats.get("by_source"):
        for s in stats["by_source"]:
            console.print(
                f"  [cyan]{s['id']}[/cyan]: +{s['added']} ~{s['updated']} "
                f"={s['unchanged']} -{s['removed']}"
            )


@app.command()
def search(
    query: str = typer.Argument(..., help="Query string"),
    limit: int = typer.Option(5, "-n", "--limit"),
    summary: bool = typer.Option(False, "--summary", help="Include 50-word summaries"),
) -> None:
    """Search the index for relevant docs."""
    settings = Settings()
    searcher = Searcher(settings)
    results = searcher.search(query, limit=limit)
    output = searcher.format_with_summary(results) if summary else searcher.format_minimal(results)
    console.print(output)


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0"),
    port: int = typer.Option(8765),
) -> None:
    """Start the MCP + Web UI server."""
    import uvicorn

    from .server import build_app

    uvicorn.run(build_app(), host=host, port=port)


@app.command()
def measure(
    log_path: Path = typer.Option(
        Path.home() / ".claude" / "ctx-baseline.jsonl",
        "--log", help="Path to ctx-baseline.jsonl from the hook.",
    ),
    baseline_days: int = typer.Option(7, help="Length of baseline window."),
    current_days: int = typer.Option(7, help="Length of current window."),
) -> None:
    """Compare baseline vs current .md token consumption from hook logs."""
    from .measure import report
    console.print(report(log_path, baseline_days, current_days))


@app.command()
def stats() -> None:
    """Show indexing stats."""
    settings = Settings()
    db = open_db_for_read(settings)
    total = db.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"]
    by_status = db.execute(
        "SELECT status, COUNT(*) AS c FROM docs GROUP BY status"
    ).fetchall()
    total_tokens = db.execute(
        "SELECT COALESCE(SUM(tokens_est), 0) AS t FROM docs"
    ).fetchone()["t"]
    last_run = db.execute(
        "SELECT * FROM index_runs ORDER BY ts DESC LIMIT 1"
    ).fetchone()

    console.print(f"[bold]Total docs:[/bold] {total}")
    console.print(f"[bold]Total tokens indexed:[/bold] {total_tokens:,}")
    for r in by_status:
        console.print(f"  {r['status']}: {r['c']}")
    if last_run:
        console.print(
            f"[dim]Last index: {last_run['duration_sec']:.1f}s, "
            f"+{last_run['added']} ~{last_run['updated']} "
            f"={last_run['unchanged']} -{last_run['removed']}[/dim]"
        )


def open_db_for_read(settings: Settings):
    from .db import open_db
    return open_db(settings.data_dir / "ctx.db", settings.embed_dim)


if __name__ == "__main__":
    app()
