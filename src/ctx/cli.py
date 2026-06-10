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


@app.command()
def migrate(
    source: str = typer.Option(None, "--source", help="Only this source id (else all file sources)."),
    execute: bool = typer.Option(False, "--execute", help="Write to the store (default: dry-run)."),
    chunk: int = typer.Option(100, help="Embedding batch size."),
) -> None:
    """Migrate file-backed docs into the ctx-owned store (full-ctx move).

    Reads each indexed file doc and writes it into the store under a stable,
    idempotent ext_id (re-runnable). Dry-run by default. After verifying,
    remove the migrated source(s) from sources.yaml so they stop being scanned.
    """
    import hashlib

    from .store import SqliteStore, _extract_title

    settings = Settings()
    store = SqliteStore(settings)
    sql = "SELECT source_id, path, absolute_path FROM docs WHERE source_id != 'ctx'"
    params: list = []
    if source:
        sql += " AND source_id = ?"
        params.append(source)
    rows = store.db.execute(sql, params).fetchall()

    mode = "EXECUTE" if execute else "dry-run"
    console.print(f"[bold]Migrate -> store[/bold]  ({mode})  candidates: {len(rows)}")

    by_src: dict[str, int] = {}
    buf: list[dict] = []
    migrated = skipped = 0

    def flush() -> None:
        if buf and execute:
            store.put_batch(buf)
        buf.clear()

    for r in rows:
        try:
            content = Path(r["absolute_path"]).read_text(encoding="utf-8", errors="replace")
        except OSError:
            skipped += 1
            continue
        if not content.strip():
            skipped += 1
            continue
        ext_id = "mig_" + hashlib.sha1(
            f'{r["source_id"]}|{r["path"]}'.encode()
        ).hexdigest()[:16]
        kind = "note" if r["source_id"].startswith("vault") else "reference"
        buf.append({
            "content": content, "kind": kind, "ext_id": ext_id,
            "title": _extract_title(content),
        })
        by_src[r["source_id"]] = by_src.get(r["source_id"], 0) + 1
        migrated += 1
        if len(buf) >= chunk:
            flush()
    flush()

    for sid, n in sorted(by_src.items()):
        console.print(f"  [cyan]{sid}[/cyan]: {n}")
    verb = "Wrote" if execute else "Would write"
    console.print(
        f"[green]{verb} {migrated}[/green] docs to store · "
        f"skipped(empty/unreadable)={skipped}"
    )
    if not execute:
        console.print("[dim]Re-run with --execute to write, then drop the source(s) "
                      "from sources.yaml.[/dim]")


@app.command(name="backfill-chunks")
def backfill_chunks(batch: int = typer.Option(200, help="Embedding batch size.")) -> None:
    """(Re)chunk + embed every store-held doc into vec_chunks. Idempotent."""
    from .store import SqliteStore

    settings = Settings()
    store = SqliteStore(settings)
    docs = store.db.execute(
        "SELECT id, content, title FROM docs WHERE content IS NOT NULL"
    ).fetchall()
    pairs: list = []
    n = 0
    for d in docs:
        pairs.extend(store._insert_chunks(d["id"], d["content"], d["title"] or ""))
        n += 1
        if len(pairs) >= batch:
            store._embed_chunks(pairs)
            store.db.commit()
            pairs = []
    if pairs:
        store._embed_chunks(pairs)
        store.db.commit()
    total = store.db.execute("SELECT COUNT(*) AS c FROM chunks").fetchone()["c"]
    console.print(f"[green]Backfilled {n} docs -> {total} chunks[/green]")


@app.command()
def enrich() -> None:
    """Re-derive tags + provenance + titles for migrated docs from the source files.

    Reads the original sources (sources.yaml.bak), recomputes each migrated doc's
    mig_ id, and sets: tags from its folder path, origin = source/path, and a
    title from the filename when the doc had none.
    """
    import hashlib

    import yaml

    from .store import SqliteStore

    settings = Settings()
    store = SqliteStore(settings)
    bak = settings.data_dir / "sources.yaml.bak"
    if not bak.exists():
        console.print("[red]no sources.yaml.bak — nothing to enrich from[/red]")
        raise typer.Exit(1)
    sources = (yaml.safe_load(bak.read_text()) or {}).get("sources", [])

    enriched = retitled = 0
    for src in sources:
        sid = str(src.get("id", "")).strip()
        root = Path(str(src["root"])).expanduser().resolve()
        if not root.exists():
            continue
        for ext in ("md", "mdx", "markdown"):
            for p in root.rglob(f"*.{ext}"):
                try:
                    rel = str(p.relative_to(root))
                except ValueError:
                    continue
                ext_id = "mig_" + hashlib.sha1(f"{sid}|{rel}".encode()).hexdigest()[:16]
                row = store.db.execute(
                    "SELECT id, title, kind FROM docs WHERE ext_id = ?", (ext_id,)
                ).fetchone()
                if not row:
                    continue
                doc_id = row["id"]
                folders = [f for f in Path(rel).parent.parts if f not in (".", "")]
                tags = [sid, *folders]
                if row["kind"]:
                    tags.append(f"kind/{row['kind']}")
                store._set_tags(doc_id, tags)
                store.db.execute(
                    "UPDATE docs SET origin = ? WHERE id = ?", (f"{sid}/{rel}", doc_id)
                )
                if not row["title"] or row["title"] == "Untitled":
                    nice = p.stem.replace("_", " ").replace("-", " ").strip().title()
                    store.db.execute(
                        "UPDATE docs SET title = ? WHERE id = ?", (nice or rel, doc_id)
                    )
                    retitled += 1
                enriched += 1
    store.db.commit()
    console.print(f"[green]Enriched {enriched} docs[/green] (retitled {retitled})")


def open_db_for_read(settings: Settings):
    from .db import open_db
    return open_db(settings.data_dir / "ctx.db", settings.embed_dim)


if __name__ == "__main__":
    app()
