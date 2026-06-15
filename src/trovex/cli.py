import time
from pathlib import Path

import typer
from rich.console import Console

from .config import Settings
from .indexer import Indexer
from .search import Searcher

app = typer.Typer(no_args_is_help=True, help="trovex — token-efficient .md routing")
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

    # Honest empty-state: don't send a first-run user to a query that can't match.
    indexed = stats["added"] + stats["updated"] + stats["unchanged"]
    if indexed == 0:
        console.print(
            "\n[yellow]No markdown to index here.[/yellow] Point trovex at a repo "
            "with [cyan].md[/cyan] docs: [cyan]uv run trovex index /path/to/repo[/cyan]"
        )
        return

    # Point first-run users straight at the aha: the savings number on query 1.
    console.print("\n[bold]Next[/bold] — ask a question, see the tokens saved:")
    console.print(
        '  [cyan]uv run trovex search "how do we deploy?"[/cyan]'
        "  [dim](use a real question about your repo)[/dim]"
    )
    console.print(
        "[dim]Then wire it into your agent — [/dim][cyan]uv run trovex serve[/cyan]"
        "[dim] — and savings add up on the dashboard at http://localhost:8765/savings[/dim]"
    )


@app.command()
def search(
    query: str = typer.Argument(..., help="Query string"),
    limit: int = typer.Option(5, "-n", "--limit"),
    summary: bool = typer.Option(False, "--summary", help="Include 50-word summaries"),
    savings: bool = typer.Option(True, "--savings/--no-savings", help="Show the per-query token-savings estimate."),
) -> None:
    """Search the index for relevant docs."""
    settings = Settings()
    searcher = Searcher(settings)
    results = searcher.search(query, limit=limit)
    output = searcher.format_with_summary(results) if summary else searcher.format_minimal(results)
    console.print(output)
    if not results:
        console.print(
            "[dim]No match. Try different words, or re-run [/dim]"
            "[cyan]uv run trovex index <repo>[/cyan][dim] if your docs changed.[/dim]"
        )
        return
    if savings:
        s = searcher.savings_estimate(results)
        if s and s["saved"] > 0:
            console.print(
                f"\n[green]≈ {s['saved']:,} tokens saved[/green] this query  "
                f"[dim]· read 1 canonical doc (~{s['actual_read']:,} tok) instead of "
                f"the top {s['compared']} (~{s['would_have_read']:,} tok) · {s['ratio']:.0%} less · estimate[/dim]"
            )


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
        Path.home() / ".claude" / "trovex-baseline.jsonl",
        "--log", help="Path to trovex-baseline.jsonl from the hook.",
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
    """Migrate file-backed docs into the trovex-owned store (full-trovex move).

    Reads each indexed file doc and writes it into the store under a stable,
    idempotent ext_id (re-runnable). Dry-run by default. After verifying,
    remove the migrated source(s) from sources.yaml so they stop being scanned.
    """
    import hashlib

    from .store import SqliteStore, _extract_title

    settings = Settings()
    store = SqliteStore(settings)
    sql = "SELECT source_id, path, absolute_path FROM docs WHERE source_id != 'trovex'"
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


_FACET_TYPE = {
    "reports": "report", "report": "report", "audit": "audit", "audits": "audit",
    "decision": "decision", "decisions": "decision", "adr": "decision",
    "spec": "spec", "specs": "spec", "self-learning": "self-learning",
    "learnings": "self-learning", "incident": "incident", "incidents": "incident",
    "runbook": "runbook", "runbooks": "runbook", "plan": "plan", "plans": "plan",
    "log": "log", "logs": "log", "guide": "guide", "guides": "guide",
}
_FACET_DOMAIN = {
    "accounting", "payroll", "auth", "infra", "iodd", "regulation", "kb", "zefix",
    "ocr", "minio", "clients", "scripts", "banking", "debtors", "suppliers",
    "outline", "freescout", "loki", "gitnexus", "supabase", "qdrant", "neo4j",
    "security", "frontend", "backend", "data",
}
_FACET_OWNER = {"cto", "cos", "founder"}


def _pick_query(content: str) -> str:
    import re
    text = re.sub(r"^---.*?---", "", content, flags=re.DOTALL)
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith(("#", "-", "*", "|", "`")) and len(s) > 40:
            return s[:200]
    return ""


@app.command()
def eval(n: int = 40, k: int = 5) -> None:  # noqa: A001
    """Retrieval eval: sample docs, query with a sentence from each, measure recall.

    recall@1 = top passage is from the right doc; recall@k = right doc in top k.
    A sanity check so we stop flying blind on retrieval quality.
    """
    import random

    from .store import SqliteStore

    settings = Settings()
    store = SqliteStore(settings)
    docs = store.db.execute(
        "SELECT ext_id, content, title FROM docs WHERE source_id='trovex' AND content IS NOT NULL"
    ).fetchall()
    sample = random.sample(docs, min(n, len(docs)))
    hit1 = hitk = scored = 0
    for d in sample:
        q = _pick_query(d["content"]) or (d["title"] or "")
        if not q:
            continue
        ids = [h["ext_id"] for h in store.search_chunks(q, limit=k)]
        scored += 1
        if ids and ids[0] == d["ext_id"]:
            hit1 += 1
        if d["ext_id"] in ids:
            hitk += 1
    if not scored:
        console.print("[red]no scorable docs[/red]")
        return
    console.print(
        f"[bold]Retrieval eval[/bold] (n={scored})  "
        f"[green]recall@1 = {hit1/scored:.0%}[/green]  recall@{k} = {hitk/scored:.0%}"
    )


@app.command()
def backup() -> None:
    """Snapshot trovex.db into data_dir/backups/ (consistent online copy, keeps 14)."""
    from .backup import make_backup
    settings = Settings()
    dest = make_backup(settings.data_dir / "trovex.db", settings.data_dir)
    console.print(f"[green]Backed up[/green] -> {dest}")


@app.command()
def facet() -> None:
    """Promote organic folder tags into faceted tags (type/ owner/ domain/).

    Additive — keeps the originals. type/report, owner/backend-lead,
    domain/accounting, etc. so the store can filter + group by facet.
    """
    from .store import SqliteStore

    settings = Settings()
    store = SqliteStore(settings)
    rows = store.db.execute(
        "SELECT id FROM docs WHERE source_id = 'trovex'"
    ).fetchall()
    added = 0
    for r in rows:
        doc_id = r["id"]
        tags = [t["tag"] for t in store.db.execute(
            "SELECT tag FROM doc_tags WHERE doc_id = ?", (doc_id,))]
        facets: set[str] = set()
        for t in tags:
            if t in _FACET_TYPE:
                facets.add(f"type/{_FACET_TYPE[t]}")
            if t in _FACET_DOMAIN:
                facets.add(f"domain/{t}")
            if t.endswith("-lead") or t in _FACET_OWNER:
                facets.add(f"owner/{t}")
        for ft in facets:
            cur = store.db.execute(
                "INSERT OR IGNORE INTO doc_tags(doc_id, tag) VALUES (?, ?)",
                (doc_id, ft),
            )
            added += cur.rowcount
    store.db.commit()
    console.print(f"[green]Added {added} facet tags[/green]")


def open_db_for_read(settings: Settings):
    from .db import open_db
    return open_db(settings.data_dir / "trovex.db", settings.embed_dim)


if __name__ == "__main__":
    app()
