# markdown-for-agents-worker

> Serve Markdown to AI agents from any static site — via HTTP content negotiation on Cloudflare Workers. Zero runtime conversion, zero cost, deterministic output.

AI coding agents have started asking for Markdown instead of HTML:
[Claude Code](https://claude.com/claude-code) and OpenCode send `Accept: text/markdown`
when they fetch a page. Cloudflare's built-in *Markdown for Agents* handles this on
Pro plans; this repo is a free, portable alternative: you ship pre-generated `.md`
files alongside your HTML, and a ~40-line Worker serves the right format to the
right client.

Same URL, two representations:

```bash
# browsers (and everything else) keep getting HTML
$ curl -sI https://toolpantry.app/emi-calculator | grep -i content-type
content-type: text/html; charset=utf-8

# AI agents get clean Markdown
$ curl -s -H "Accept: text/markdown" https://toolpantry.app/emi-calculator | head -3
# EMI Calculator — Monthly Payment, Interest & Prepayment

> Calculate monthly EMI, total interest, total payment, amortization, and prepayment savings...
```

**Live example:** [toolpantry.app](https://toolpantry.app) — a 122-page static tools site
using this exact setup.

## How it works

```
  Browser  ──Accept: text/html──────▶  Worker ──▶ /emi-calculator.html
  AI agent ──Accept: text/markdown──▶  Worker ──▶ /emi-calculator.md
```

1. You pre-generate a `.md` version of every page (`{slug}.md` next to `{slug}.html`).
2. `worker.js` runs in front of your static assets (`run_worker_first: true`).
3. When a request carries `Accept: text/markdown`, it serves the `.md` file with
   `Content-Type: text/markdown` and `Vary: Accept`; otherwise it falls through to
   the normal asset.
4. HTML responses also carry `Vary: Accept`, so caches keep the two variants apart.

## Quickstart (Cloudflare Workers, free plan)

```bash
# 1. Generate .md files next to your .html files
python3 generate_md.py ./public --base https://example.com

# 2. Add the worker + config to your project root
#    (copy worker.js from this repo, then use a wrangler.jsonc like:)
```

```jsonc
{
  "name": "my-static-site",
  "main": "worker.js",
  "compatibility_date": "2026-10-01",
  "assets": {
    "directory": "./public",
    "binding": "ASSETS",
    "run_worker_first": true
  }
}
```

```bash
# 3. Deploy
npx wrangler deploy

# 4. Verify
curl -s -H "Accept: text/markdown" https://example.com/about | head -3
```

The `.md` files are plain static assets — you can also link them directly
(`/about.md`) or skip the Worker entirely and just ship the files.

## Why pre-generated Markdown instead of runtime HTML→MD conversion?

- **Deterministic.** You review exactly what agents receive. Runtime converters
  occasionally mangle tables, code, or layout components.
- **Free and fast.** No per-request conversion cost; the Worker just picks a file.
- **Better quality.** For template-driven sites, generating `.md` from your own
  data (or converting and hand-polishing once) beats generic conversion.
  `generate_md.py` is a decent generic starting point — review its output.

## Use it as an agent skill

This repo ships two agent skills (SKILL.md convention):

| Skill | Role |
| --- | --- |
| [`skills/markdown-for-agents`](skills/markdown-for-agents/SKILL.md) | **Fix** — implement llms.txt, `.md` versions, and content negotiation for a site |
| [`skills/agent-ready-check`](skills/agent-ready-check/SKILL.md) | **Diagnose** — audit any deployed URL or local build (9-point score, per-item fixes) |

Install both into your agent's skills folder:

```bash
git clone https://github.com/wu736139669/markdown-for-agents-worker
cp -r markdown-for-agents-worker/skills/markdown-for-agents ~/.claude/skills/   # or ~/.agents/skills/
cp -r markdown-for-agents-worker/skills/agent-ready-check  ~/.claude/skills/
```

Then prompt:

> Check if my site is ready for AI agents, then fix the gaps.

Works with any agent that supports the SKILL.md convention (Claude Code,
OpenCode, Cursor, Codex, Copilot, Windsurf and friends). Or use the hosted
checker at https://toolpantry.app/agent-ready-checker.

## Pair it with llms.txt

Discovery matters as much as negotiation. Publish an [llms.txt](https://llmstxt.org)
index and add link relations to every page head so agents can find the Markdown
without guessing:

```html
<link rel="alternate" type="text/markdown" href="/about.md" />
<link rel="describedby" href="/llms.txt" />
```

## Caveats

- Only clients that send `Accept: text/markdown` benefit from negotiation.
  Most current agents (ChatGPT, Codex, Gemini) don't send it yet — for those,
  `llms.txt` + `rel="alternate"` + directly linkable `.md` URLs are the fallback.
- Always set `Vary: Accept` on negotiated URLs (this worker does) so CDNs don't
  cross-serve the two formats.
- If a `.md` file is missing, the request falls back to HTML — safe by default.

## License

MIT
