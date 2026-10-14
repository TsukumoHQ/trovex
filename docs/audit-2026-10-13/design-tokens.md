# DS-01 token inventory (taken before any change)

Exact values from the code on `origin/dev`. The audit branch adds no new colour, font, radius
or easing; every new rule reuses the values below.

## Static pages: `web/public/vs/compare.css` (all 69 /answers /vs /for /use-cases /glossary /measure /method pages)

| Token | Value |
|---|---|
| `--bg` | `#0b0e14` |
| `--bg-card` | `#11151f` |
| `--bg-elev` | `#161b26` |
| `--fg` / `--fg-muted` / `--fg-subtle` | `#e6edf3` / `#9aa6b8` / `#74808f` |
| `--accent` | `#22c55e` |
| `--accent-soft` / `--accent-line` | `rgba(34,197,94,0.12)` / `rgba(34,197,94,0.28)` |
| `--line` / `--line-strong` | `rgba(255,255,255,0.08)` / `rgba(255,255,255,0.14)` |
| `--maxw` | `760px` |
| Fonts | Fira Sans (body 17px/1.65), Fira Code (code, command chips) |
| Command copy button | `.qs-copy`: Fira Code 10.5px uppercase, 0.06em tracking, 1px `--line-strong` border, radius 5px |
| Motion before | none (no transitions in compare.css) |

## Landing + /savings + /audit: `web/src/index.css`, `web/src/savings/savings.css`

| Token | Value |
|---|---|
| `--stage` / `--stage-2` | `#06080d` / `#080b12` |
| `--bg-elevated` / `--bg-card` / `--bg-hover` / `--bg-input` | `#11151f` / `#161b26` / `#1e2433` / `#0d1119` |
| `--border` / `--border-strong` | `rgba(148,163,184,0.10)` / `rgba(148,163,184,0.18)` |
| `--fg` / `--fg-muted` / `--fg-subtle` / `--fg-faint` | `#e6edf3` / `#9aa6b8` / `#74808f` / `#5a6577` |
| `--accent` / `--accent-soft` / `--accent-line` / `--on-accent` | `#22c55e` / `rgba(34,197,94,0.12)` / `rgba(34,197,94,0.28)` / `#06140b` |
| Status colours | canonical `#22c55e`, stale `#ef4444`, duplicate `#f59e0b`, plan `#60a5fa` |
| Fonts | `--font-sans` Fira Sans, `--font-mono` Fira Code |
| Radius | `--radius` 8px, `--radius-sm` 5px, `--radius-lg` 14px |
| Easing | `--ease: cubic-bezier(0.16, 1, 0.3, 1)` |
| Motion before | hover colour transitions .15s; hero `fadeUp` .85s; `.reveal` .7s; savings bar 1.2s; `pulse` 2s; reduced-motion block in index.css turns off all animation |

## What DS-01 added (150-250ms, existing tokens only)

| Surface | Interaction | Motion | Reduced motion |
|---|---|---|---|
| Landing `CopyCmd` (`.cmd-copy`) | copy → "copied" | 180ms colour/border/background to `--accent` / `--accent-line` / `--accent-soft` + 200ms `scale(.94→1)` settle | global `animation: none`; transition removed |
| Static pages `.qs-copy` (`/for`, `/answers`, `/glossary`, `/vs`, `/use-cases`) | copy → "copied" (`data-state` set by `quickstart.js`, `copy-track.js`, `vs/track.js`) | same 180/200ms | animation and transition removed |
| `/savings` calculator share buttons | copy link / post / badge / save card | same 180/200ms | removed |
| `/savings` result figures | input change → % and monthly figures re-key | 200ms `opacity .55→1`, `translateY(3px→0)` | none (static) |
| Signature link (topbar/nav) | hover | 180ms colour to `--accent` | transition removed |

No layout shift: the copy buttons keep their size (text swap as before), and the result tick
only animates opacity and transform.
