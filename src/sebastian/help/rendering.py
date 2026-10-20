"""Markdown → HTML for the help pages, with links and images rewritten (see `sebastian.help`)."""
import re
from urllib.parse import urlsplit

from django.urls import reverse

from .site import normalize, resolve

_HEADINGS = ('h1', 'h2', 'h3', 'h4', 'h5', 'h6')
_RAW_ANCHOR = re.compile(r'(<a\s+(?:id|name)=")([^"]+)"')


def page_anchor(page: str, anchor: str = '') -> str:
    """Id of a page (or of an anchor in it) inside a book page."""
    base = re.sub(r'[^\w-]', '-', page)
    return f'{base}--{anchor}' if anchor else base


def _markdown(treeprocessor):
    import markdown
    from markdown.treeprocessors import Treeprocessor
    from pymdownx.superfences import fence_div_format

    class _Rewriter(Treeprocessor):
        def run(self, root):
            treeprocessor(root)

    md = markdown.Markdown(extensions=[
        'toc', 'tables', 'attr_list', 'admonition', 'pymdownx.details',
        'pymdownx.superfences',
    ], extension_configs={
        'toc': {'permalink': False},
        'pymdownx.superfences': {'custom_fences': [
            # diagrams drawn by mermaid.js in the browser
            {'name': 'mermaid', 'class': 'mermaid', 'format': fence_div_format},
        ]},
    })
    # after 'toc' (priority 5), which assigns the heading ids
    md.treeprocessors.register(_Rewriter(md), 'sebastian_help', 1)
    return md


class RenderedPage:
    def __init__(self, html, headings):
        self.html = html
        self.headings = headings     # [(level, id, text)] after the book shift
        self.has_mermaid = 'class="mermaid"' in html


def render_page(site, page, book=None):
    """HTML of `page`. With `book` (a `Book`), for the book's single page: headings one level
    down (the book title is the H1) and ids prefixed by the page, links to pages of the same
    book turned into anchors."""
    headings = []

    def url_of(target, anchor):
        if book is not None and target in book.pages:
            return '#' + page_anchor(target, anchor)
        url = reverse('sebastian-help-page', args=[target])
        return f'{url}#{anchor}' if anchor else url

    def rewrite(root):
        for el in root.iter():
            if el.tag == 'a':
                href = el.get('href') or ''
                parts = urlsplit(href)
                if parts.scheme or parts.netloc:
                    el.set('target', '_blank')
                    el.set('rel', 'noopener')
                elif href.startswith('#'):
                    if book is not None:
                        el.set('href', '#' + page_anchor(page, href[1:]))
                elif parts.path.endswith('.md'):
                    el.set('href', url_of(resolve(page, parts.path), parts.fragment))
                elif parts.path:
                    el.set('href', reverse('sebastian-help-file', args=[resolve(page, parts.path)]))
            elif el.tag == 'img':
                src = el.get('src') or ''
                parts = urlsplit(src)
                if src and not (parts.scheme or parts.netloc or src.startswith('/')):
                    el.set('src', reverse('sebastian-help-file', args=[resolve(page, parts.path)]))
            if el.tag in _HEADINGS:
                level = int(el.tag[1])
                if book is not None:
                    level = min(level + 1, 6)
                    el.tag = f'h{level}'
                    hid = el.get('id') or ''
                    el.set('id', page_anchor(page) if level == 2 else page_anchor(page, hid))
                headings.append((level, el.get('id') or '', ''.join(el.itertext())))

    html = _markdown(rewrite).convert(site.source(page))
    if book is not None:
        # anchors written as raw HTML (<a id="x"></a>, e.g. generated documents) are not in the
        # Markdown tree: prefix them like the heading ids
        html = _RAW_ANCHOR.sub(lambda m: f'{m.group(1)}{page_anchor(page, m.group(2))}"', html)
    return RenderedPage(html, headings)


def render_book(site, book):
    """[(page, RenderedPage)] of the pages of `book` that exist, for its single page."""
    return [(page, render_page(site, page, book=book)) for page in book.pages if site.exists(page)]


__all__ = ['render_page', 'render_book', 'page_anchor', 'normalize']
