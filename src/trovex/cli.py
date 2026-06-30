import time
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path

import typer
from rich.console import Console

from .config import Settings
from .indexer import Indexer
from .search import Searcher

app = typer.Typer(no_args_is_help=True, help="trovex — token-efficient .md routing")
console = Console()


def _version_string() -> str:
    try:
        return _pkg_version("trovex")
    except PackageNotFoundError:  # source tree without an installed dist
        return "0.0.0"


def _version_callback(value: bool) -> None:
    if value:
        print(_version_string())
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show the trovex version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """trovex — token-efficient .md routing."""


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

    from .embedder import model_provider

    _prov = model_provider(settings.embed_model)
    _where = (
        "local ONNX, nothing leaves your machine"
        if _prov != "openai"
        else "OpenAI API — chunks are sent to OpenAI"
    )
    console.print(f"[dim]Model: {settings.embed_model} ({_where})[/dim]")
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
    savings: bool = typer.Option(
        True, "--savings/--no-savings", help="Show the per-query token-savings estimate."
    ),
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


_ALL_IFACES = {"0.0.0.0", "::", "[::]"}


def _run_server(host: str, port: int) -> None:
    """Launch uvicorn, warning loudly on an all-interfaces bind. The dashboard and
    query-log views (/usage, /insights) are read-open, so a public bind exposes your
    team's query text to anyone who can reach the port — keep it on 127.0.0.1 unless
    it sits behind an authenticated proxy."""
    import uvicorn

    from .server import build_app

    if host in _ALL_IFACES:
        console.print(
            f"[yellow]⚠ trovex is binding ALL interfaces ({host}:{port}). The dashboard "
            "and query-log views (/usage, /insights) are read-open — anyone who can reach "
            "this port sees your query text. Use 127.0.0.1 (default) or front it with an "
            "authenticated proxy for shared/remote use.[/yellow]"
        )
    uvicorn.run(build_app(), host=host, port=port)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8765),
) -> None:
    """Start the MCP + Web UI server."""
    _print_update_notice()
    _run_server(host, port)


@app.command()
def mcp() -> None:
    """Serve the MCP server over stdio — the transport .mcpb registry bundles launch.

    Same tools as `trovex serve` (HTTP), but spoken over stdin/stdout for a client
    that launches trovex directly (MCP registries / .mcpb bundles). stdout is the
    JSON-RPC channel, so ALL logging and any first-run model-download chatter are
    forced to stderr — they never corrupt the stream. Blocks until the client closes.
    """
    import contextlib
    import logging
    import sys

    from .mcp_app import mcp as mcp_server
    from .state import get_state

    # stdout belongs to JSON-RPC — pin every log to stderr.
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr, force=True)

    # Warm up the singleton state (builds the embedder; the first ever run may download
    # the ONNX model and print progress) with stdout redirected to stderr, so the
    # warm-up cannot write a byte to the JSON-RPC channel. After this stdout is pristine.
    with contextlib.redirect_stdout(sys.stderr):
        get_state()

    mcp_server.run(transport="stdio")


def _print_update_notice() -> None:
    """Light, fail-safe startup notice for long-running commands. Honors the 24h
    cache and never raises — a version check must never break or slow `serve`."""
    try:
        from .update import check_for_update, notice_line

        info = check_for_update()
        if info is not None:
            line = notice_line(info)
            if line:
                console.print(f"[dim]{line}[/dim]")
    except Exception:
        pass


@app.command()
def update(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Bypass the no-downgrade + dev-build guards (explicit reinstall/downgrade).",
    ),
    check_only: bool = typer.Option(False, "--check", help="Only check; don't run the upgrade."),
) -> None:
    """Check GitHub for a newer trovex release and upgrade it (uv tool / pip).

    Follows the fleet auto-updater contract: pinned org, semver no-downgrade,
    a dev-build guard (won't clobber a source build), and offline fail-safe.
    """
    from .update import (
        check_for_update,
        installed_version,
        is_dev_build,
        notice_line,
        upgrade_command,
    )

    installed = installed_version()
    info = check_for_update(force=True)
    if info is None:
        console.print("Couldn't reach GitHub to check for updates (offline?). Try again later.")
        return
    if check_only:
        console.print(notice_line(info) or f"trovex {info.installed} is up to date.")
        return
    if not force:
        if is_dev_build(installed):
            console.print(
                f"trovex {installed} looks like a dev/source build — refusing to auto-update "
                "(it would clobber local work). Use --force to override."
            )
            return
        if not info.newer:
            console.print(f"trovex {info.installed} is up to date.")
            return
    console.print(notice_line(info) or f"Reinstalling trovex {info.latest} (--force).")
    cmd = upgrade_command()
    console.print(f"Running: {' '.join(cmd)}")
    import subprocess

    try:
        subprocess.run(cmd, check=False)  # noqa: S603 — pinned uv/pip upgrade command
    except (OSError, ValueError) as e:
        console.print(f"[red]Upgrade failed:[/red] {e}\nRun it manually: {' '.join(cmd)}")
        return
    console.print(
        f"Done. Restart `trovex serve` to load the new version, then `trovex update --check` "
        f"to confirm v{info.latest}."
    )


