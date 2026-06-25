/**
 * Sebastian widgets — Tom Select initialization for ordering, typeahead, and cascading fields.
 *
 * Expects Tom Select CSS + JS already loaded (added by htmx/base.html).
 * Re-initializes on htmx:afterSwap so partial HTMX updates keep working.
 */

(function () {
  'use strict';

  // Track initialized elements to avoid double-init on HTMX partial swaps.
  const _initialized = new WeakSet();

  // ── Ordering widget ────────────────────────────────────────────────────────
  // Rendered as <select class="sb-ordering" multiple data-max-items="N"
  //              data-current="field1,-field2">
  // A hidden <input id="sb-ordering-value" name="ordering"> carries the value.
  // Form is submitted explicitly by the user clicking Filtra.

  function initOrdering() {
    document.querySelectorAll('select.sb-ordering').forEach(function (el) {
      if (_initialized.has(el)) return;
      _initialized.add(el);

      var maxItems    = parseInt(el.dataset.maxItems || '3', 10);
      var current     = (el.dataset.current || '').split(',').filter(Boolean);
      var hiddenInput = document.getElementById('sb-ordering-value');

      new TomSelect(el, {
        maxItems:    maxItems,
        plugins:     ['remove_button'],
        placeholder: el.getAttribute('placeholder') || 'Ordina per…',
        // Pass current values via the items setting so TomSelect pre-selects
        // them in the correct order during its own setup phase.
        items: current,
        onInitialize: function () {
          // Items already loaded by the 'items' setting; sync the hidden input.
          if (hiddenInput) hiddenInput.value = current.join(',');
        },
        onItemAdd: function (value) {
          // Mutual exclusion: remove the opposite direction for the same field.
          // 'ragione_sociale' and '-ragione_sociale' cannot both be selected.
          var opposite = value.startsWith('-') ? value.slice(1) : ('-' + value);
          if (this.items.indexOf(opposite) !== -1) {
            this.removeItem(opposite, true);  // silent — won't retrigger onChange
          }
          if (hiddenInput) hiddenInput.value = this.items.join(',');
        },
        onItemRemove: function () {
          if (hiddenInput) hiddenInput.value = this.items.join(',');
        },
      });
    });
  }

  // ── Typeahead widget ───────────────────────────────────────────────────────
  // Rendered as <select class="sb-typeahead"
  //              data-typeahead-url="/api/…/typeahead/"
  //              data-typeahead-chars="2"
  //              data-cascade-field="field_name">   ← optional, set by cascade

  function initTypeahead() {
    document.querySelectorAll('select.sb-typeahead').forEach(function (el) {
      if (_initialized.has(el)) return;
      _initialized.add(el);

      var url          = el.dataset.typeaheadUrl  || '';
      var minChars     = parseInt(el.dataset.typeaheadChars || '2', 10);
      var cascadeField = el.dataset.cascadeField  || '';

      new TomSelect(el, {
        valueField:    'value',
        labelField:    'label',
        // Also search 'text' — options pre-loaded from the native <select> use
        // option.textContent stored as 'text', not 'label'.
        searchField:   ['label', 'text'],
        // scores[7] === scores['7'] in JS — hideSelected would delete API results whose integer PK matches the native option's string value.
        hideSelected:  false,
        preload:       minChars === 0,
        // Render both remote options ({label}) and native-<select> options ({text}).
        render: {
          option: function (data, escape) {
            return '<div>' + escape(data.label || data.text || '') + '</div>';
          },
          item: function (data, escape) {
            return '<div>' + escape(data.label || data.text || '') + '</div>';
          },
        },
        load: function (query, callback) {
          if (query.length < minChars) { callback(); return; }
          var params = new URLSearchParams({ q: query });
          // Append cascade parent values if present.
          if (cascadeField) {
            var form = el.closest('form');
            if (form) {
              var cascadeGroups = _parseCascadeGroups(form);
              var extras = _cascadeParamsFor(form, cascadeField, cascadeGroups);
              extras.forEach(function (kv) { params.set(kv[0], kv[1]); });
            }
          }
          fetch(url + '?' + params.toString())
            .then(function (r) { return r.json(); })
            .then(callback)
            .catch(function () { callback(); });
        },
        // TomSelect auto-selects any <option selected> from the native <select>,
        // so no onInitialize hook is needed.
      });
    });
  }

  // ── Cascading dropdowns ────────────────────────────────────────────────────
  // The <form> carries data-cascade-groups='[["field_a","field_b","field_c"]]'.
  // Each cascaded <select> has data-cascade-field="field_name".

  function _parseCascadeGroups(form) {
    try {
      return JSON.parse(form.dataset.cascadeGroups || '[]');
    } catch (_) {
      return [];
    }
  }

  function _cascadeParamsFor(form, fieldName, groups) {
    // Return [[paramName, value], …] for all ancestors of fieldName in any group.
    var params = [];
    groups.forEach(function (group) {
      var idx = group.indexOf(fieldName);
      if (idx <= 0) return;
      for (var i = 0; i < idx; i++) {
        var ancestorName = group[i];
        var ancestorEl   = form.querySelector('[data-cascade-field="' + ancestorName + '"]');
        if (ancestorEl) {
          var ts = ancestorEl.tomselect;
          var val = ts ? ts.getValue() : ancestorEl.value;
          if (val) params.push([ancestorName, val]);
        }
      }
    });
    return params;
  }

  function initCascade() {
    document.querySelectorAll('form[data-cascade-groups]').forEach(function (form) {
      var groups = _parseCascadeGroups(form);
      if (!groups.length) return;

      groups.forEach(function (group) {
        group.forEach(function (fieldName, idx) {
          if (idx === group.length - 1) return; // last field has no downstream
          var el = form.querySelector('[data-cascade-field="' + fieldName + '"]');
          if (!el || !el.tomselect) return;

          el.tomselect.on('change', function () {
            // Clear and reload all downstream fields.
            for (var d = idx + 1; d < group.length; d++) {
              var downstreamName = group[d];
              var downEl = form.querySelector('[data-cascade-field="' + downstreamName + '"]');
              if (!downEl || !downEl.tomselect) continue;
              var dTs = downEl.tomselect;
              dTs.clear();
              dTs.clearOptions();
              // If typeahead_chars=0, trigger an immediate load.
              var minChars = parseInt(downEl.dataset.typeaheadChars || '2', 10);
              if (minChars === 0) {
                dTs.load('');
              }
            }
          });
        });
      });
    });
  }

  // ── Simple TomSelect enhancement ──────────────────────────────────────────
  // Rendered as <select class="ts-select"> — static options already in the HTML,
  // no remote load. Adds search + keyboard nav to any plain <select>.

  function initTsSelect() {
    document.querySelectorAll('select.ts-select').forEach(function (el) {
      if (_initialized.has(el)) return;
      _initialized.add(el);
      new TomSelect(el, {
        allowEmptyOption: true,
      });
    });
  }

  // ── Filter form cleanup ────────────────────────────────────────────────────
  // Strip empty params and NullBooleanSelect 'unknown' sentinel from HTMX requests.

  document.addEventListener('htmx:configRequest', function (evt) {
    var elt = evt.detail.elt;
    if (!elt || !elt.matches || !elt.matches('#sb-filter-form')) return;
    var params = evt.detail.parameters;
    Object.keys(params).forEach(function (key) {
      if (params[key] === '' || params[key] === 'unknown') {
        delete params[key];
      }
    });
  });

  function initFilterForm() {
    var form = document.getElementById('sb-filter-form');
    if (!form || _initialized.has(form)) return;
    _initialized.add(form);
    // Replace NullBooleanSelect 'unknown' sentinel label with a blank so it
    // reads as "no selection" rather than the string "Unknown".
    form.querySelectorAll('select option[value="unknown"]').forEach(function (opt) {
      opt.text = '';
    });
  }

  // ── Entrypoint ─────────────────────────────────────────────────────────────

  function initAll() {
    initOrdering();
    initTypeahead();
    initTsSelect();
    initCascade();
    initFilterForm();
  }

  document.addEventListener('DOMContentLoaded', initAll);
  document.addEventListener('htmx:afterSwap',   initAll);
}());
