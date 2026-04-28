# drf-sebastian Framework Specification

See README.md for an introduction.

**Version**: 0.2.0  
**Last Updated**: 2026-04-28  
**Author**: Sig  
**Status**: Architecture settled — Phase 1 scaffold complete

---

## 1. Problem Statement

**If we need both an API and a Web GUI for our application**, we may choose between two approaches:

1. A traditional Django Web Application with a DRF API: duplication of logic between API views/serializers and GUI views/forms. Some logic may live in Models too.
2. A JavaScript SPA with a Django DRF API: duplication between client and server side; SPA apps are powerful but require more development time, a challenging pipeline and may give SEO problems. Data-driven GUI synchronisation (e.g. enabling/disabling controls) is time-consuming and often litters code with checks already made server-side.

In both cases, duplication raises development cost and may produce inconsistencies.

---

## 2. The Sebastian Solution

**API-First** (single source of truth) with **Built-in GUI**.

Sebastian overloads existing DRF ViewSets, Serializers, and Routers with GUI-specific metadata so the same API endpoints produce both JSON data and HTML GUI fragments. The same business logic, permissions, and validation applies to both — there is no duplication.

Based on HTMX, Sebastian provides a GUI framework with standard placeholders (menu bar, status bar, content frame) and standard concepts (actions, lists, details, edit forms, inline entities, widgets).

Sebastian enriches the API with GUI-related and context-related metadata:

- An entity's fields are grouped in **field groups**: each group can have visibility and editability rules for the current user. When no groups are defined, all fields are accessible with default permissions. Groups are rendered as tabs or sections in detail and form views.
- **Entity groups** represent weak-entity (inline) relations — e.g. attachments owned by a parent record. They are managed via HTMX-powered per-row modal forms with no page reload, one modal per API endpoint.
- The API returns, for each instance, the actions available for the current user (may differ for list and detail views).
- `enabled`/`visible` concepts apply to actions and field groups and map directly to GUI control visibility and availability.

Field groups are especially useful in workflows, where different users may access different data in different work phases.

GUI URLs mirror API URLs:

```
GET  /api/richieste/             → JSON list
GET  /api/richieste/123/         → JSON detail
POST /api/richieste/123/approva/ → JSON action result

GET  /gui/richieste/             → HTML list with filters
GET  /gui/richieste/new/         → HTML create form       ← GUI-only
GET  /gui/richieste/123/         → HTML detail with action buttons
GET  /gui/richieste/123/edit/    → HTML edit form         ← GUI-only
POST /gui/richieste/123/approva/ → HTML fragment (HTMX)
```

**Minimal adoption example** — add two mixins to existing DRF code:

```python
from sebastian.mixins import GUIMixin
from sebastian.serializers import GUISerializer

class RichiestaSerializer(GUISerializer, serializers.ModelSerializer):
    class Meta:
        model  = Richiesta
        fields = '__all__'

class RichiestaViewSet(GUIMixin, viewsets.ModelViewSet):  # ← add GUIMixin
    queryset         = Richiesta.objects.all()
    serializer_class = RichiestaSerializer
    filterset_fields = ['stato']
```

With a full `Sebastian` inner class and `@action` metadata (see §3.4 and §4.4):

```python
from sebastian.mixins import GUIMixin
from sebastian.serializers import GUISerializer
from sebastian.config import FieldGroup, EntityGroup
from sebastian.decorators import action

class RichiestaViewSet(GUIMixin, viewsets.ModelViewSet):
    queryset         = Richiesta.objects.select_related('fornitore').all()
    serializer_class = RichiestaSerializer

    class Sebastian:
        groups = [
            FieldGroup('generale', ['titolo', 'descrizione', 'budget', 'stato'],
                       label='Generale'),
            FieldGroup('direzione', ['note_direttore', 'cig'],
                       label='Direzione',
                       edit_permission=lambda req, obj: req.user.groups.filter(name='direttori').exists()),
            EntityGroup('allegati', model=Allegato, serializer_class=AllegatoSerializer,
                        label='Allegati', related_field='richiesta'),
        ]

    @action(detail=True, methods=['post'],
            permission_classes=[IsAdminUser],
            gui_config={
                'label':   'Approva',
                'icon':    'check-circle',
                'color':   'success',
                'confirm': 'Confermi approvazione?',
                'position': 'detail',
            })
    def approva(self, request, pk=None):
        instance = self.get_object()
        instance.stato = 'approvata'
        instance.save()
        return Response(self.get_serializer(instance).data)
```

