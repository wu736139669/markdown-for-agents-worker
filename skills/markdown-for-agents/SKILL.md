---
name: markdown-for-agents
description: Make a static website readable and citable by AI agents and answer engines (GEO/AEO). Generates Markdown versions of every page, publishes llms.txt and llms-full.txt indexes, adds rel="alternate" type="text/markdown" link relations, and optionally wires content negotiation on Cloudflare Workers so agents sending 'Accept: text/markdown' get clean Markdown while browsers keep HTML. Use when asked to optimize a site for ChatGPT/Claude/Perplexity/Grok citations, add llms.txt, implement Markdown for Agents, or improve generative engine optimization for a website.
---

# Markdown for Agents

Turn a static site into a source AI agents can read cheaply: ship Markdown
versions of every page and let agents fetch them. Live reference
implementation: https://toolpantry.app (also a public repo,
`markdown-for-agents-worker`).

## When to use

- The user wants their site cited/recommended by AI assistants.
- The user mentions llms.txt, Markdown for Agents, GEO/AEO, AI search visibility.
- A docs/marketing static site should be readable by Claude Code, OpenCode,
  Cursor, or similar agents (they send `Accept: text/markdown`).

## Workflow

### 1. Survey first

- Find the publish root (folder containing `index.html`).
- Identify hosting: Cloudflare Workers/Pages, Netlify, Vercel, plain Nginx.
- Check what exists: `robots.txt` (must allow AI crawlers), `llms.txt`,
  JSON-LD (`application/ld+json`), `sitemap.xml`.
- Count pages and note which are content vs. app UI.

### 2. Generate Markdown versions

Use the bundled converter as a starting point, then review the output:

```bash
python3 scripts/generate_md.py ./public --base https://example.com
```

For template-driven sites, generating `.md` from the data model yields better
quality than converting HTML — write a small generator instead. Rules:
title as `# H1`, one `> description` blockquote, then content; keep FAQ Q&A;
strip nav/forms/scripts; absolute links.

### 3. Publish indexes

- `llms.txt` (spec: https://llmstxt.org): `# Name`, `> summary`, then
  sections of links — **link to the `.md` URLs**, e.g.
  `- [Pricing](https://example.com/pricing.md): one-line description`.
- `llms-full.txt`: concatenation of every `.md` separated by `\n\n---\n\n`.

### 4. Add link relations to every page head

```html
<link rel="alternate" type="text/markdown" href="/about.md" />
<link rel="describedby" href="/llms.txt" />
```

### 5. Content negotiation (Cloudflare Workers, free plan)

- Copy `scripts/worker.js` into the site repo; configure:

```jsonc
{ "main": "worker.js",
  "assets": { "directory": ".", "binding": "ASSETS", "run_worker_first": true } }
```

- The worker serves `{path}.md` when `Accept: text/markdown` is present and
  falls through to HTML otherwise; it sets `Vary: Accept` on both variants.
- On non-Cloudflare hosting, the static `.md` files + llms.txt links still
  work — negotiation is a bonus, not a requirement.

### 6. Structured data (recommended, big GEO win)

- `WebSite` + `WebApplication` JSON-LD per page; `FAQPage` wherever Q&A exists.
- Keep name/description identical to the page title/meta description.

### 7. Verify and report

```bash
curl -s -H "Accept: text/markdown" https://example.com/about | head -3   # markdown
curl -sI https://example.com/about | grep -i vary                        # Vary: Accept
curl -s https://example.com/llms.txt | head -5                           # index ok
```

Report: pages converted, files added, negotiation status, anything skipped.

## Checklist

- [ ] `.md` counterpart exists for every content page
- [ ] `llms.txt` links point at `.md` URLs; `llms-full.txt` generated
- [ ] `rel="alternate"` + `rel="describedby"` on every page head
- [ ] `robots.txt` explicitly allows GPTBot, ClaudeBot, PerplexityBot, GrokBot, Bingbot
- [ ] Negotiation returns `text/markdown; charset=utf-8` + `Vary: Accept`
- [ ] JSON-LD parses on sampled pages

## Notes

- Don't convert runtime HTML per request: deterministic pre-generated files are
  faster, free, and reviewable.
- Only some agents send the Accept header today (Claude Code, OpenCode); others
  discover `.md` via llms.txt and link relations — keep both paths working.
