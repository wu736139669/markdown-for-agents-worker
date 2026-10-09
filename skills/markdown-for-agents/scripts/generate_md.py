#!/usr/bin/env python3
"""Generate Markdown versions of static HTML pages (stdlib only).

Usage:
    python3 generate_md.py ./public --base https://example.com

For every .html file it writes a sibling .md file with the same stem:
    public/about.html   ->  public/about.md
    public/index.html   ->  public/index.md

The converter keeps the content that agents care about (headings, paragraphs,
lists, links, code, FAQ details) and drops chrome (nav, footer, scripts, forms).
Review the output before shipping — markdown-for-agents-worker simply serves
whatever .md files it finds.

Tips for high-quality output:
  - Use semantic HTML (<main>, <h1>..<h3>, <p>, <ul>, <details>).
  - For template-driven sites, generating .md from your own data model often
    beats converting HTML. See the live example for that approach.
"""
import argparse
import html as ihtml
import pathlib
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urljoin

SKIP_TAGS = {
    'script', 'style', 'svg', 'canvas', 'iframe', 'video', 'audio', 'noscript',
    'form', 'button', 'select', 'option', 'input', 'textarea', 'template',
    'label', 'output',
}
BLOCK_TAGS = {
    'p', 'div', 'section', 'article', 'aside', 'header', 'footer', 'main',
    'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'blockquote', 'pre', 'details', 'summary', 'table', 'tr', 'hr', 'br',
}
HEADINGS = {'h1': '#', 'h2': '##', 'h3': '###', 'h4': '####', 'h5': '#####', 'h6': '######'}


class Converter(HTMLParser):
    def __init__(self, base, only_main=False):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.out = []
        self.parts = []
        self.skip = 0
        self.main_depth = 0
        # When the page has a <main>, ignore everything outside of it
        # (chrome, nav, footers, head instead of skipping blindly).
        self.seen_main = only_main
        self.in_pre = False

    # -- output helpers -------------------------------------------------
    def flush(self):
        text = re.sub(r'[ \t]+', ' ', ''.join(self.parts)).strip()
        text = re.sub(r' {2,}', ' ', text)
        if text:
            self.out.append(text)
        self.parts = []

    def emit(self, line):
        self.flush()
        self.out.append(line)

    # -- parser hooks ---------------------------------------------------
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'main':
            self.seen_main = True
            self.main_depth += 1
        if self.skip:
            self.skip += 1
            return
        if self.seen_main and self.main_depth == 0:
            # Outside <main>: ignore the tag without touching the skip counter,
            # otherwise the main element itself would be treated as skipped.
            return
        if tag in SKIP_TAGS:
            self.skip = 1
            return

        if tag in BLOCK_TAGS:
            self.flush() if self.parts else None
        if tag in HEADINGS:
            self.emit('')
            self.parts.append(HEADINGS[tag] + ' ')
        elif tag == 'li':
            self.flush()
            self.parts.append('- ')
        elif tag == 'summary':
            self.flush()
            self.parts.append('**')
        elif tag == 'blockquote':
            self.parts.append('> ')
        elif tag == 'pre':
            self.emit('```')
            self.in_pre = True
        elif tag == 'hr':
            self.emit('---')
        elif tag == 'br':
            self.parts.append('  \n')
        elif tag == 'strong' or tag == 'b':
            self.parts.append('**')
        elif tag == 'em' or tag == 'i':
            self.parts.append('*')
        elif tag == 'code' and not self.in_pre:
            self.parts.append('`')
        elif tag == 'a':
            href = a.get('href', '')
            if href and not href.startswith(('#', 'javascript:', 'mailto:')):
                self.parts.append('[')
                self._href = urljoin(self.base, href) if self.base else href
                self.parts.append('__LINK_OPEN__')
            else:
                self._href = None
        elif tag == 'img':
            alt = a.get('alt', '')
            src = a.get('src', '')
            if src:
                self.parts.append(f'![{alt}]({urljoin(self.base, src) if self.base else src})')

    def handle_endtag(self, tag):
        if tag == 'main':
            self.main_depth = max(0, self.main_depth - 1)
        if self.skip:
            self.skip -= 1
            return
        if self.seen_main and self.main_depth == 0 and tag not in ('body', 'html'):
            return

        if tag in HEADINGS or tag in ('p', 'li', 'blockquote', 'tr', 'table'):
            self.flush()
        elif tag == 'summary':
            self.parts.append('**')
            self.flush()
        elif tag == 'pre':
            self.flush()
            self.emit('```')
            self.in_pre = False
        elif tag in ('strong', 'b'):
            self.parts.append('**')
        elif tag in ('em', 'i'):
            self.parts.append('*')
        elif tag == 'code' and not self.in_pre:
            self.parts.append('`')
        elif tag == 'a' and getattr(self, '_href', None):
            self.parts.append(f']({self._href})')
            self._href = None
        elif tag in ('td', 'th'):
            self.parts.append(' | ')

    def handle_data(self, data):
        if self.skip or (self.seen_main and self.main_depth == 0):
            return
        if self.in_pre:
            self.parts.append(data)
        else:
            self.parts.append(re.sub(r'\s+', ' ', data))

    def result(self):
        self.flush()
        lines = []
        for x in self.out:
            if x == '' and lines and lines[-1] == '':
                continue
            lines.append(x.replace('__LINK_OPEN__', ''))
        return '\n\n'.join(x for x in lines if x)


def convert_file(path, base):
    s = path.read_text(encoding='utf-8')
    title = re.search(r'<title>(.*?)</title>', s, re.S)
    desc = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', s, re.S)
    title = re.sub(r'\s+', ' ', ihtml.unescape(title.group(1))).strip() if title else path.stem
    desc = re.sub(r'\s+', ' ', ihtml.unescape(desc.group(1))).strip() if desc else ''

    c = Converter(base, only_main=bool(re.search(r'<main[\s>]', s, re.I)))
    c.feed(s)
    body = c.result()
    # The page title is the document H1; demote every heading in the body
    # by one level so the hierarchy stays sane.
    body = re.sub(r'(?m)^(#{1,5}) ', r'#\1 ', body)

    head = [f'# {title}']
    if desc:
        head += ['', f'> {desc}']
    if base:
        head += ['', f'Source: {urljoin(base + "/", path.stem if path.stem != "index" else "")}']
    return '\n'.join(head) + '\n\n' + body + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('directory', help='directory containing .html files')
    ap.add_argument('--base', default='', help='optional site base URL for absolute links')
    args = ap.parse_args()

    root = pathlib.Path(args.directory)
    files = sorted(root.rglob('*.html'))
    if not files:
        print('no .html files found in', root, file=sys.stderr)
        sys.exit(1)
    for f in files:
        md = convert_file(f, args.base.rstrip('/'))
        out = f.with_suffix('.md')
        out.write_text(md, encoding='utf-8')
        print(f'{f} -> {out} ({len(md)} bytes)')
    print(f'done: {len(files)} files')


if __name__ == '__main__':
    main()