---

## 3. Architecture

### 3.1 Component Overview

```
src/sebastian/
├── mixins.py        GUIMixin — ViewSet mixin for HTML rendering + GUI-only actions
├── routers.py       GUIRouter — mirrors DRF router registry to /gui/ URL space
├── renderers.py     SebastianHTMLRenderer — renders action-appropriate template
├── serializers.py   GUISerializer — enforces FieldGroup permissions at serializer layer
├── config.py        FieldGroup, EntityGroup — declared in ViewSet.Sebastian.groups
├── decorators.py    @action — DRF @action extended with gui_config metadata
├── dispatch.py      call() — internal ViewSet dispatch for cascading actions
└── templatetags/
    └── sebastian_tags.py   get_item, input_type, field_value filters
```

### 3.2 URL Routing

The user registers an API router normally, then passes it to `GUIRouter`:

```python
# urls.py
from rest_framework.routers import DefaultRouter
from sebastian.routers import GUIRouter
from selco.views import RichiestaViewSet

api_router = DefaultRouter()
api_router.register('richieste', RichiestaViewSet, basename='richiesta')

gui_router = GUIRouter(api_router)   # ← reads api_router.registry

urlpatterns = [
    path('api/', include(api_router.urls)),
    path('gui/', include(gui_router.urls)),  # ← auto-mirrored
]
```

`GUIRouter` walks `api_router.registry` and for each registered ViewSet produces:

| Route | Method | ViewSet action |
|---|---|---|
| `/gui/{prefix}/` | GET | `list` |
| `/gui/{prefix}/new/` | GET | `create_form` ¹ |
| `/gui/{prefix}/<pk>/` | GET | `retrieve` |
| `/gui/{prefix}/<pk>/edit/` | GET | `update_form` ¹ |
| `/gui/{prefix}/<pk>/{url_path}/` | * | mirrored `@action` (detail) |
| `/gui/{prefix}/{url_path}/` | * | mirrored `@action` (list-level) |

¹ Only added when the ViewSet has `GUIMixin`. These have no API equivalent.

`@action` routes are only mirrored when the action carries `gui_config` metadata.

Non-data views (dashboard, help, options) are wired manually in `urls.py`. Sebastian provides the shell template; the developer provides the view.

### 3.3 Content Negotiation and GUI Detection

GUI routes force `format='html'` via URL kwargs, which causes DRF's built-in content negotiation to select `SebastianHTMLRenderer` (registered with `format = 'html'`). This is mechanism **A**.

A convenience flag **B** is also set — `request.sebastian_gui = True` — via a lightweight view wrapper in `GUIRouter` and via `GUIMixin.initial()`. It is available for debug tooling and custom ViewSet hooks; it carries no semantic weight in the core.

```python
# GUIRouter wraps every view:
def _wrap(view):
    def wrapped(request, *args, **kwargs):
        request.sebastian_gui = True     # B: debug flag
        return view(request, *args, **kwargs)
    return wrapped

# GUIMixin.initial() also sets it after content negotiation:
def initial(self, request, *args, **kwargs):
    super().initial(request, *args, **kwargs)
    if getattr(request, 'accepted_renderer', None):
        if request.accepted_renderer.format == 'html':
            request.sebastian_gui = True
```

### 3.4 The `Sebastian` Inner Class

Every ViewSet that uses `GUIMixin` may declare a `Sebastian` inner class to configure its GUI behaviour. The class is named `Sebastian` (not `GUIConfig`) because its metadata applies to both the API layer (serializer field-group permission enforcement) and the GUI layer (template rendering, action buttons).

```python
class RichiestaViewSet(GUIMixin, viewsets.ModelViewSet):

    class Sebastian:
        # Field groups and entity groups — declaration order is respected in GUI
        groups = [
            FieldGroup(...),
            EntityGroup(...),
        ]

        # Per-action template overrides (optional)
        list_template   = 'selco/richieste_list.html'
        detail_template = 'selco/richieste_detail.html'
        form_template   = 'selco/richieste_form.html'
```

When no `Sebastian` class is declared, all fields are shown in a single flat group with default permissions.

### 3.5 Renderer

`SebastianHTMLRenderer` selects the appropriate template based on `view.action` and any per-action overrides declared in `ViewSet.Sebastian`:

