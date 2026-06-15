# FAQ

Honest answers, including when trovex isn't the right tool.

## What does trovex actually do?

It indexes your repo's markdown and exposes one MCP tool. Your coding agent asks a question
in plain language; trovex returns the single current doc that answers it as a `path:line`
pointer with a freshness marker (canonical, stale, or duplicate), and serves just the
section that answers instead of the whole file. Agents can also write what they learn back
through one shared store, so the whole fleet reads one source of truth.

## Why does this save tokens?

Without it, your agent reads several `.md` files each session to work out which is current,
then answers from a guess. It pays for the discarded reads, and it pays again next session.
trovex hands it the one current doc, so a typical doc lookup drops from roughly 720 tokens
to roughly 280. About 60% fewer on doc lookups, for the same answer. The dashboard shows
your real number; don't take ours on faith.

## My context window is huge. Why bother?

A bigger window doesn't make the reread cheaper, it makes it bigger. The cost compounds
across every session, agent, and teammate. And a big window isn't a current one; it will
hold three conflicting docs and answer from the wrong one. trovex serves the right doc
cheaply. Window size doesn't fix correctness.

## I already use CLAUDE.md / AGENTS.md.

Keep it for high-level rules. It's one static file, though. It goes stale, doesn't scale
past a few topics, and can't route a question to the right doc or section. trovex keeps many
docs canonical and serves the one that answers the specific question. The two work together.

## How is this different from RAG or dumping the repo?

Dumping the repo (repomix, files-to-prompt) floods the window with everything, which is the
opposite of token-efficient. Plain RAG returns a handful of candidate chunks ranked by
similarity and leaves the agent to pick, with no freshness signal. trovex returns the one
current doc with an explicit freshness marker, and closes the loop by letting agents write
canonical notes back. The unit of output is an answer, not a candidate set.

## Is it one more service to babysit?

One local process. Run `trovex serve`, point your agent at it, done in about a minute. No
cloud, no keys. It shows you the tokens it saves, so it justifies its own existence.

## Does my code leave my machine?

No. Indexing and embeddings run locally in SQLite and ONNX. Nothing is sent anywhere.

## Which agents and editors work with it?

Anything that speaks MCP: Claude Code, Cursor, Windsurf, Zed, and other MCP clients. See the
[quickstart](./quickstart.md) for wiring it up.

## When is trovex NOT worth it?

If your repo has a small or tidy doc set, your agent isn't rereading much, and the savings
number stays low, keep your current setup. trovex earns its place on doc-heavy repos with
real agent traffic, and on teams where several agents and people work the same docs. Run the
[self-audit](../growth/content/lead-magnet-token-audit.md) if you're not sure.

## Is trovex open source? Can I get the code?

Yes, it's open-source-licensed (core AGPL-3.0, CLI MIT), and it will open to the public.
Right now it's in private beta, so access to the code is gated while we work with a small
group of early testers. The license isn't changing; the doors just open in stages.
[Request access at trovex.dev](https://trovex.dev) and we'll get you in.

## Is it free? What's the license?

Yes. The core is AGPL-3.0, the CLI is MIT. During the private beta, access is by request at
[trovex.dev](https://trovex.dev); once you're in, you can self-host and modify it freely. If
you run a modified version as a network service, AGPL asks you to share your changes.

## I'm rolling agents out across a team. Can you help?

That's the consulting side. trovex is the free tool; helping teams run agents well at scale
(including embedding or hosting a modified trovex privately, without the AGPL copyleft
obligations) is the paid work. [Working with a team? Let's talk.](https://trovex.dev)
