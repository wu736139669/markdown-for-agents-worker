#!/usr/bin/env python3
"""Agent readiness checker — stdlib only.

Audit a deployed URL or a local static build for AI-agent readiness:
robots.txt AI-crawler rules, llms.txt / llms-full.txt, Markdown content
negotiation, JSON-LD, sitemap.xml, and rel="alternate" Markdown links.

Usage:
    python3 check_site.py https://example.com
    python3 check_site.py --dir ./public
    python3 check_site.py https://example.com --json

Exit code is always 0 unless the target cannot be evaluated at all.
"""
import argparse
import gzip
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36 AgentReadyCheck/1.0')
AI_BOTS = ['gptbot', 'oai-searchbot', 'chatgpt-user', 'claudebot', 'anthropic-ai',
           'perplexitybot', 'grokbot', 'xai-searchbot', 'bingbot']

WEIGHTS = {'robots': 1, 'llms': 2, 'llmsfull': 1, 'markdown': 2, 'jsonld': 1, 'sitemap': 1, 'alternate': 1}
LABELS = {
    'robots': 'robots.txt welcomes AI crawlers',
    'llms': 'llms.txt exists (site index for LLMs)',
    'llmsfull': 'llms-full.txt exists (all content in one file)',
    'markdown': 'Serves Markdown to AI agents (content negotiation)',
    'jsonld': 'Structured data (JSON-LD) on the page',
    'sitemap': 'XML sitemap available',
    'alternate': 'Pages declare their Markdown version (rel=alternate)',
}


def parse_robots(text):
    agents, wildcard, blocked = [], False, set()
    for line in text.split('\n'):
        clean = re.sub(r'#.*', '', line).strip()
        if not clean:
            continue
        m = re.match(r'user-agent:\s*(.+)', clean, re.I)
        if m:
            agents = [a.lower() for a in re.split(r'[,\s]+', m.group(1)) if a]
            continue
        m = re.match(r'disallow:\s*(.*)', clean, re.I)
        if m and agents and m.group(1).strip() == '/':
            for a in agents:
                if a == '*':
                    wildcard = True
                else:
                    blocked.add(a)
    if wildcard:
        return False, 'robots.txt disallows all crawlers (User-agent: * / Disallow: /)'
    hits = [b for b in AI_BOTS if b in blocked]
    if hits:
        return False, 'Explicitly blocked: ' + ', '.join(hits)
    return True, 'Search and AI crawlers are allowed'


def fetch(url, accept=None, timeout=15, tries=3):
    req = urllib.request.Request(url, headers={'user-agent': UA})
    if accept:
        req.add_header('accept', accept)
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
                if r.headers.get('content-encoding') == 'gzip':
                    data = gzip.decompress(data)
                return r, data
        except urllib.error.HTTPError as e:
            return e, b''
        except Exception:
            if i < tries - 1:
                time.sleep(1.5 * (i + 1))
    return None, b''


def check_remote(base):
    checks = []
    base = base.rstrip('/')
    _, page = fetch(base, accept='text/html,*/*')
    html = page.decode('utf-8', 'ignore')

    r, robots = fetch(base + '/robots.txt')
    if r is not None and getattr(r, 'status', 200) == 200 and robots.strip():
        ok, detail = parse_robots(robots.decode('utf-8', 'ignore'))
    else:
        ok, detail = False, 'robots.txt not found'
    checks.append(('robots', ok, detail))

    for key, path in (('llms', '/llms.txt'), ('llmsfull', '/llms-full.txt')):
        r, body = fetch(base + path, timeout=45)
        ok = bool(r is not None and getattr(r, 'status', 200) == 200 and body.strip())
        checks.append((key, ok, f'{path} ' + ('found (' + str(len(body)) + ' bytes)' if ok else 'not found')))

    r, body = fetch(base, accept='text/markdown, text/html;q=0.9')
    ct = (r.headers.get('content-type') or '').lower() if r is not None and hasattr(r, 'headers') else ''
    ok = 'text/markdown' in ct
    if ok:
        vary = (r.headers.get('vary') or '').lower()
        detail = 'Returns text/markdown' + ('' if 'accept' in vary else ' (missing Vary: Accept)')
    else:
        detail = f'Returned {ct or "unknown"} — no Markdown variant'
    checks.append(('markdown', ok, detail))

    ok = 'application/ld+json' in html
    checks.append(('jsonld', ok, 'application/ld+json found' if ok else 'No JSON-LD found'))

    r, sm = fetch(base + '/sitemap.xml')
    ok = bool(r is not None and getattr(r, 'status', 200) == 200 and (b'<urlset' in sm[:10000] or b'<sitemapindex' in sm[:10000]))
    checks.append(('sitemap', ok, 'sitemap.xml found' if ok else 'sitemap.xml not found'))

    ok = bool(re.search(r'rel=["\']alternate["\'][^>]*text/markdown|text/markdown[^>]*rel=["\']alternate["\']', html, re.I))
    checks.append(('alternate', ok, 'rel="alternate" type="text/markdown" found' if ok else 'No Markdown alternate link declared'))
    return checks, base


