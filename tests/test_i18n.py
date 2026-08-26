"""
Verifies the Italian translation catalog bundled with the library is wired
correctly: locale discovery via INSTALLED_APPS, package-data inclusion, and
that the compiled .mo actually gets used when the active language is 'it'.
"""
import re
from pathlib import Path

import pytest
from django.test import override_settings
from django.utils import translation


GUI = {'HTTP_ACCEPT': 'text/html'}

SEBASTIAN_SRC = Path(__file__).resolve().parent.parent / 'src' / 'sebastian'


@pytest.mark.django_db
def test_default_language_renders_english(auth_client, supplier):
    r = auth_client.get('/gui/suppliers/', **GUI)
    assert r.status_code == 200
    assert b'Filter' in r.content
    assert b'plus-lg"></i> New' in r.content


@pytest.mark.django_db
def test_italian_locale_translates_library_chrome(auth_client, supplier):
    with translation.override('it'):
        r = auth_client.get('/gui/suppliers/', **GUI)
    assert r.status_code == 200
    assert b'Filtra' in r.content
    assert b'plus-lg"></i> Nuovo' in r.content
    # English defaults must be gone, not just the Italian strings present
    assert b'plus-lg"></i> New' not in r.content


@pytest.mark.django_db
def test_italian_locale_translates_bool_yesno(supplier):
    from demo.serializers import SupplierSerializer
    from rest_framework.request import Request
    from rest_framework.test import APIRequestFactory

    factory = APIRequestFactory()
    with translation.override('it'):
        req = Request(factory.get('/'))
        req.sebastian_gui = True
        s = SupplierSerializer(supplier, context={'request': req})
        assert s.data['active__display'] == 'Sì'


@pytest.mark.django_db
def test_translations_not_shadowed_by_django_contrib_admin(auth_client, purchase_request):
    """Regression: django.contrib.admin ships its own Italian catalog that also
    defines plain (context-less) msgids for common words like "Delete", "Save",
    "Home" — with different values than ours for some ("Delete" -> "Cancella",
    "Home" -> "Pagina iniziale"). Because 'django.contrib.admin' is merged AFTER
    'sebastian' in Django's app-translation loading (apps merge in *reversed*
    INSTALLED_APPS order, so apps listed earlier win), an unscoped {% trans %}
    would silently pick up admin's value instead of ours. Every sebastian
    string uses msgctxt "sebastian" (pgettext/{% trans ... context %}) so it
    can never collide with another app's plain-context catalog, regardless of
    merge order.
    """
    with translation.override('it'):
        r = auth_client.get(f'/gui/requests/{purchase_request.pk}/', HTTP_ACCEPT='text/html')
        assert r.status_code == 200
        assert b'Elimina' in r.content        # ours; admin's own catalog says "Cancella"
        assert b'Cancella' not in r.content

        r2 = auth_client.get('/gui/', HTTP_ACCEPT='text/html')
        assert b'Sebastian \xe2\x80\x94 Home' in r2.content   # ours; admin's says "Pagina iniziale"
        assert b'Pagina iniziale' not in r2.content


def test_strans_and_sgettext_usages_are_all_in_the_extraction_registry():
    """Regression: {% strans %} and sgettext() are both invisible to
    `django-admin makemessages` (it only recognizes the real {% trans %}/
    {% blocktrans %} tags and a fixed list of literal Python function names).
    _translatable_strings.py exists specifically to work around that by
    calling the real pgettext() for every such string so extraction finds
    them -- see its docstring and spec §7.3. This test statically scans the
    template/Python source for every {% strans %}/sgettext() call and fails
    if any string isn't ALSO present in the registry, so a forgotten update
    fails CI instead of silently vanishing from the .po file next time
    someone runs makemessages.
    """
    quoted = r'(?:"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\')'

    def _unquote(match):
        return match.group(1) if match.group(1) is not None else match.group(2)

    used = set()
    for html_file in SEBASTIAN_SRC.glob('templates/**/*.html'):
        text = html_file.read_text()
        for m in re.finditer(r'\{%\s*strans\s+' + quoted, text):
            used.add(_unquote(m))

    for py_file in SEBASTIAN_SRC.glob('*.py'):
        if py_file.name in ('i18n.py', '_translatable_strings.py'):
            continue  # the definitions themselves, not call sites
        text = py_file.read_text()
        for m in re.finditer(r'\bsgettext\(\s*' + quoted, text):
            used.add(_unquote(m))

    registry_text = (SEBASTIAN_SRC / '_translatable_strings.py').read_text()
    registered = {
        _unquote(m) for m in re.finditer(
            r"pgettext\(\s*'sebastian',\s*" + quoted, registry_text,
        )
    }

    missing = used - registered
    assert not missing, (
        f'{sorted(missing)} used via {{% strans %}}/sgettext() but missing from '
        'src/sebastian/_translatable_strings.py -- makemessages will silently '
        'drop them from the .po file. Add a matching pgettext(\'sebastian\', ...) '
        'line there.'
    )