@app.command()
def measure(
    log_path: Path = typer.Option(
        Path.home() / ".claude" / "trovex-baseline.jsonl",
        "--log",
        help="Path to trovex-baseline.jsonl from the hook.",
    ),
    baseline_days: int = typer.Option(7, help="Length of baseline window."),
    current_days: int = typer.Option(7, help="Length of current window."),
) -> None:
    """Compare baseline vs current .md token consumption from hook logs."""
    from .measure import report

    console.print(report(log_path, baseline_days, current_days))


_DEFAULT_QUERIES = [
    "how do I install this",
    "how do I run the tests",
    "how do I configure it",
    "what is the architecture",
    "how do I deploy",
    "what are the main commands or API",
    "how do I contribute",
    "what license is this under",
]


def _load_queries(path: Path | None) -> list[str]:
    """Queries from a file (one per line) or the built-in starter set."""
    if path is None:
        return list(_DEFAULT_QUERIES)
    try:
        return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except OSError:
        return []


def _load_labels(path: Path) -> list:
    """Ground-truth for --retrieval: `query<TAB>expected-path[,path2,...]` per line.

    TAB (or `|`) separates the query from the comma-list of doc paths that correctly
    answer it; `#` comments and blanks are skipped. Returns LabeledQuery objects.
    """
    from .retrieval_eval import LabeledQuery

    out: list = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        sep = "\t" if "\t" in line else ("|" if "|" in line else None)
        if sep is None:
            continue  # no separator → not a label line
        query, rest = line.split(sep, 1)
        relevant = [p.strip() for p in rest.split(",") if p.strip()]
        if query.strip() and relevant:
            out.append(LabeledQuery(query.strip(), relevant))
    return out


def _bench_json(result) -> str:
    """Machine-readable JSON of a BenchResult / EvalReport (both dataclasses)."""
    import json
    from dataclasses import asdict

    return json.dumps(asdict(result), default=str)


