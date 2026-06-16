# Comparison prose: batch 2 (Continue, Aider, Cody, Pieces, Claude Projects)

*Owner: content-lead · comparison copy for geo-lead to render as `/vs/<slug>/` pages
(matching the batch-1 layout: short answer → what it is → where they differ → table →
when the other is the right choice → FAQ). Geo-lead owns the HTML/JSON-LD; this is the prose.*

**Honesty rules applied:** describe each tool fairly at the level we're sure of, no strawman,
name what it's genuinely good at, and be explicit that several are **complementary** (they do
a different job, not a worse version of trovex's). Many of these aren't direct competitors;
the honest framing is "different tool, here's the boundary." The only trovex proof figure is
the real ~60% fewer tokens per doc lookup. Where a tool's specifics vary by version, hedge
("as of 2026") rather than assert. trovex's lane throughout: **the canonical, freshness-marked
doc that answers a query, served locally to a coding agent over MCP, with a shared write path.**

---

## trovex vs Continue

**Short answer:** Continue is an open-source AI coding assistant you run in your editor
(VS Code, JetBrains) with the model and context providers you choose. trovex isn't an
assistant; it's a context source that serves your agent the one canonical doc for a query.
They sit at different layers, and Continue can consume a source like trovex rather than
compete with it.

**What Continue is:** an open-source IDE extension that puts chat, autocomplete, and editing
in your editor, with pluggable models and configurable context providers. It's a strong,
customizable front-end for working with an LLM on your code.

**Where they differ:** Continue is the interface and orchestration; trovex is one of the
things it can pull context from. Continue's built-in context (open files, codebase indexing)
gives the model material to work with, but it doesn't mark one doc canonical-and-current with
a freshness signal, or close a shared write loop across a team. trovex does exactly that, over
MCP, for the doc slice.

**When Continue is the right choice:** you want an open, model-agnostic assistant in your
editor. Use it; then point it at trovex (or another MCP server) when you also want one
canonical, freshness-marked answer for your docs instead of raw codebase indexing.

## trovex vs Aider

**Short answer:** Aider is a terminal-based AI pair programmer that edits your code through
an LLM, using a git-aware map of the repo. trovex doesn't edit code; it answers "which doc is
current?" cheaply. Different jobs, and they can run side by side.

**What Aider is:** a CLI tool that pairs with you to write and refactor code, applies changes
as git commits, and builds a repo map so the model has structural context. It's excellent at
the edit loop.

**Where they differ:** Aider's repo map is about *code structure for editing*; trovex is about
*which markdown doc is the canonical answer to a question*, served at the section level with a
freshness marker. Aider doesn't claim to keep your docs canonical or to share a write path
across agents; that's trovex's job. An Aider session can ask trovex for the current runbook
while it works.

**When Aider is the right choice:** you want a focused, git-native code-editing agent in the
terminal. trovex is complementary, the doc-context layer, not a replacement.

## trovex vs Cody

**Short answer:** Cody (Sourcegraph) is a code AI assistant backed by Sourcegraph's code
search and codebase context, strong in large and enterprise codebases. trovex is narrower and
local: the canonical, freshness-marked doc for a query, served to any MCP client with no cloud.

**What Cody is:** an assistant that grounds answers in your codebase using Sourcegraph's
search and context retrieval, with enterprise features (scale, permissions, multiple repos).
For broad code understanding across a big org, that's its strength.

**Where they differ:** Cody retrieves relevant code/context across a codebase; trovex serves
the *one current doc* with an explicit canonical/stale/duplicate marker and a shared write
path, locally (SQLite + ONNX, no keys). Cody is breadth of code context, often cloud-backed;
trovex is canonical-doc currency for agents, local-first. Different axis (recall across code
vs currency of the answering doc).

**When Cody is the right choice:** large or enterprise codebases where org-wide code search and
governance matter. trovex fits the developer or small team who wants the current doc, cheaply,
on their own machine.

## trovex vs Pieces

**Short answer:** Pieces is a developer long-term-memory tool that captures snippets and
context across your tools, on-device. trovex is repo-scoped canonical-doc context for coding
agents. Both are local-first, but they remember different things.

**What Pieces is:** a personal developer memory and snippet manager that saves materials,
context, and conversations across your workflow and surfaces them later, with on-device
options. It's about *your* cross-tool memory.

**Where they differ:** Pieces remembers your personal materials across apps; trovex serves a
coding agent the canonical current doc from a specific repo, with a freshness marker, over MCP,
and shares one write path across a fleet and teammates. Personal cross-tool memory vs the
repo's single source of truth for agents. Complementary, not overlapping.

**When Pieces is the right choice:** you want a personal, cross-application memory of snippets
and context. trovex is the choice when the job is "give my agents the one current doc from this
repo, cheaply, and keep the team consistent."

## trovex vs Claude Projects

**Short answer:** Claude Projects lets you attach documents and instructions to a persistent
Claude workspace so they're in context for that project, hosted by Anthropic. trovex is
local-first, works with any MCP client, and serves the *one current* doc per query with a
freshness marker rather than holding the whole set in a project's context.

**What Claude Projects is (as of 2026):** a feature in Claude that keeps project knowledge and
custom instructions available across chats in that project, a convenient, hosted way to give
Claude persistent context for a body of work.

**Where they differ:** a Project holds your uploaded knowledge for Claude specifically, in
Anthropic's hosted context. trovex runs on your machine, works across MCP clients (Claude Code,
Cursor, Windsurf, Zed, and others), routes a query to the single canonical doc with a freshness
marker instead of relying on everything being in the project window, and offers a shared write
path. So: hosted, Claude-scoped, whole-set-in-context vs local, client-agnostic, one-current-
answer-per-query.

**When Claude Projects is the right choice:** you work primarily in Claude's chat UI and want a
simple, hosted home for a project's knowledge. trovex fits when your agents run in coding tools
over MCP, you want it local with no keys, and you need the *current* doc served cheaply (about
60% fewer tokens per lookup) with one source of truth across a fleet.

---

## Shared CTA (every page)

trovex is in private beta. [Request access at trovex.dev](https://trovex.dev) and we'll get you
set up. Several of the tools above are complementary; if you're figuring out how they fit
together for a team running agents at scale, that's the kind of thing we help with. Happy to talk.