```python
ACTION_TEMPLATES = {
    'list':        'sebastian/list.html',
    'retrieve':    'sebastian/detail.html',
    'create_form': 'sebastian/form.html',
    'update_form': 'sebastian/form.html',
}
```

Template context always includes `data`, `view`, `request`, `response`, and `sebastian_config` (the `Sebastian` inner class, or `None`).

---

## 4. Core Features

### 4.1 Field Groups

Field groups partition a serializer's fields into named sections. They are declared in `ViewSet.Sebastian.groups` as `FieldGroup` instances. Declaration order is the rendered order.

```python
from sebastian.config import FieldGroup

FieldGroup(
    name='direzione',
    fields=['note_direttore', 'cig'],
    label='Direzione',                              # tab/section label in GUI
    edit_permission=lambda req, obj: (              # callable (request, obj) -> bool
        req.user.groups.filter(name='direttori').exists()
        and obj.stato == 'inviata'
    ),
    visible_permission=None,                        # None = always visible
)
```

**Permission callables** have signature `(request, obj) -> bool`. They are pure callables — no base class required — so each application implements its own permission logic, decoupled from Sebastian. The callable can check user roles, workflow state, or any other condition.

**Runtime behaviour**:

1. Record-level permission check passes (DRF standard).
2. For each `FieldGroup`, `edit_permission` and `visible_permission` are evaluated.
3. Result is injected into `GUISerializer.get_fields()` via `self.context['view']`.
4. Fields in non-visible groups are removed from the serializer output.
5. Fields in visible-but-not-editable groups are marked `read_only=True`.
6. On `PUT`/`PATCH`, the serializer also enforces field group permissions server-side — not just cosmetically in the GUI.

Fields not assigned to any group are accessible with no restrictions by default.

### 4.2 Entity Groups

Entity groups represent inline relations — weak-entity models owned by the parent record (e.g. `Allegato` owned by `Richiesta`). They are declared alongside field groups in `ViewSet.Sebastian.groups`.

```python
from sebastian.config import EntityGroup

EntityGroup(
    name='allegati',
    model=Allegato,
    serializer_class=AllegatoSerializer,
    label='Allegati',
    related_field='richiesta',    # FK on Allegato pointing to Richiesta; auto-detected if unambiguous
    display='tabular',            # 'tabular' | 'stacked'
    edit_permission=None,
    visible_permission=None,
)
```

**GUI behaviour**: The entity group section in the detail/form view renders as an inline table with per-row **Edit** and **Delete** buttons and a top-level **Add** button. All operations use HTMX modal forms — each modal maps 1:1 to one API endpoint call. After save or delete, only the entity group section is refreshed, not the whole page.

```
EntityGroup section in parent detail view:
┌─────────────────────────────────────────────┐
│ Allegati                           [+ Add]  │
├──────────────────────┬──────────────────────┤
│ contratto.pdf  120KB │  [Edit]  [Delete]    │
│ offerta.docx   45KB  │  [Edit]  [Delete]    │
└──────────────────────┴──────────────────────┘
```

The parent ViewSet handles all nested CRUD via `@action` methods (no separate ViewSet for inline entities). `GUIRouter` auto-generates the modal routes from `EntityGroup` declarations.

**Why modal forms and not a single-form with inlines**: DRF writable nested serializers require complex `create()`/`update()` overrides and the payload stops being standard REST. Modal forms give a 1:1 map between GUI operations and API endpoints, are auto-generatable, and eliminate the "forgot to save inline" problem.

### 4.3 List Views

Auto-generated from the ViewSet's serializer, filterset, and ordering configuration:

```python
class RichiestaViewSet(GUIMixin, viewsets.ModelViewSet):
    queryset         = Richiesta.objects.all()
    serializer_class = RichiestaSerializer
    filterset_fields = ['stato', 'fornitore']
    ordering_fields  = ['created_at', 'budget']
    search_fields    = ['titolo', 'descrizione']
```

Generates:
- Filter inputs for `stato` and `fornitore`
- Full-text search box for `titolo` and `descrizione`
- Sortable columns for `created_at` and `budget`
- Pagination controls showing current position, filtered count, and total count
- **New** button (shown if user has create permission)

### 4.4 Detail Views

Auto-generated from serializer fields and `@action` methods:

