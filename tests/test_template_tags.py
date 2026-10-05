"""
Unit tests for sebastian_tags template filters.
No database required — pure Python.
"""
import pytest
from sebastian.templatetags.sebastian_tags import (
    data_keys, display_value, get_item, input_type,
)


# ── data_keys ─────────────────────────────────────────────────────────────────

def test_data_keys_excludes_display_keys():
    data = {'id': 1, 'name': 'Acme', 'name__display': 'Acme Inc'}
    assert data_keys(data) == ['id', 'name']


def test_data_keys_excludes_sebastian_prefix():
    data = {'id': 1, 'sebastian__str': 'Acme Inc'}
    assert data_keys(data) == ['id']


def test_data_keys_non_dict_returns_empty():
    assert data_keys(None) == []
    assert data_keys('string') == []
    assert data_keys(42) == []


def test_data_keys_empty_dict():
    assert data_keys({}) == []


# ── display_value ─────────────────────────────────────────────────────────────

def test_display_value_prefers_display_key():
    data = {'supplier': 1, 'supplier__display': 'Acme Inc'}
    assert display_value(data, 'supplier') == 'Acme Inc'


def test_display_value_falls_back_when_display_missing():
    data = {'name': 'Acme'}
    assert display_value(data, 'name') == 'Acme'


def test_display_value_skips_empty_display_string():
    data = {'name': 'Acme', 'name__display': ''}
    assert display_value(data, 'name') == 'Acme'


def test_display_value_skips_none_display():
    data = {'name': 'Acme', 'name__display': None}
    assert display_value(data, 'name') == 'Acme'


def test_display_value_none_returns_empty():
    # nullable date/decimal fields: never the literal "None" in the detail view
    assert display_value({'budget': None}, 'budget') == ''
    assert display_value({'budget': 0}, 'budget') == 0


def test_display_value_missing_key_returns_empty():
    assert display_value({'a': 1}, 'missing') == ''


def test_display_value_non_dict_returns_empty():
    assert display_value(None, 'key') == ''


def test_display_value_empty_string_does_not_leak_str_method():
    # Regression: getattr('', 'title') would otherwise return the bound
    # str.title method instead of a missing-value default (any other str
    # method name — upper, strip, replace, ... — triggers the same bug).
    assert display_value('', 'title') == ''
    assert display_value('', 'upper') == ''


# ── get_item ──────────────────────────────────────────────────────────────────

def test_get_item_dict():
    assert get_item({'key': 'val'}, 'key') == 'val'


def test_get_item_missing_returns_empty():
    assert get_item({'key': 'val'}, 'missing') == ''


def test_get_item_double_underscore_key():
    # Django template variables cannot access __ keys but our filter can
    data = {'sebastian__str': 'Acme Inc'}
    assert get_item(data, 'sebastian__str') == 'Acme Inc'


def test_get_item_none_returns_empty():
    assert get_item(None, 'key') == ''


def test_get_item_empty_string_does_not_leak_str_method():
    # Regression: create_form() context used to omit 'instance' entirely, and
    # Django silently resolves a missing template variable to '' rather than
    # None — get_item('', 'title') then returned <built-in method title of
    # str ...> instead of '', because every str genuinely has a .title method.
    assert get_item('', 'title') == ''
    assert get_item('', 'upper') == ''


# ── input_type ────────────────────────────────────────────────────────────────

def test_input_type_integer():
    from rest_framework import serializers
    assert input_type(serializers.IntegerField()) == 'number'


def test_input_type_boolean():
    from rest_framework import serializers
    assert input_type(serializers.BooleanField()) == 'bool-select'


def test_input_type_date():
    from rest_framework import serializers
    assert input_type(serializers.DateField()) == 'date'


def test_input_type_email():
    from rest_framework import serializers
    assert input_type(serializers.EmailField()) == 'email'


def test_input_type_char_defaults_to_text():
    from rest_framework import serializers
    assert input_type(serializers.CharField()) == 'text'


# ---- form_input_value ------------------------------------------------------

def test_form_input_value_none_and_missing_are_empty():
    from sebastian.templatetags.sebastian_tags import form_input_value
    assert form_input_value({'note': None}, 'note') == ''
    assert form_input_value({}, 'note') == ''
    assert form_input_value(None, 'note') == ''


def test_form_input_value_keeps_zero():
    """0 is a real value: it must not be rendered as an empty input."""
    from sebastian.templatetags.sebastian_tags import form_input_value
    assert form_input_value({'peso': 0}, 'peso') == '0'


def test_form_input_value_truncates_datetime_to_minute():
    from sebastian.templatetags.sebastian_tags import form_input_value
    assert form_input_value({'d': '2026-09-29T10:15:30+02:00'}, 'd') == '2026-09-29T10:15'


def test_textarea_renders_none_as_empty():
    """A nullable TextField (value None) must not show the literal "None" in the form."""
    from django.template import Context, Template
    out = Template(
        "{% load sebastian_tags %}"
        "<textarea>{% if instance %}{{ instance|get_item:'note'|default_if_none:'' }}{% endif %}</textarea>"
    ).render(Context({'instance': {'note': None}}))
    assert out == '<textarea></textarea>'


class TestButtonStyles:
    """Built-in semantic styles resolve to solid (filled) Bootstrap buttons."""

    def test_builtin_styles_are_solid(self):
        from sebastian.templatetags.sebastian_tags import btn_class
        for style in ('new', 'edit', 'delete', 'view', 'info', 'warning', 'success', 'secondary'):
            assert 'outline' not in btn_class(style)
        assert btn_class('view') == 'btn-secondary'

    def test_unknown_style_falls_back_to_bootstrap_modifier(self):
        from sebastian.templatetags.sebastian_tags import btn_class
        assert btn_class('primary') == 'btn-primary'


class TestActionOrder:
    """gui_config['order']: ordered actions first (ascending), then the others by name."""

    def test_order(self, rf):
        from sebastian.mixins import _SebastianBaseMixin

        def _action(**cfg):
            def method(self, request):
                pass
            method.mapping = {'get': 'x'}
            method.gui_config = {'label': 'x', **cfg}
            return method

        class View(_SebastianBaseMixin):
            alfa = _action()
            beta = _action(order=20)
            gamma = _action(order=10)
            delta = _action()

        view = View()
        view.request = rf.get('/')
        names = [a['name'] for a in view.get_available_actions()]
        assert names == ['gamma', 'beta', 'alfa', 'delta']



class TestLoginUrlTag:
    """sb_login_url: SEBASTIAN['LOGIN_URL'], else Django's LOGIN_URL (expired-session handling)."""

    def test_sebastian_setting_wins(self, settings):
        from sebastian.templatetags.sebastian_tags import sb_login_url
        settings.SEBASTIAN = {**getattr(settings, 'SEBASTIAN', {}), 'LOGIN_URL': '/gui/login/'}
        settings.LOGIN_URL = '/accounts/login/'
        assert sb_login_url() == '/gui/login/'

    def test_falls_back_to_django_login_url(self, settings):
        from sebastian.templatetags.sebastian_tags import sb_login_url
        settings.SEBASTIAN = {k: v for k, v in getattr(settings, 'SEBASTIAN', {}).items()
                              if k != 'LOGIN_URL'}
        settings.LOGIN_URL = '/accounts/login/'
        assert sb_login_url() == '/accounts/login/'