@app.command()
def bench(
    repo: Path = typer.Argument(..., help="Repo/dir with .md docs to benchmark."),
    queries: Path | None = typer.Option(
        None,
        "--queries",
        help="File of doc-lookup questions, one per line (default: a built-in starter set).",
    ),
    eval_mode: bool = typer.Option(
        False,
        "--eval",
        help="Full answer+judge A/B (needs OPENAI_API_KEY); default is the cheap token-model.",
    ),
    latency: bool = typer.Option(
        False,
        "--latency",
        help="Measure query LATENCY (embed+knn+score) over the queries instead of token savings.",
    ),
    repeats: int = typer.Option(
        20, "--repeats", help="Repeats per query for --latency (more = steadier percentiles)."
    ),
    retrieval: bool = typer.Option(
        False,
        "--retrieval",
        help="Score retrieval QUALITY (hit@k/MRR/recall@k) over a --labels file, no LLM.",
    ),
    labels: Path | None = typer.Option(
        None,
        "--labels",
        help="For --retrieval: `query<TAB>expected-path[,path2]` per line (the ground truth).",
    ),
    k: int = typer.Option(3, "--k", help="Baseline candidate count (top-k read / retrieval window)."),
    model: str = typer.Option("gpt-5.4-mini", help="LLM for --eval (answers + judges)."),
    json_out: bool = typer.Option(
        False, "--json", help="Emit machine-readable JSON (median, spread, per-query/category)."
    ),
) -> None:
    """Benchmark trovex on YOUR repo — the method is the claim, run it yourself.

    Default = the token-accounting MODEL (no LLM, instant): the cost of reading the 1 routed
    canonical doc vs the top-k candidates. --eval = the full answer+judge A/B counted at EQUAL
    task-success (needs a key). --latency = the sqlite-vec query speed (p50/p95/max ms), no LLM.
    --retrieval = did the router return the RIGHT doc (hit@k/MRR/recall@k) over a --labels
    ground-truth file, no LLM. Reports the distribution (median + spread), not a max.
    """
    import os
    import tempfile

    from .embedder import embedder_from_settings

    # Check the key BEFORE the (slow) index, so --eval without a key fails fast.
    # --latency / --retrieval never need a key (no LLM), so don't gate them.
    llm_eval = eval_mode and not latency and not retrieval
    key = os.environ.get("OPENAI_API_KEY") if llm_eval else None
    if llm_eval and not key:
        console.print("[red]--eval needs OPENAI_API_KEY in your environment.[/red]")
        raise typer.Exit(1)

    labeled: list = []
    qs: list[str] = []
    if retrieval:
        if labels is None:
            console.print("[red]--retrieval needs --labels FILE[/red] (query<TAB>expected-path).")
            raise typer.Exit(1)
        labeled = _load_labels(labels)
        if not labeled:
            console.print(
                f"[red]No labels in {labels}.[/red] Format: query<TAB>expected-path[,path2]."
            )
            raise typer.Exit(1)
    else:
        qs = _load_queries(queries)
        if not qs:
            console.print("[red]No queries.[/red] Provide --queries FILE (one question per line).")
            raise typer.Exit(1)

    with tempfile.TemporaryDirectory() as td:
        settings = Settings(data_dir=Path(td), sources_config_path=Path(td) / "none.yaml")
        emb = embedder_from_settings(settings)
        stats = Indexer(settings, embedder=emb).reindex(root=repo.resolve())
        if not stats.get("added"):
            console.print(f"[yellow]No .md indexed under {repo}.[/yellow]")
            raise typer.Exit(1)
        searcher = Searcher(settings, embedder=emb)

        if retrieval:
            from .retrieval_eval import evaluate_retrieval, format_retrieval_stats

            rstats = evaluate_retrieval(searcher, labeled, k=k)
            if json_out:
                print(_bench_json(rstats))
            else:
                console.print(
                    f"[bold]retrieval quality[/bold] · {len(labeled)} labelled queries "
                    f"on {repo.name}\n{format_retrieval_stats(rstats)}"
                )
        elif latency:
            from .query_latency import format_latency_stats, measure_query_latency

            stats = measure_query_latency(searcher, qs, repeats=repeats)
            if json_out:
                print(_bench_json(stats))
            else:
                console.print(
                    f"[bold]query-latency[/bold] · {len(qs)} queries × {repeats} on "
                    f"{repo.name} ({stats.n} samples)\n{format_latency_stats(stats)}"
                )
        elif eval_mode:
            from openai import OpenAI

            from .eval_bench import EvalQuery, format_eval_report, run_eval
            from .eval_llm import make_answer_fn, make_content_fn, make_judge_fn

            client = OpenAI(api_key=key, timeout=60.0)
            report = run_eval(
                [EvalQuery(q, "user") for q in qs],
                searcher,
                answer_fn=make_answer_fn(client, model),
                judge_fn=make_judge_fn(client, model),
                content_fn=make_content_fn(),
                baseline_k=k,
            )
            if json_out:
                print(_bench_json(report))
            else:
                console.print(
                    format_eval_report(
                        report,
                        query_source=f"{len(qs)} queries on {repo.name} (answer+judge, {model})",
                    )
                )
        else:
            from .benchmark import format_report, run_benchmark

            r = run_benchmark(searcher, qs, limit=max(k, 5))
            if json_out:
                print(_bench_json(r))
            else:
                console.print(
                    format_report(
                        r,
                        repo=str(repo),
                        query_source=f"{len(qs)} queries (token-accounting MODEL — add --eval for the answer-quality A/B)",
                    )
                )