- Field groups rendered as Bootstrap tabs (in declaration order)
- Entity group sections rendered as inline tables with HTMX add/edit/delete
- Action buttons for all `@action` methods the current user has permission for
- **Edit** button (shown if user has update permission)

### 4.5 Forms (Create / Update)

Auto-generated from serializer fields grouped by field groups:

- Field types → HTML input types (`CharField` → `text`, `DecimalField` → `number`, `DateField` → `date`, etc.)
- `required` → HTML5 `required` attribute
- `help_text` → field hint
- `choices` (TextChoices / IntegerChoices) → `<select>` dropdown
- `read_only` fields → plaintext display (not form inputs)
- Related fields (`ForeignKey`) → `<select>` (Tom Select with API typeahead, deferred to Phase 4)

Serializer constraints are auto-converted to HTML5 attributes:

```python
budget = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
# → <input type="number" min="0" step="0.01">

titolo = serializers.CharField(max_length=200, required=True)
# → <input type="text" maxlength="200" required>
```

### 4.6 Actions

Declared with Sebastian's `@action` decorator (drop-in for DRF's `@action`):

```python
from sebastian.decorators import action

@action(
    detail=True,
    methods=['post'],
    permission_classes=[IsAdminUser],
    gui_config={
        'label':    'Approva',
        'icon':     'check-circle',   # Bootstrap Icons name
        'color':    'success',        # Bootstrap colour: primary|success|danger|warning|secondary
        'confirm':  'Confermi approvazione?',
        'position': 'detail',         # 'detail' | 'list' | 'both'
    },
)
def approva(self, request, pk=None):
    ...
```

`gui_config` is stored on the function as `func.gui_config`. All other DRF `@action` arguments pass through unchanged.

`GUIRouter` only mirrors `@action` routes that carry `gui_config`. Actions without `gui_config` remain API-only.

### 4.7 Permission → UI

**Record-level**: standard DRF `permission_classes` and `get_permissions()`.

**Field-level**: `FieldGroup.edit_permission` / `visible_permission` callables evaluated in `GUISerializer` (applies to API and GUI alike).

**Action-level**: `GUIMixin.get_available_actions()` evaluates each `@action`'s `permission_classes` against the current request and returns only the permitted actions. Templates use this list to render buttons.

```python
# In templates:
{% for action in view.get_available_actions %}
  <button hx-post="..." class="btn btn-{{ action.gui_config.color }}">
    {{ action.gui_config.label }}
  </button>
{% endfor %}
```

The `SEBASTIAN['HIDE_UNAUTHORIZED_ACTIONS']` setting controls whether unauthorised actions are hidden entirely or rendered disabled.

---

## 5. HTMX Integration

### Partial vs Full-Page Rendering

Sebastian detects HTMX requests via the `HX-Request` header. Full-page navigation renders `base.html` (Bootstrap 5 shell with nav, content area, modal placeholder, toast container). HTMX requests return content fragments only, without the shell. This is handled in the renderer (Phase 2).

### Entity Group Modals

The `modal.html` template renders a Bootstrap modal fragment. The parent detail view loads it into `#sebastian-modal` via `hx-get`. After a successful save or delete, the server returns `HX-Trigger: {"refreshEntity": "<group_name>"}`, which causes HTMX to refresh only the entity group section.

```html
<!-- Add button in entity group section -->
<button hx-get="/gui/richieste/123/allegati/new/"
        hx-target="#sebastian-modal"
        hx-swap="innerHTML">
  + Add
</button>

<!-- Edit button per row -->
<button hx-get="/gui/richieste/123/allegati/7/edit/"
        hx-target="#sebastian-modal"
        hx-swap="innerHTML">
  Edit
</button>
```

### Action Buttons

```html
<button hx-post="/gui/richieste/123/approva/"
        hx-target="#sebastian-content"
        hx-confirm="Confermi approvazione?">
  Approva
</button>
```

---

## 6. Cascading Actions

Actions can cascade — a workflow state change on one object may trigger a state change on another. Sebastian provides `dispatch.call()` for internal ViewSet invocation without an HTTP round-trip. Django's nested `transaction.atomic()` (savepoints) handles atomicity:

```python
from django.db import transaction
from sebastian.dispatch import call

class RichiestaViewSet(GUIMixin, viewsets.ModelViewSet):

    @action(detail=True, methods=['post'], ...)
    def approva(self, request, pk=None):
        with transaction.atomic():
            instance = self.get_object()
            instance.stato = 'approvata'
            instance.save()
            # Cascade: activate the linked Contratto in the same transaction
            call(ContrattoViewSet, 'attiva', request, pk=instance.contratto_id)
        return Response(self.get_serializer(instance).data)
```