def check_local(root, sample=12):
    root = pathlib.Path(root)
    if not (root / 'index.html').exists() and not list(root.glob('*.html')):
        raise SystemExit(f'no html files found under {root}')
    checks = []

    robots = root / 'robots.txt'
    if robots.exists() and robots.read_text(errors='ignore').strip():
        ok, detail = parse_robots(robots.read_text(errors='ignore'))
    else:
        ok, detail = False, 'robots.txt not found'
    checks.append(('robots', ok, detail))

    for key, name in (('llms', 'llms.txt'), ('llmsfull', 'llms-full.txt')):
        p = root / name
        ok = p.exists() and p.read_text(errors='ignore').strip() != ''
        checks.append((key, ok, f'{name} ' + ('found' if ok else 'not found')))

    htmls = sorted(p for p in root.rglob('*.html') if not p.name.startswith('google'))
    md_missing = [p for p in htmls if not p.with_suffix('.md').exists()]
    coverage = 1 - (len(md_missing) / max(1, len(htmls)))
    ok = bool(htmls) and not md_missing
    detail = f'{len(htmls) - len(md_missing)}/{len(htmls)} pages have .md versions'
    if md_missing[:3]:
        detail += ' — missing e.g. ' + ', '.join(p.name for p in md_missing[:3])
    checks.append(('markdown', ok, detail))

    sample_files = [root / 'index.html'] if (root / 'index.html').exists() else []
    sample_files += [p for p in htmls if p.name != 'index.html'][:sample]
    jsonld = sum(1 for p in sample_files if 'application/ld+json' in p.read_text(errors='ignore'))
    alt = sum(1 for p in sample_files
              if re.search(r'rel=["\']alternate["\'][^>]*text/markdown|text/markdown[^>]*rel=["\']alternate["\']',
                           p.read_text(errors='ignore'), re.I))
    n = max(1, len(sample_files))
    checks.append(('jsonld', jsonld > 0, f'{jsonld}/{n} sampled pages have JSON-LD'))
    checks.append(('sitemap', (root / 'sitemap.xml').exists(), 'sitemap.xml ' + ('found' if (root / 'sitemap.xml').exists() else 'not found')))
    checks.append(('alternate', alt > 0, f'{alt}/{n} sampled pages declare a Markdown alternate'))
    return checks, str(root)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('url', nargs='?', help='deployed URL to audit')
    ap.add_argument('--dir', help='local static build directory to audit instead')
    ap.add_argument('--json', action='store_true', help='print JSON instead of a table')
    args = ap.parse_args()

    if args.dir:
        checks, target = check_local(args.dir)
    elif args.url:
        checks, target = check_remote(args.url)
    else:
        ap.error('provide a URL or --dir')

    order = ['robots', 'llms', 'llmsfull', 'markdown', 'jsonld', 'sitemap', 'alternate']
    checks.sort(key=lambda c: order.index(c[0]))
    score = sum(WEIGHTS[c[0]] for c in checks if c[1])
    max_score = sum(WEIGHTS.values())

    if args.json:
        print(json.dumps({
            'target': target,
            'score': score,
            'maxScore': max_score,
            'checks': [{'id': c[0], 'label': LABELS[c[0]], 'pass': c[1], 'detail': c[2]} for c in checks],
        }, indent=2))
        return

    print(f'Agent readiness: {target}')
    print(f'Score: {score}/{max_score}\n')
    for cid, ok, detail in checks:
        print(f'  [{"x" if ok else " "}] {LABELS[cid]}')
        print(f'       {detail}')
    if score < max_score:
        print('\nFix guide: https://github.com/wu736139669/markdown-for-agents-worker'
              ' (or use the markdown-for-agents skill)')


if __name__ == '__main__':
    main()
