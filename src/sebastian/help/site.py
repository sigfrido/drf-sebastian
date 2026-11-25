"""Help pages on disk: table of contents (index.md), books, page titles (see `sebastian.help`)."""
import posixpath
import re
from dataclasses import dataclass, field
from pathlib import Path

from django.urls import reverse, NoReverseMatch
from django.utils.text import slugify

from .. import app_settings

_HEADING = re.compile(r'^(#{1,6})\s+(.*?)\s*(?:\{#([\w-]+)\})?\s*#*\s*$')
_LIST_LINK = re.compile(r'^\s*[-*+]\s+\[([^\]]*)\]\(([^)\s]+)\)')


@dataclass
class Book:
    slug: str
    title: str
    pages: list = field(default_factory=list)   # page names, in index order


@dataclass
class Index:
    title: str
    books: list   # [Book]


def normalize(page: str) -> str:
    """Page name from a path relative to the pages folder: no leading './' or '/', no '.md'."""
    page = posixpath.normpath(page.strip().lstrip('/'))
    return page[:-3] if page.endswith('.md') else page


def resolve(base_page: str, href: str) -> str:
    """Name of the page or file `href` (relative to `base_page`) points to."""
    return normalize(posixpath.join(posixpath.dirname(base_page), href))


class HelpSite:
    """Help pages folder. Titles and index are cached and reloaded when the files change."""

    def __init__(self, root, index='index'):
        self.root = Path(root).resolve()
        self.index_page = index
        self._titles = {}    # page -> (mtime, title)
        self._index = None   # (mtime, Index)

    # ------------------------------------------------------------------ files

    def file_path(self, name: str):
        """Absolute path of a file of the help, or None if it is outside the folder or missing."""
        name = posixpath.normpath(name.lstrip('/'))
        if name.startswith('..') or '\\' in name:
            return None
        path = (self.root / name).resolve()
        if self.root not in path.parents or not path.is_file():
            return None
        return path

    def page_file(self, page: str):
        return self.file_path(f'{normalize(page)}.md')

    def exists(self, page: str) -> bool:
        return self.page_file(page) is not None

    def source(self, page: str) -> str:
        path = self.page_file(page)
        return path.read_text(encoding='utf-8') if path else ''

    def title(self, page: str) -> str:
        """First H1 of the page (its name if it has none)."""
        path = self.page_file(page)
        if path is None:
            return page
        mtime = path.stat().st_mtime
        cached = self._titles.get(page)
        if cached and cached[0] == mtime:
            return cached[1]
        title = page
        for line in path.read_text(encoding='utf-8').splitlines():
            m = _HEADING.match(line)
            if m and len(m.group(1)) == 1:
                title = m.group(2)
                break
        self._titles[page] = (mtime, title)
        return title

    # ------------------------------------------------------------------ index

    def index(self) -> Index:
        path = self.page_file(self.index_page)
        mtime = path.stat().st_mtime if path else None
        if self._index and self._index[0] == mtime:
            return self._index[1]
        title, books, book = '', [], None
        for line in (path.read_text(encoding='utf-8').splitlines() if path else []):
            heading = _HEADING.match(line)
            if heading:
                level, text, slug = len(heading.group(1)), heading.group(2), heading.group(3)
                if level == 1 and not title:
                    title = text
                elif level == 2:
                    book = Book(slug=slug or slugify(text), title=text)
                    books.append(book)
                continue
            link = _LIST_LINK.match(line)
            if link and book is not None and link.group(2).split('#')[0].endswith('.md'):
                page = resolve(self.index_page, link.group(2).split('#')[0])
                if page not in book.pages:
                    book.pages.append(page)
        index = Index(title=title or 'Help', books=books)
        self._index = (mtime, index)
        return index

    def book(self, slug: str):
        return next((b for b in self.index().books if b.slug == slug), None)

    def book_of(self, page: str):
        return next((b for b in self.index().books if page in b.pages), None)

    # ------------------------------------------------------------------ visibility

    def visible_books(self, request):
        """Books of the index the user of `request` can see (``HELP['BOOKS']``)."""
        return [b for b in self.index().books if book_visible(b, request)]

    def index_source(self, request) -> str:
        """Source of the index page without the sections (H2 and what follows, up to the next
        H2) of the books the user of `request` cannot see."""
        hidden = {b.title for b in self.index().books if not book_visible(b, request)}
        lines, skipping = [], False
        for line in self.source(self.index_page).splitlines():
            heading = _HEADING.match(line)
            if heading and len(heading.group(1)) <= 2:
                skipping = len(heading.group(1)) == 2 and heading.group(2) in hidden
            if not skipping:
                lines.append(line)
        return '\n'.join(lines)

    def page_visible(self, page: str, request) -> bool:
        """True if the page is in a book the user can see, or in no book (e.g. the index)."""
        books = [b for b in self.index().books if page in b.pages]
        return not books or any(book_visible(b, request) for b in books)

    def neighbours(self, page: str, request=None):
        """(previous, next) page in index order, across books; None at the ends. With `request`,
        only pages of the books the user can see."""
        books = self.index().books if request is None else self.visible_books(request)
        order = [p for b in books for p in b.pages]
        if page not in order:
            return None, None
        i = order.index(page)
        return (order[i - 1] if i > 0 else None), (order[i + 1] if i < len(order) - 1 else None)


def book_visible(book, request) -> bool:
    """True if the user of `request` can see `book`: its permission in ``HELP['BOOKS']``
    (permission-like callable or dotted path, called with ``obj=None``), visible to all if it
    has none."""
    permission = app_settings.help_book_permissions().get(book.slug)
    if permission is None:
        return True
    if isinstance(permission, str):
        from django.utils.module_loading import import_string
        permission = import_string(permission)
    return bool(permission(request, None))


_site = None


def get_site():
    """The `HelpSite` of ``SEBASTIAN['HELP']``, or None if the help is not configured."""
    global _site
    root = app_settings.help_pages_dir()
    if not root:
        return None
    if _site is None or _site.root != Path(root).resolve():
        _site = HelpSite(root, app_settings.help_index_page())
    return _site


def help_url(page: str = '') -> str:
    """URL of a help page (``'gui/lists'`` or ``'gui/lists#filters'``), of the index if
    `page` is empty; '' if the help is not configured."""
    if get_site() is None:
        return ''
    page, _, anchor = (page or '').partition('#')
    try:
        url = (reverse('sebastian-help-page', args=[normalize(page)]) if page
               else reverse('sebastian-help-index'))
    except NoReverseMatch:
        return ''
    return f'{url}#{anchor}' if anchor else url