@app.command()
def stats() -> None:
    """Show indexing stats."""
    settings = Settings()
    db = open_db_for_read(settings)
    total = db.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"]
    by_status = db.execute("SELECT status, COUNT(*) AS c FROM docs GROUP BY status").fetchall()
    total_tokens = db.execute("SELECT COALESCE(SUM(tokens_est), 0) AS t FROM docs").fetchone()["t"]
    last_run = db.execute("SELECT * FROM index_runs ORDER BY ts DESC LIMIT 1").fetchone()

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
def prune(
    status: str = typer.Option("duplicate", help="Doc status to prune."),
    execute: bool = typer.Option(False, "--execute", help="Actually delete (default: dry-run)."),
) -> None:
    """Prune docs by status (default: near-duplicates) via the proper cascade delete.

    Dry-run by default: lists each doomed doc + the canonical it duplicates, so you
    can sanity-check the kept set first. Pass --execute to delete each via the store's
    cascade (chunks, vec_chunks, chunks_fts, doc_versions, vec_docs, docs) — no orphan
    vec rows. Near-dupes won't be recreated by a re-index (they matched existing canon).
    Take a backup first (cp data_dir/trovex.db ...).
    """
    from .store import SqliteStore

    settings = Settings()
    store = SqliteStore(settings)
    rows = store.db.execute(
        """SELECT d.id, d.ext_id, d.title,
                  c.id AS canon_id, c.title AS canon_title
           FROM docs d LEFT JOIN docs c ON c.id = d.dup_of_id
           WHERE d.status = ?
           ORDER BY d.id""",
        (status,),
    ).fetchall()
    if not rows:
        console.print(f"[green]No docs with status='{status}'. Nothing to prune.[/green]")
        return

    console.print(f"[bold]{len(rows)} doc(s) with status='{status}'[/bold] (each → its canonical):")
    orphans = 0
    for r in rows:
        if r["canon_id"]:
            canon = f"#{r['canon_id']} [dim]{(r['canon_title'] or '')[:40]}[/dim]"
        else:
            canon = "[red]NO canonical (dup_of_id null/missing)[/red]"
            orphans += 1
        console.print(
            f"  #{r['id']} {r['ext_id'] or '[dim](no ext_id)[/dim]'}  [dim]{(r['title'] or '')[:40]}[/dim]  → {canon}"
        )
    if orphans:
        console.print(
            f"[yellow]{orphans} have no resolvable canonical — review before --execute.[/yellow]"
        )

    if not execute:
        console.print(
            f"\n[yellow]DRY-RUN.[/yellow] Re-run with [cyan]--execute[/cyan] to delete these {len(rows)}."
        )
        return

    deleted = 0
    for r in rows:
        if store.delete_by_id(r["id"]):
            deleted += 1
    console.print(
        f"[green]Deleted {deleted}/{len(rows)} '{status}' docs.[/green] Run [cyan]trovex stats[/cyan] to verify."
    )


