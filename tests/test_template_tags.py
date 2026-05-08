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
    data = {'id': 1, 'name': 'Acme', 'name__display': 'Acme Srl'}
    assert data_keys(data) == ['id', 'name']


def test_data_keys_excludes_sebastian_prefix():
    data = {'id': 1, 'sebastian__str': 'Acme Srl'}
    assert data_keys(data) == ['id']


def test_data_keys_non_dict_returns_empty():
    assert data_keys(None) == []
    assert data_keys('string') == []
    assert data_keys(42) == []


def test_data_keys_empty_dict():
    assert data_keys({}) == []


# ── display_value ─────────────────────────────────────────────────────────────

def test_display_value_prefers_display_key():
    data = {'fornitore': 1, 'fornitore__display': 'Acme Srl'}
    assert display_value(data, 'fornitore') == 'Acme Srl'


def test_display_value_falls_back_when_display_missing():
    data = {'name': 'Acme'}
    assert display_value(data, 'name') == 'Acme'


def test_display_value_skips_empty_display_string():
    data = {'name': 'Acme', 'name__display': ''}
    assert display_value(data, 'name') == 'Acme'


def test_display_value_skips_none_display():
    data = {'name': 'Acme', 'name__display': None}
    assert display_value(data, 'name') == 'Acme'


def test_display_value_missing_key_returns_empty():
    assert display_value({'a': 1}, 'missing') == ''


def test_display_value_non_dict_returns_empty():
    assert display_value(None, 'key') == ''


# ── get_item ──────────────────────────────────────────────────────────────────

def test_get_item_dict():
    assert get_item({'key': 'val'}, 'key') == 'val'


def test_get_item_missing_returns_empty():
    assert get_item({'key': 'val'}, 'missing') == ''


def test_get_item_double_underscore_key():
    # Django template variables cannot access __ keys but our filter can
    data = {'sebastian__str': 'Acme Srl'}
    assert get_item(data, 'sebastian__str') == 'Acme Srl'


def test_get_item_none_returns_empty():
    assert get_item(None, 'key') == ''


# ── input_type ────────────────────────────────────────────────────────────────

def test_input_type_integer():
    from rest_framework import serializers
    assert input_type(serializers.IntegerField()) == 'number'


def test_input_type_boolean():
    from rest_framework import serializers
    assert input_type(serializers.BooleanField()) == 'checkbox'


def test_input_type_date():
    from rest_framework import serializers
    assert input_type(serializers.DateField()) == 'date'


def test_input_type_email():
    from rest_framework import serializers
    assert input_type(serializers.EmailField()) == 'email'


def test_input_type_char_defaults_to_text():
    from rest_framework import serializers
    assert input_type(serializers.CharField()) == 'text'