`call(viewset_class, action_name, request, **kwargs)` instantiates the target ViewSet and calls the action method directly. Permission checks on the target ViewSet still run — enforcement is consistent whether the call comes from HTTP or internally.

---

## 7. Frontend Options

### 7.1 Server-Side (Default — HTMX)

```python
SEBASTIAN = {
    'FRONTEND_MODE': 'server',
    'TEMPLATE_PACK': 'bootstrap5',
}
```

- Auto-generated HTML templates (Bootstrap 5)
- HTMX for dynamic updates without full page reloads
- Server-side rendering, SEO-friendly, progressive enhancement

### 7.2 SPA Mode (deferred)

```python
SEBASTIAN = {
    'FRONTEND_MODE': 'spa',
    'SCHEMA_ENDPOINT': True,
}
```

- API returns JSON only
- Additional `GET /api/{resource}/?_schema` endpoint returns UI metadata (fields, types, actions, permissions)
- Frontend (React/Vue/etc.) builds UI from schema

---

## 8. Configuration Reference

```python
# settings.py
SEBASTIAN = {
    # Frontend mode
    'FRONTEND_MODE': 'server',        # 'server' | 'spa'

    # Template settings
    'TEMPLATE_PACK':  'bootstrap5',   # 'bootstrap5' | 'tailwind' | 'custom'
    'BASE_TEMPLATE':  'sebastian/base.html',

    # UI defaults
    'DEFAULT_PAGE_SIZE':     25,
    'MAX_PAGE_SIZE':         100,
    'SHOW_FIELD_HELP_TEXT':  True,

    # Action button defaults
    'DEFAULT_ACTION_COLOR':     'primary',
    'DEFAULT_CONFIRM_ACTIONS':  ['delete', 'remove'],

    # Permission display
    'HIDE_UNAUTHORIZED_ACTIONS': True,   # False = show disabled
}
```

---

## 9. Extension Points

### 9.1 Custom Renderer

```python
from sebastian.renderers import SebastianHTMLRenderer

class CustomHTMLRenderer(SebastianHTMLRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        # Custom pre-processing
        return super().render(data, accepted_media_type, renderer_context)
```

### 9.2 Custom Template Tags

```python
# myapp/templatetags/custom_sebastian.py
from django import template
register = template.Library()

@register.filter
def euro(value):
    return f'€ {value:,.2f}'
```

### 9.3 ViewSet Hooks

`GUIMixin` provides overridable hooks:

```python
class RichiestaViewSet(GUIMixin, viewsets.ModelViewSet):

    def get_sebastian_config(self):
        """Returns ViewSet.Sebastian inner class, or None."""
        return super().get_sebastian_config()

    def get_groups(self):
        """Returns groups list from Sebastian.groups, or []."""
        return super().get_groups()

    def get_available_actions(self):
        """Returns gui_config metadata for permitted @actions."""
        return super().get_available_actions()
```

### 9.4 Template Override per ViewSet

```python
class RichiestaViewSet(GUIMixin, viewsets.ModelViewSet):

    class Sebastian:
        groups          = [...]
        list_template   = 'selco/richieste_list.html'
        detail_template = 'selco/richieste_detail.html'
        form_template   = 'selco/richieste_form.html'
```

### 9.5 Works with APIView

`GUIMixin` works with `GenericAPIView` and its subclasses (including all ViewSets) automatically — DRF places `view` in the serializer context via `get_serializer_context()`.

For plain `APIView`, the developer must pass `context={'view': self, 'request': request}` when instantiating serializers — standard DRF practice.

`GUIRouter` mirrors ViewSets registered in the API router. Plain `APIView`-based views are wired manually in `urls.py` — they can still use `GUIMixin` for content negotiation, just without auto-mirroring.

---

## 10. Technology Stack

### Core Dependencies

```
Django >= 5.0
djangorestframework >= 3.14
```

### Optional Dependencies

```
django-filter >= 23.0    # For filterset_fields support
django-htmx >= 1.17      # For enhanced HX-Request utilities (optional)
```

### Frontend Assets (server mode, loaded via CDN in `base.html`)

```html
<link  href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
<link  href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
```

---

## 11. Package Layout

