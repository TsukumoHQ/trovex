# Atom — clone-and-run (X / founder 6430128)

> **DRAFT. Founder account, builder voice. Not armed.** cmo gates copy; tech-copy may
> polish to owner-voice. A human fires. Artifact-led per research doc 65794b11 (a
> runnable snippet beats a claim). Only first-party number: ~60%.

**Format:** single post + the command as an image/code block (legible, screenshot-able).
**Funnel:** top → trovex.dev (activation). **Ask:** run it on your own repo.

---

## Post body

three commands. no clone, no account, no keys. run it on a repo you know and read your own number:

```
uv tool install git+https://github.com/TsukumoHQ/trovex
trovex index /path/to/your/repo
trovex search "how do we roll back a deploy?"
```

that last line prints the tokens it saved versus reading the top candidate docs. on a doc-heavy repo that's around 60% on the lookup, same answer. your number, your repo — not mine.

don't want to install anything? `uvx --from git+https://github.com/TsukumoHQ/trovex trovex search "..."`

local: sqlite + onnx, your code never leaves the box.

---

## Reply 1 (thread it after the post)

wire it into your agent over MCP and the savings stack up on a dashboard:

```
trovex serve
claude mcp add --transport http trovex http://localhost:8765/mcp
```

teardown + the why behind the number → trovex.dev

---

## Notes
- Link (`trovex.dev`) goes in the reply, not the post body.
- The command block is the artifact — make it the visual. Real commands, verbatim from README.
- No banned words; no fabricated metrics; ~60% framed as the user's-own-measurement, not a boast.
