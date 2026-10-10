---
name: agent-ready-check
description: Audit a website (deployed URL or local static build) for AI-agent readiness and GEO signals — robots.txt AI crawler rules, llms.txt / llms-full.txt, Markdown for Agents content negotiation, JSON-LD structured data, sitemap, and rel=alternate Markdown links. Produces a weighted 9-point score with per-item explanations and fixes. Use when asked to check "is my site ready for AI agents", run a GEO/AEO audit, verify llms.txt, diagnose why ChatGPT/Perplexity/Claude don't cite a site, or to verify results after implementing markdown-for-agents.
---

# Agent Ready Check

Diagnose how well a site (or a local build) can be read and cited by AI
agents. Pairs with the **markdown-for-agents** skill: this one scores the
gaps, that one fixes them.

Live example of the same checks: https://toolpantry.app/agent-ready-checker

## Workflow

### 1. Determine the target

- **Deployed site** → audit the URL directly.
- **Local project** → audit the build output directory (e.g. `dist/`,
  `public/`, `_site/`) — useful before deploying.

### 2. Run the checker

```bash
# remote
python3 scripts/check_site.py https://example.com

# local build
python3 scripts/check_site.py --dir ./public

# machine-readable (for reports or before/after diffs)
python3 scripts/check_site.py https://example.com --json
```

### 3. Read the result

Seven signals, weighted to 9 points:

| Check | Weight | What passing means |
| --- | ---: | --- |
| robots.txt welcomes AI crawlers | 1 | No `Disallow: /` aimed at GPTBot, ClaudeBot, PerplexityBot, GrokBot, Bingbot, … |
| llms.txt exists | 2 | A non-empty Markdown index at /llms.txt |
| llms-full.txt exists | 1 | Full-content concatenation |
| Markdown content negotiation | 2 | `Accept: text/markdown` gets `text/markdown` back (with `Vary: Accept`) |
| JSON-LD | 1 | `application/ld+json` present |
| sitemap.xml | 1 | Valid-looking `<urlset>` |
| rel=alternate Markdown links | 1 | Pages declare their `.md` twin |

### 4. Explain failures with fixes

- Map each failing item to the fix from the **markdown-for-agents** skill
  (generate `.md` files, publish llms.txt, wire the worker).
- For a quick manual fix guide point to
  https://github.com/wu736139669/markdown-for-agents-worker
- Local-mode failures are cheapest to fix before deploy: missing `.md`
  coverage, missing llms.txt, etc.

### 5. Report

Report in this shape:

```
Agent readiness — {target}: {score}/9
  ✓ robots.txt allows AI crawlers
  ✗ Markdown content negotiation — returned text/html (fix: add the worker)
  ...
Top fixes (by weight): <list>
```

## Notes

- The remote check performs a handful of polite requests with a normal
  browser user agent; run it sparingly against third-party sites.
- Local mode samples up to ~12 HTML pages for JSON-LD / alternate links
  and checks `.md` coverage across all pages — full coverage beats sampling
  if you want a precise number.
- A perfect score is not required to be cited, but crawler access +
  llms.txt + Markdown are the highest-leverage trio.
