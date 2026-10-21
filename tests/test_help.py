"""Online help (sebastian.help): index, pages, single printable page of a book, files."""
import re

import pytest
from django.test import override_settings

HTMX = {'HTTP_HX_REQUEST': 'true'}


@pytest.mark.django_db
class TestHelpPages:

    def test_index(self, auth_client):
        r = auth_client.get('/gui/help/')
        html = r.content.decode()
        assert r.status_code == 200
        assert '<h1 id="demo-help">Demo help</h1>' in html
        # table of contents: books with their pages and the link to the single page
        assert 'href="/gui/help/gui/requests/"' in html
        assert 'href="/gui/help/book/guide/"' in html
        assert 'href="/gui/help/book/workflow/"' in html
        assert 'Demo <b>1.2.3</b>' in html   # subtitle below the title of the help

    def test_page_links_images_and_navigation(self, auth_client):
        html = auth_client.get('/gui/help/gui/requests/').content.decode()
        # links to other pages (relative, with anchor), anchors in the page, images
        assert 'href="/gui/help/gui/suppliers/#adding-a-supplier"' in html
        assert 'href="/gui/help/workflow/"' in html
        assert 'href="#submitting"' in html
        assert 'src="/gui/help/file/img/pixel.png"' in html
        assert 'class="admonition note"' in html
        assert '<table>' in html
        # previous / next in index order, across books
        assert re.search(r'href="/gui/help/gui/suppliers/">Suppliers', html)
        # the help styles are in the page (not hidden by a cached sebastian.css): images no
        # wider than the column
        assert '.sb-help-content .mermaid svg {\n    max-width: 100% !important;' in html
        # no diagram: mermaid.js not loaded
        assert 'mermaid.min.js' not in html

    def test_external_links_and_mermaid(self, auth_client):
        html = auth_client.get('/gui/help/gui/suppliers/').content.decode()
        assert 'href="https://www.djangoproject.com/" rel="noopener" target="_blank"' in html
        html = auth_client.get('/gui/help/workflow/').content.decode()
        assert '<div class="mermaid">stateDiagram-v2' in html
        # Markdown inside <div ... markdown="1"> (md_in_html), e.g. a part wrapped to be styled
        assert '<div class="demo-states">' in html
        assert '<h2 id="draft">Draft</h2>' in html and '<em>draft</em>' in html
        assert 'mermaid/mermaid.min.js' in html

    def test_book_single_page(self, auth_client):
        r = auth_client.get('/gui/help/book/guide/')
        html = r.content.decode()
        assert r.status_code == 200
        assert '<h1>User guide</h1>' in html
        # pages as chapters (h2, id = page), their sections one level down with prefixed ids
        assert '<h2 id="gui-requests">Requests</h2>' in html
        assert '<h3 id="gui-requests--submitting">Submitting</h3>' in html
        assert html.index('id="gui-requests"') < html.index('id="gui-suppliers"')
        # links inside the book become anchors, outside the book stay page links
        assert 'href="#gui-suppliers--adding-a-supplier"' in html
        assert 'href="#gui-requests--submitting"' in html
        assert 'href="/gui/help/workflow/"' in html
        # anchors written as raw HTML are prefixed too
        assert '<a id="gui-suppliers--raw-anchor"></a>' in html
        assert 'href="#gui-suppliers--raw-anchor"' in html
        # table of contents and printed footer
        assert '<a href="#gui-requests--submitting">Submitting</a>' in html
        assert '@bottom-right' in html and 'Demo help' in html
        # subtitle of the help (testproject: the version) below the book title and, as plain
        # text, in the printed footer
        assert '<p class="subtitle">Demo <b>1.2.3</b></p>' in html
        assert 'content: "Demo help — User guide — Demo 1.2.3"' in html

    def test_files(self, auth_client):
        r = auth_client.get('/gui/help/file/img/pixel.png')
        assert r.status_code == 200 and r['Content-Type'] == 'image/png'
        # never the sources, nothing outside the folder
        assert auth_client.get('/gui/help/file/index.md').status_code == 404
        assert auth_client.get('/gui/help/file/../settings.py').status_code == 404
        assert auth_client.get('/gui/help/file/img/../../settings.py').status_code == 404

    def test_missing(self, auth_client):
        assert auth_client.get('/gui/help/nope/').status_code == 404
        assert auth_client.get('/gui/help/book/nope/').status_code == 404
        assert auth_client.get('/gui/help/../settings/').status_code == 404

    def test_login_required(self, client):
        r = client.get('/gui/help/')
        assert r.status_code == 302 and r['Location'].startswith('/gui/login/')

    def test_contextual_help_icon(self, auth_client):
        html = auth_client.get('/gui/requests/', **HTMX).content.decode()
        assert 'href="/gui/help/gui/requests/#submitting"' in html
        # ViewSets without help_page: no icon
        html = auth_client.get('/gui/suppliers/', **HTMX).content.decode()
        assert '/gui/help/' not in html


def test_help_url_tag():
    from django.template import Context, Template
    t = Template('{% load sebastian_tags %}{% help_url %}|{% help_url "workflow" %}')
    assert t.render(Context()) == '/gui/help/|/gui/help/workflow/'


def test_help_off_without_pages_dir(settings):
    from sebastian.help import help_url
    settings.SEBASTIAN = {**settings.SEBASTIAN, 'HELP': {}}
    assert help_url('workflow') == ''


@pytest.mark.django_db
def test_project_stylesheets(auth_client, settings):
    settings.SEBASTIAN = {**settings.SEBASTIAN,
                          'HELP': {**settings.SEBASTIAN['HELP'], 'CSS': ['demo/help.css']}}
    for url in ('/gui/help/gui/requests/', '/gui/help/book/guide/'):
        html = auth_client.get(url).content.decode()
        assert '<link rel="stylesheet" href="/static/demo/help.css">' in html, url
