"""
Online help: Markdown pages served inside the GUI, behind the same login.

Pages live in ``SEBASTIAN['HELP']['PAGES_DIR']`` (``*.md``, sub-folders allowed; images and
other files next to them). ``index.md`` in that folder is the table of contents: its H1 is the
title of the help, each H2 a *book* (a main heading, e.g. "User guide") followed by the ordered
list of links to its pages::

    # OPUS help

    Introductory text (optional).

    ## User guide {#guide}

    - [Logging in](gui/login.md)
    - [Lists](gui/lists.md)

Pages use plain Markdown links (``[text](../workflow/phases.md#owner)``) and images
(``![alt](img/home.png)``), relative to the page, so they read the same in GitHub or an IDE
preview; the help rewrites them to help URLs. Each book is also available as a single printable
page (pages in index order, headings numbered, links within the book turned into anchors), to
print as PDF from the browser.

A ViewSet links its own page with ``Sebastian.help_page = 'gui/lists'`` (optionally with
``#anchor``): list and detail pages then show a help icon. Requires the ``help`` extra
(``markdown`` and ``pymdown-extensions``).
"""
from .site import help_url, get_site  # noqa: F401
