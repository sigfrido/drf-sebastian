"""Help views: index, page, single printable page of a book, files (see `sebastian.help`)."""
import mimetypes

from django.http import FileResponse, Http404
from django.shortcuts import render

from .. import app_settings
from .rendering import render_book, render_page
from .site import get_site

# files of the help folder that can be served (images, attachments); never the sources
_SERVED = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.pdf'}


def _site_or_404():
    site = get_site()
    if site is None:
        raise Http404('Help not configured')
    return site


def _context(request, site, page):
    from ..views import gui_page_context
    index = site.index()
    previous, following = site.neighbours(page)
    return {
        **gui_page_context(request),
        'help_title': index.title,
        'help_books': [
            {'slug': b.slug, 'title': b.title,
             'pages': [{'name': p, 'title': site.title(p)} for p in b.pages if site.exists(p)]}
            for b in index.books
        ],
        'help_page': page,
        'help_book': site.book_of(page),
        'help_previous': {'name': previous, 'title': site.title(previous)} if previous else None,
        'help_next': {'name': following, 'title': site.title(following)} if following else None,
        'help_mermaid_js': 'sebastian/vendor/mermaid/mermaid.min.js',
    }


def help_index(request):
    site = _site_or_404()
    return help_page(request, site.index_page)


def help_page(request, page):
    site = _site_or_404()
    if not site.exists(page):
        raise Http404(f'Help page not found: {page}')
    rendered = render_page(site, page)
    context = _context(request, site, page)
    context.update({
        'page_title': f'{site.title(page)} — {context["help_title"]}',
        'help_content': rendered.html,
        'help_has_mermaid': rendered.has_mermaid,
    })
    return render(request, f'sebastian/{context["pack_name"]}/help.html', context)


def help_book(request, slug):
    """Single printable page of a book: its pages in index order (print it as PDF)."""
    site = _site_or_404()
    book = site.book(slug)
    if book is None:
        raise Http404(f'Help book not found: {slug}')
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags
    from django.utils.safestring import mark_safe
    pages = render_book(site, book)
    help_title = site.index().title
    # subtitle of the help (e.g. the application version): below the book title and, as plain
    # text, in the footer of the printed pages
    subtitle = render_to_string('sebastian/_help_subtitle.html', request=request).strip()
    subtitle_text = ' '.join(strip_tags(subtitle).replace('&mdash;', '—').split())
    footer = ' — '.join(t for t in (help_title, book.title, subtitle_text) if t)
    return render(request, 'sebastian/help_book.html', {
        'help_title': help_title,
        'help_subtitle': mark_safe(subtitle),
        # footer of the printed pages (CSS string of @page margin boxes)
        'footer_css': _css_string(footer),
        'book': book,
        'pages': [{'name': name, 'html': r.html, 'headings': r.headings} for name, r in pages],
        'help_has_mermaid': any(r.has_mermaid for _, r in pages),
        'help_mermaid_js': 'sebastian/vendor/mermaid/mermaid.min.js',
        'skin_name': app_settings.skin(),
    })


def _css_string(text):
    from django.utils.safestring import mark_safe
    escaped = ''.join(c if c.isalnum() or c in ' -—.,:;()' else f'\\{ord(c):x} ' for c in text)
    return mark_safe(f'"{escaped}"')


def help_file(request, path):
    site = _site_or_404()
    file = site.file_path(path)
    if file is None or file.suffix.lower() not in _SERVED:
        raise Http404(f'Help file not found: {path}')
    content_type = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
    return FileResponse(open(file, 'rb'), content_type=content_type)