@app.command()
def migrate(
    source: str = typer.Option(
        None, "--source", help="Only this source id (else all file sources)."
    ),
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
        ext_id = "mig_" + hashlib.sha1(f"{r['source_id']}|{r['path']}".encode()).hexdigest()[:16]
        kind = "note" if r["source_id"].startswith("vault") else "reference"
        buf.append(
            {
                "content": content,
                "kind": kind,
                "ext_id": ext_id,
                "title": _extract_title(content),
            }
        )
        by_src[r["source_id"]] = by_src.get(r["source_id"], 0) + 1
        migrated += 1
        if len(buf) >= chunk:
            flush()
    flush()

    for sid, n in sorted(by_src.items()):
        console.print(f"  [cyan]{sid}[/cyan]: {n}")
    verb = "Wrote" if execute else "Would write"
    console.print(
        f"[green]{verb} {migrated}[/green] docs to store · skipped(empty/unreadable)={skipped}"
    )
    if not execute:
        console.print(
            "[dim]Re-run with --execute to write, then drop the source(s) from sources.yaml.[/dim]"
        )


def _fmt_date(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _scan_dir(settings, root: Path, label: str):
    """Gather + resolve every .md under root. Returns (paths, files, skipped)."""
    from . import onboarding

    paths = onboarding.gather(
        root, set(settings.ignore_dirs), max_bytes=settings.max_file_size_bytes
    )
    files = []
    for p in paths:
        f = onboarding.build(p, root, label)
        if f is not None:
            files.append(f)
    return paths, files, len(paths) - len(files)


def _print_scan(files, skipped: int) -> None:
    """The date/source summary shared by `import` preview and the `onboard` wizard."""
    dates = sorted(f.mtime for f in files)
    by_source: dict[str, int] = {}
    for f in files:
        by_source[f.date_source] = by_source.get(f.date_source, 0) + 1
    console.print(
        f"[bold]{len(files)}[/bold] docs · dated "
        f"[cyan]{_fmt_date(dates[0])}[/cyan] → [cyan]{_fmt_date(dates[-1])}[/cyan]  "
        f"[dim](skipped {skipped} empty/unreadable)[/dim]"
    )
    console.print(
        "  dates from: "
        + "  ".join(f"{src}={n}" for src, n in sorted(by_source.items(), key=lambda x: -x[1]))
    )


def _write_files(settings, files, kind: str, chunk: int) -> int:
    """Embed + write resolved files into the store in batches. Returns count written."""
    from .store import SqliteStore

    store = SqliteStore(settings)
    buf: list[dict] = []
    written = 0
    for f in files:
        buf.append(
            {
                "content": f.content,
                "kind": kind or None,
                "ext_id": f.ext_id,
                "title": f.title,
                "mtime": f.mtime,
                "tags": f.tags,
            }
        )
        if len(buf) >= chunk:
            store.put_batch(buf, embed_chunks=True)
            written += len(buf)
            buf.clear()
            console.print(f"[dim]  …{written}/{len(files)}[/dim]")
    if buf:
        store.put_batch(buf, embed_chunks=True)
        written += len(buf)
    return written


@app.command(name="import")
def import_(
    root: Path = typer.Argument(..., help="Directory to import all .md from."),
    source: str = typer.Option(
        None, "--source", help="Source label / tag (default: the directory name)."
    ),
    kind: str = typer.Option(
        "reference", "--kind", help="Lifecycle kind for imported docs ('' for living)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview what would import (dates, counts) — write nothing."
    ),
    chunk: int = typer.Option(100, help="Embedding batch size."),
) -> None:
    """Import every .md under ROOT into the trovex store, dated from its history.

    Non-interactive / scriptable — for the guided first-run flow use `onboard`.
    Resolves each file's real date (git first-commit → frontmatter date → file
    mtime), tags it from its folder path, writes it into the trovex-owned store.
    Re-runnable: ext_id is derived from the path, so re-importing updates in place.
    """
    root = root.expanduser().resolve()
    if not root.is_dir():
        console.print(f"[red]Not a directory:[/red] {root}")
        raise typer.Exit(1)
    label = (source or root.name).strip().strip("/").lower() or "import"

    settings = Settings()
    console.print(
        f"[bold]Import[/bold] {root}  →  store (source [cyan]{label}[/cyan])  "
        f"{'[yellow]dry-run[/yellow]' if dry_run else ''}"
    )
    paths, files, skipped = _scan_dir(settings, root, label)
    console.print(f"[dim]Found {len(paths)} markdown files. Resolving dates…[/dim]")

    if not files:
        console.print("[yellow]Nothing to import[/yellow] (no readable, non-empty .md).")
        return
    _print_scan(files, skipped)

    if dry_run:
        console.print("\n[dim]Sample (newest first):[/dim]")
        for f in sorted(files, key=lambda x: -x.mtime)[:8]:
            console.print(
                f"  [cyan]{_fmt_date(f.mtime)}[/cyan] [dim]{f.date_source:11}[/dim] {f.rel}"
            )
        console.print("\n[dim]Re-run without --dry-run to write to the store.[/dim]")
        return

    written = _write_files(settings, files, kind, chunk)
    console.print(
        f"\n[green]Imported {written} docs[/green] into the store, dated + tagged + queryable."
    )
    console.print(
        "[bold]Next[/bold] — query them: "
        '[cyan]uv run trovex search "..."[/cyan]  '
        "[dim]or browse at[/dim] [cyan]uv run trovex serve[/cyan] → http://localhost:8765"
    )


@app.command()
def onboard() -> None:
    """Guided first run: pick a folder, preview the dated docs, import, start serving.

    The friendly front door to `import` — walks you through choosing a directory,
    shows what would land (count, date range, where each date came from), confirms
    before writing, then offers to launch the server. Everything it does is also
    available non-interactively via `import` / `serve`.
    """
    console.print("[bold]trovex onboard[/bold] — import your markdown, dated from its history.\n")
    settings = Settings()

    while True:
        raw = typer.prompt("Folder to import .md from", default=str(Path.cwd()))
        root = Path(raw).expanduser().resolve()
        if root.is_dir():
            break
        console.print(f"[red]Not a directory:[/red] {root}")

    default_label = (root.name or "import").strip().strip("/").lower()
    label = (typer.prompt("Source label (tag)", default=default_label)).strip().strip(
        "/"
    ).lower() or default_label

    console.print(f"\n[dim]Scanning {root} …[/dim]")
    paths, files, skipped = _scan_dir(settings, root, label)
    if not files:
        console.print("[yellow]No readable, non-empty .md found here.[/yellow] Nothing to do.")
        return
    console.print(f"[dim]Found {len(paths)} files.[/dim]")
    _print_scan(files, skipped)
    console.print("\n[dim]Newest first:[/dim]")
    for f in sorted(files, key=lambda x: -x.mtime)[:8]:
        console.print(f"  [cyan]{_fmt_date(f.mtime)}[/cyan] [dim]{f.date_source:11}[/dim] {f.rel}")

    if not typer.confirm(f"\nImport these {len(files)} docs into the store?", default=True):
        console.print("[dim]Aborted — nothing written.[/dim]")
        return
    kind = (
        typer.prompt("Kind (lifecycle tag, blank for living docs)", default="reference")
    ).strip()

    console.print()
    written = _write_files(settings, files, kind, 100)
    console.print(f"\n[green]Imported {written} docs[/green], dated + tagged + queryable.")

    if not typer.confirm("Start the server now?", default=True):
        console.print("[dim]Later:[/dim] [cyan]uv run trovex serve[/cyan] → http://localhost:8765")
        return
    console.print(
        f"[dim]Serving at[/dim] [cyan]http://localhost:{settings.port}[/cyan] "
        "[dim](Ctrl-C to stop)…[/dim]"
    )
    _run_server(settings.host, settings.port)


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
def retitle(
    execute: bool = typer.Option(False, "--execute", help="Apply (default: dry-run)."),
) -> None:
    """Re-derive every store doc's title from its content with the current rule
    (H1 -> any heading -> frontmatter title: -> first line). Fixes docs that
    indexed as 'Untitled' before the fallback existed. No doc rewrite."""
    from .store import SqliteStore, _extract_title

    settings = Settings()
    store = SqliteStore(settings)
    rows = store.db.execute(
        "SELECT id, title, content FROM docs WHERE content IS NOT NULL"
    ).fetchall()
    changed: list[tuple[int, str]] = []
    for r in rows:
        new = _extract_title(r["content"])
        if new != (r["title"] or ""):
            changed.append((r["id"], new))
            if execute:
                store.db.execute("UPDATE docs SET title = ? WHERE id = ?", (new, r["id"]))
    if execute:
        store.db.commit()
    mode = "EXECUTE" if execute else "dry-run"
    console.print(f"[bold]retitle[/bold] ({mode}): {len(changed)}/{len(rows)} re-derived")
    for _id, new in changed[:20]:
        console.print(f"  #{_id} -> [dim]{new[:60]}[/dim]")


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
    "reports": "report",
    "report": "report",
    "audit": "audit",
    "audits": "audit",
    "decision": "decision",
    "decisions": "decision",
    "adr": "decision",
    "spec": "spec",
    "specs": "spec",
    "self-learning": "self-learning",
    "learnings": "self-learning",
    "incident": "incident",
    "incidents": "incident",
    "runbook": "runbook",
    "runbooks": "runbook",
    "plan": "plan",
    "plans": "plan",
    "log": "log",
    "logs": "log",
    "guide": "guide",
    "guides": "guide",
}
_FACET_DOMAIN = {
    "accounting",
    "payroll",
    "auth",
    "infra",
    "iodd",
    "regulation",
    "kb",
    "zefix",
    "ocr",
    "minio",
    "clients",
    "scripts",
    "banking",
    "debtors",
    "suppliers",
    "outline",
    "freescout",
    "loki",
    "gitnexus",
    "supabase",
    "qdrant",
    "neo4j",
    "security",
    "frontend",
    "backend",
    "data",
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
        f"[green]recall@1 = {hit1 / scored:.0%}[/green]  recall@{k} = {hitk / scored:.0%}"
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
    rows = store.db.execute("SELECT id FROM docs WHERE source_id = 'trovex'").fetchall()
    added = 0
    for r in rows:
        doc_id = r["id"]
        tags = [
            t["tag"]
            for t in store.db.execute("SELECT tag FROM doc_tags WHERE doc_id = ?", (doc_id,))
        ]
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