```
drf-sebastian/
├── pyproject.toml              distribution: drf-sebastian, import: sebastian
├── .venv/
├── src/sebastian/
│   ├── apps.py
│   ├── config.py               FieldGroup, EntityGroup
│   ├── decorators.py           @action wrapper
│   ├── dispatch.py             call()
│   ├── mixins.py               GUIMixin
│   ├── renderers.py            SebastianHTMLRenderer
│   ├── routers.py              GUIRouter
│   ├── serializers.py          GUISerializer
│   ├── templatetags/
│   │   └── sebastian_tags.py   get_item, input_type, field_value
│   └── templates/sebastian/
│       ├── base.html           Bootstrap 5 + HTMX shell
│       ├── list.html
│       ├── detail.html
│       ├── form.html
│       └── modal.html          EntityGroup HTMX modal
├── testproject/
│   ├── manage.py
│   ├── settings.py
│   ├── urls.py                 api_router + GUIRouter wired
│   └── selco/
│       ├── models.py           Fornitore, Richiesta, Allegato
│       ├── serializers.py
│       ├── views.py            ViewSets with Sebastian inner class
│       └── urls.py
└── tests/
    └── conftest.py
```

---

## 12. Testing Strategy

### Unit Tests

- `GUIRouter` URL generation matches expected patterns
- `GUIMixin` sets `request.sebastian_gui` correctly
- `GUISerializer.get_fields()` respects `FieldGroup` permissions
- `SebastianHTMLRenderer` selects correct template per action

### Integration Tests

- Full CRUD via GUI endpoints (list → detail → edit → save)
- `@action` execution via GUI route
- Filter/search functionality
- Field group visibility/editability enforcement on `PUT`

### Browser Tests (Playwright — Phase 4)

- HTMX interactions (row click, form submit, partial swap)
- Entity group modal: add, edit, delete, section refresh
- Action confirmation dialogs
- Form validation error display

---

## 13. Open Issues

1. **Related fields in forms**: FK fields currently render as `<select>` with all options. Tom Select with API typeahead (for large datasets) is deferred to Phase 4.
2. **Nested API routes for EntityGroup**: parent ViewSet handles nested CRUD via `@action`. Route generation from `EntityGroup` declarations is Phase 3.
3. **HTMX partial rendering**: renderer currently always returns full-page HTML. Partial fragment detection (`HX-Request` header → skip `base.html`) is Phase 2.
4. **Bulk actions**: how to handle `@action` on multiple selected list items — not yet designed.
5. **File uploads**: `FileField` / `ImageField` form handling (enctype, preview) — not yet designed.
6. **Menu generation**: auto-generate nav menu from router registry, store visible items in session — deferred.
7. **Breadcrumbs**: auto-generate from URL structure — deferred.
8. **SPA schema endpoint**: `GET /api/{resource}/?_schema` — deferred.
9. **`dispatch.call()` permission bypass**: currently the target ViewSet's permissions still run; if an internal call legitimately needs to bypass them, an explicit flag will be needed — not yet designed.
10. **EntityGroup `model=None` pattern**: the current workaround for circular imports (patch after class body) should be replaced with a lazy resolution mechanism.

---

## Glossary

- **API-first**: Design paradigm where the API is the primary interface; the GUI is derived from it.
- **Field group**: A named set of serializer fields sharing visibility and editability permissions. Declared in `ViewSet.Sebastian.groups`.
- **Entity group**: A named inline relation (weak entity) rendered as an HTMX-powered section with per-row modal forms.
- **GUIMixin**: ViewSet/GenericAPIView mixin that adds HTML rendering and GUI-only actions (`create_form`, `update_form`).
- **GUIRouter**: Takes a DRF router, mirrors its registry to generate parallel `/gui/` URL patterns.
- **GUISerializer**: Serializer mixin that enforces field group permissions at the serializer layer.
- **Sebastian inner class**: `class Sebastian:` declared inside a ViewSet — holds `groups`, template overrides, and other Sebastian metadata. Named `Sebastian` (not `GUIConfig`) because its configuration applies to both API and GUI layers.
- **ViewSet**: DRF class grouping related API endpoints.
- **HTMX**: Library for dynamic HTML updates without JavaScript.
- **Content negotiation**: Automatic response format selection based on `Accept` header or `format` URL kwarg.
- **Snap-in**: A component that adds functionality to existing code with minimal changes.
