/**
 * markdown-for-agents-worker
 *
 * Serve Markdown versions of static pages to AI agents via HTTP content
 * negotiation (RFC 9110). Agents such as Claude Code and OpenCode send
 * `Accept: text/markdown`; browsers keep receiving HTML.
 *
 * This worker runs in front of Workers static assets (or any assets binding)
 * and returns the pre-generated `{path}.md` file when the client asks for
 * Markdown. No runtime HTML conversion, no per-request cost, deterministic
 * output — you ship the .md files you reviewed.
 */

export default {
  async fetch(request, env) {
    const accept = request.headers.get('Accept') || '';

    if ((request.method === 'GET' || request.method === 'HEAD') && acceptsMarkdown(accept)) {
      const url = new URL(request.url);
      const mdPath = markdownPath(url.pathname);
      if (mdPath) {
        const res = await env.ASSETS.fetch(new URL(mdPath, url.origin));
        if (res.ok) {
          const headers = new Headers({
            'content-type': 'text/markdown; charset=utf-8',
            'vary': 'Accept',
            'cache-control': 'public, max-age=3600',
          });
          return new Response(request.method === 'HEAD' ? null : res.body, {
            status: 200,
            headers,
          });
        }
      }
    }

    const res = await env.ASSETS.fetch(request);

    // The same URL can return HTML or Markdown depending on Accept.
    // Tell caches about it (HTML pages only — assets like images don't need it).
    const contentType = res.headers.get('content-type') || '';
    if (contentType.startsWith('text/html')) {
      const headers = new Headers(res.headers);
      headers.append('Vary', 'Accept');
      return new Response(res.body, { status: res.status, statusText: res.statusText, headers });
    }

    return res;
  },
};

function acceptsMarkdown(acceptHeader) {
  return acceptHeader.toLowerCase().includes('text/markdown');
}

/** `/about` -> `/about.md`, `/` -> `/index.md`, `/about.html` -> `/about.md` */
function markdownPath(pathname) {
  let p = pathname.replace(/\/+$/, '');
  if (p === '') p = '/index';
  if (p.endsWith('.html')) p = p.slice(0, -5);
  if (p.endsWith('.md')) return null;
  return p + '.md';
}
