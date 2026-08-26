# drf-sebastian Framework Specification

See README.md for an introduction and a Quick Start.

**Version**: 0.1.0 (tracks `pyproject.toml`)
**Last Updated**: 2026-08-25
**Author**: Sig
**Status**: Core framework complete and in real-world use (see [roadmap](roadmap.md)). SPA/schema mode remains a deferred idea, not an implemented feature.

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

Based on HTMX, Sebastian provides a GUI framework with standard placeholders (menu bar, content frame, modals) and standard concepts (actions, lists, details, edit forms, nested/inline resources, singleton resources, widgets).

Sebastian enriches the API with GUI-related and context-related metadata:

- An entity's fields are grouped in **field groups** (`FieldGroup`): each group can have visibility and editability rules for the current user. When no groups are defined, all fields are accessible with default permissions. Groups are rendered as tabs (htmx pack) or accordion sections (plain pack) in detail and form views.
- **Nested resources** represent weak-entity (inline) relations — e.g. attachments owned by a parent record — declared via `NestedGUIMixin` and `ViewSet.Sebastian.inlines`. They are real, independently-routable child ViewSets, not a separate config object; the parent's GUI simply mounts their list/form as an inline section.
- **Singleton resources** (`SingletonGUIMixin`) — for GUI pages backed by at most one instance per context (e.g. an app's settings), where list/create/destroy semantics don't apply.
- The API returns, for each instance, the actions available for the current user (may differ for list and detail views).
- `enabled`/`visible` concepts apply to actions and field groups and map directly to GUI control visibility and availability.

Field groups are especially useful in workflows, where different users may access different data in different work phases.

GUI URLs mirror API URLs:

```
GET  /api/requests/            → JSON list
GET  /api/requests/123/        → JSON detail
POST /api/requests/123/approve/→ JSON action result

GET  /gui/requests/            → HTML list with filters
GET  /gui/requests/new/        → HTML create form       ← GUI-only
GET  /gui/requests/123/        → HTML detail with action buttons
GET  /gui/requests/123/edit/   → HTML edit form          ← GUI-only
POST /gui/requests/123/approve/→ HTML fragment (HTMX)
```

**Minimal adoption example** — add two mixins to existing DRF code:

```python
from sebastian.mixins import GUIMixin
from sebastian.serializers import GUISerializerMixin

class RequestSerializer(GUISerializerMixin, serializers.ModelSerializer):
    class Meta:
        model  = Request
        fields = '__all__'

class RequestViewSet(GUIMixin, viewsets.ModelViewSet):  # ← add GUIMixin
    queryset         = Request.objects.all()
    serializer_class = RequestSerializer
    filterset_fields = ['status']
```

With a full `Sebastian` inner class, `@action` metadata, and a nested resource (see §3.4, §4.1, §4.6):

```python
from sebastian.mixins import GUIMixin, NestedGUIMixin
from sebastian.serializers import GUISerializerMixin
from sebastian.config import FieldGroup
from sebastian.decorators import action

class AttachmentViewSet(NestedGUIMixin, viewsets.ModelViewSet):
    queryset         = Attachment.objects.all()
    serializer_class = AttachmentSerializer
    mountpoint       = 'attachments'

class RequestViewSet(GUIMixin, viewsets.ModelViewSet):
    queryset         = Request.objects.select_related('supplier').all()
    serializer_class = RequestSerializer

    class Sebastian:
        groups = [
            FieldGroup('general', ['title', 'description', 'budget', 'status'],
                       label='General'),
            FieldGroup('management', ['manager_notes', 'reference_code'],
                       label='Management',
                       edit_permission=lambda req, obj: req.user.groups.filter(name='managers').exists()),
        ]
        inlines = [AttachmentViewSet]

    @action(detail=True, methods=['post'],
            permission_classes=[IsAdminUser],
            gui_config={
                'label':    'Approve',
                'icon':     'check-circle',
                'color':    'success',
                'position': 'detail',
                'confirmation': {'prompt': 'Confirm approval of $OBJECT?', 'style': 'success'},
            })
    def approve(self, request, pk=None):
        instance = self.get_object()
        instance.status = 'approved'
        instance.save()
        return Response(self.get_serializer(instance).data)
```

See it running end-to-end in `testproject/demo/` — clone the repo and follow the README's Quick Start.

---

## 3. Architecture

### 3.1 Component Overview

```
src/sebastian/
├── mixins.py         GUIMixin, NestedGUIMixin, SingletonGUIMixin
├── routers.py        SebastianRouter, GUIRouter
├── renderers.py       SebastianHTMLRenderer — resolves + renders the right template
├── serializers.py     GUISerializerMixin, gui_field, NullableFileField
├── config.py           FieldGroup, MenuItem, MenuGroup, MenuDivider
├── decorators.py       @action (gui_config), @typeahead
├── permissions.py      perm_is_admin, perm_is_staff, perm_is_action, perm_or, perm_and
├── dispatch.py          call() — internal ViewSet-to-ViewSet dispatch
├── app_settings.py      accessors for the SEBASTIAN settings dict
├── views.py              SebastianMenuView
├── static/sebastian/     widgets.js (TomSelect init), sebastian.css
└── templates/sebastian/
    ├── htmx/            HTMX-aware pack (default)
    └── plain/           No-JS pack (server renders full pages)
```

### 3.2 URL Routing

The user registers an API router normally, then passes it to `GUIRouter`:

```python
# urls.py
from sebastian.routers import SebastianRouter, GUIRouter
from demo.views import RequestViewSet

api_router = SebastianRouter()   # drop-in DefaultRouter replacement
api_router.register('requests', RequestViewSet, basename='request')

gui_router = GUIRouter(api_router)   # ← reads api_router.registry

urlpatterns = [
    path('api/', include(api_router.urls)),
    path('gui/', include(gui_router.urls)),  # ← auto-mirrored
]
```

`SebastianRouter` additionally auto-registers API URL patterns for any nested ViewSets declared in `Sebastian.inlines` (see §4.1). `GUIRouter` walks `api_router.registry` and, for each registered `GUIMixin` ViewSet, produces:

| Route | Method | ViewSet action |
|---|---|---|
| `/gui/{prefix}/` | GET/POST | `list` / `create` |
| `/gui/{prefix}/new/` | GET | `create_form` ¹ |
| `/gui/{prefix}/<pk>/` | GET/PATCH | `retrieve` / `partial_update` |
| `/gui/{prefix}/<pk>/edit/` | GET | `update_form` ¹ |
| `/gui/{prefix}/<pk>/delete/` | GET/POST | `confirm` (delete flow) |
| `/gui/{prefix}/<pk>/{url_path}/` | * | mirrored `@action` (detail) |
| `/gui/{prefix}/<pk>/{url_path}/confirm/` | GET | `confirm` (action confirmation, if `gui_config['confirmation']` is set) |
| `/gui/{prefix}/{url_path}/` | * | mirrored `@action` (list-level) |
| `/gui/menu/` | GET | `SebastianMenuView` — HTML fragment for the navbar |
| `/api/menu/` | GET | `SebastianMenuView` — same data as JSON |

Nested ViewSets (`Sebastian.inlines`) get an analogous set of routes mounted under `/gui/{parent-prefix}/<parent_pk>/{mountpoint}/...`, with parent lookup kwargs named `{parent_model_name}_pk` at every depth so arbitrarily nested resources never collide.

¹ Only added when the ViewSet has `GUIMixin`. These have no API equivalent.

`@action` routes are only mirrored when the action carries `gui_config` metadata.

Singleton resources (`SingletonGUIMixin`) are **not** auto-mirrored by `GUIRouter` — they are plain Django views, registered explicitly via `GUIRouter.add_page(url_path, view, name)` (see §4.2). Custom non-ViewSet pages use the same mechanism.

### 3.3 Content Negotiation and GUI Detection

Unlike plain DRF content negotiation, Sebastian defaults every `GUIMixin` ViewSet to **JSON-only** and opts into HTML rendering explicitly:

```python
# GUIMixin.get_renderers()  (mixins.py)
def get_renderers(self):
    if not getattr(self.request, 'sebastian_gui', False):
        return [JSONRenderer()]
    return super().get_renderers()   # includes SebastianHTMLRenderer
```

The `request.sebastian_gui` flag is set by `GUIRouter._wrap()` — a thin view wrapper applied to every `/gui/...` URL — **before** the view even dispatches, on the raw Django request. `GUIMixin.initialize_request()` copies that flag onto the DRF `Request` object once it's constructed. `SingletonGUIMixin` sets the same flag directly in its own `dispatch()`, since it isn't registered through `GUIRouter`'s normal per-ViewSet route building.

The practical effect: the exact same ViewSet/Serializer pair serves `/api/...` as JSON and `/gui/...` as HTML — there is no separate GUI-only code path, only a flag that changes which renderer is available.

`GUIRouter._wrap()` also handles the `SEBASTIAN['LOGIN_URL']` redirect for unauthenticated GUI requests, if that setting is non-empty.

### 3.4 The `Sebastian` Inner Class

Every ViewSet that uses `GUIMixin` (or `NestedGUIMixin`) may declare a `Sebastian` inner class to configure its GUI behaviour. The class is named `Sebastian` (not `GUIConfig`) because its metadata applies to both the API layer (serializer field-group permission enforcement) and the GUI layer (template rendering, action buttons, menu).

```python
class RequestViewSet(GUIMixin, viewsets.ModelViewSet):

    class Sebastian:
        label   = 'Requests'          # display name (defaults to the model's verbose_name_plural)
        groups  = [FieldGroup(...)]   # field groups, declaration order = render order
        inlines = [AttachmentViewSet] # nested resources
        menu    = MenuGroup(...)      # navbar entry (optional, see §4.3)
        ordering      = (...)         # ordering widget options (see §4.7)
        field_config  = {...}         # per-field widget config: typeahead, cascading (see §4.7)
        templates     = {'list': 'myapp/custom_list.html'}   # per-action template override
```

When no `Sebastian` class is declared, all fields are shown in a single flat group with default permissions and no menu entry.

### 3.5 Renderer

`SebastianHTMLRenderer` resolves a template from the current pack (`SEBASTIAN['TEMPLATE_PACK']`, default `'htmx'`), the view's action, and any override in `Sebastian.templates`:

```python
ACTION_TEMPLATE_SUFFIXES = {
    'list':           'list.html',
    'retrieve':       'detail.html',
    'create_form':    'form.html',
    'update_form':    'form.html',
    'confirm':        'confirm.html',
    'create':         'detail.html',
    'update':         'detail.html',
    'partial_update': 'detail.html',
}
```

HTMX requests (`HX-Request` header) receive only the `{% block content %}` fragment; full-page navigation receives the complete pack shell (`base.html`). Template context always includes `data`, `view`, `request`, `pack_name`, `skin_name`, plus action-specific keys (pagination, field labels, filter form, inline configs, menu URL).

---

## 4. Core Features

### 4.1 Field Groups & Nested Resources

Field groups partition a serializer's fields into named sections. They are declared in `ViewSet.Sebastian.groups` as `FieldGroup` instances. Declaration order is the rendered order.

```python
from sebastian.config import FieldGroup

FieldGroup(
    name='management',
    fields=['manager_notes', 'reference_code'],
    label='Management',                              # tab/section label in GUI
    edit_permission=lambda req, obj: (               # callable (request, obj) -> bool
        req.user.groups.filter(name='managers').exists()
        and obj.status == 'submitted'
    ),
    visible_permission=None,                          # None = always visible
)
```

**Permission callables** have signature `(request, obj) -> bool`. `obj` is `None` in list/label contexts, so any callable used for `visible_permission`/`edit_permission` must guard `if obj is None: return False` (or `True`, depending on intent). They are pure callables — no base class required — so each application implements its own permission logic, decoupled from Sebastian. `sebastian.permissions` ships a small set of reusable ones (`perm_is_admin`, `perm_is_staff`, `perm_is_action(name)`) plus `perm_or`/`perm_and` combinators.

**Runtime behaviour**:

1. Record-level permission check passes (DRF standard `permission_classes`).
2. For each `FieldGroup`, `edit_permission` and `visible_permission` are evaluated.
3. Fields in non-visible groups are removed from the serializer output.
4. Fields in visible-but-not-editable groups are marked `read_only=True`.
5. On `PUT`/`PATCH`, `GUISerializerMixin.validate()` also checks the raw payload against hidden/read-only fields and raises `PermissionDenied` (403) if the client tried to write one — enforcement is server-side, not just cosmetic in the GUI.

Fields not assigned to any group are accessible with no restrictions by default.

**Nested resources** (formerly a separate `EntityGroup` config object in early drafts of this spec — now a real, independent ViewSet) represent weak-entity relations owned by the parent record, e.g. `Attachment` owned by `Request`:

```python
from sebastian.mixins import NestedGUIMixin

class AttachmentViewSet(NestedGUIMixin, viewsets.ModelViewSet):
    queryset         = Attachment.objects.all()
    serializer_class = AttachmentSerializer
    mountpoint       = 'attachments'    # URL segment mounted under the parent's detail page

class RequestViewSet(GUIMixin, viewsets.ModelViewSet):
    class Sebastian:
        inlines = [AttachmentViewSet]
```

**GUI behaviour**: the inline section on the parent's detail page renders as a table with per-row **Edit**/**Delete** buttons and a top-level **New** button, loaded via `hx-trigger="load"` into `#inline-{mountpoint}`. Every operation (create/update/delete) is a real HTTP call to the nested ViewSet's own `/gui/{parent-prefix}/<pk>/{mountpoint}/...` routes; after save or delete, the server returns the updated inline list HTML directly (not a redirect), so only that section refreshes.

`NestedGUIMixin` auto-detects the parent from the `{parent_model_name}_pk` URL kwarg, filters `get_queryset()` to that parent, and injects the parent FK on create. The parent FK field name on the child model is auto-detected if unambiguous, or set explicitly via `parent_field`. Set `inline_in_api = False` on the nested ViewSet to exclude it from the parent's JSON detail response while still rendering it in the GUI.

### 4.2 Singleton Resources

For a GUI page backed by at most one record per context (e.g. an app's settings, or "impersonate user"), use `SingletonGUIMixin` instead of `GUIMixin` — there is no list, no create, no delete.

```python
from rest_framework import generics
from sebastian.mixins import SingletonGUIMixin

class SettingsView(SingletonGUIMixin, generics.GenericAPIView):
    serializer_class = SettingsSerializer

    class Sebastian:
        label  = 'Settings'
        groups = [FieldGroup('general', ['auto_approval_threshold', 'notification_email'])]

    def get_object(self):
        return Settings.get_solo()   # get_or_create(pk=1)-style singleton accessor
```

```python
# urls.py — registered explicitly, NOT auto-mirrored by GUIRouter
gui_router.add_page('settings/',      SettingsView.as_view(),                name='settings')
gui_router.add_page('settings/edit/', SettingsView.as_view(edit_mode=True),  name='settings-edit')
```

`GET /settings/` shows the read-only detail with an Edit button; `GET /settings/edit/` shows the edit form; `POST`/`PATCH`/`PUT` on either URL upserts the singleton and redirects back to the detail page. Since `add_page()` registers a plain URL rather than mirroring a router entry, link to it from a menu with `MenuItem(url_name='settings', ...)` rather than `action='...'` (see §4.3).

### 4.3 App Menu

A navbar entry is opt-in per top-level ViewSet, via `Sebastian.menu`:

```python
from sebastian.config import MenuGroup, MenuItem, MenuDivider

class Sebastian:
    menu = MenuGroup('Requests', icon='clipboard-check', items=[
        MenuItem('List', action='list', icon='list-ul'),
        MenuItem('New',  action='new',  icon='plus-circle', permission=perm_is_admin),
        MenuDivider(),
        MenuItem('Settings', url_name='settings', icon='gear'),  # points at an add_page() URL
    ])
```

`MenuItem.action` resolves against the *declaring* ViewSet's own generated routes (`'list'`, `'new'`, or any non-detail `@action` method name); `MenuItem.url_name` points at an arbitrary Django URL name instead, for custom pages or cross-ViewSet links. `MenuItem.permission` and `MenuGroup.permission` follow the same `(request, obj=None)` callable/list-of-callables protocol as field groups, and respect `SEBASTIAN['HIDE_UNAUTHORIZED_ACTIONS']` (hide vs. render disabled).

`SebastianMenuView`, auto-registered at `/api/menu/` (JSON) and `/gui/menu/` (HTML fragment), aggregates every registered ViewSet's `Sebastian.menu` into one navbar. `base.html` loads it via `hx-get="/gui/menu/" hx-trigger="load, menuRefresh from:body"`, and re-fetches it on every HTMX navigation so the active-item highlighting (longest-prefix match against `HX-Current-URL`) stays correct without a full page reload.

### 4.4 List Views

Auto-generated from the ViewSet's serializer, filterset, and ordering configuration:

```python
class RequestViewSet(GUIMixin, viewsets.ModelViewSet):
    queryset         = Request.objects.all()
    serializer_class = RequestSerializer
    filterset_class  = RequestFilter   # django-filter FilterSet
```

Generates a filter form from the `FilterSet`, a sortable-columns widget from `Sebastian.ordering` (§4.7), and pagination controls. A **New** button is shown if the user has create permission.

### 4.5 Detail Views

Auto-generated from serializer fields and `@action` methods:

- Field groups rendered as tabs (htmx pack) or `<details>` accordion sections (plain pack), in declaration order
- Nested resource sections rendered as inline tables with HTMX add/edit/delete
- Action buttons for every `@action` the current user has permission for, per `Sebastian.get_available_actions()`
- **Edit** button (shown if user has update permission)

### 4.6 Forms (Create / Update)

Auto-generated from serializer fields grouped by field groups:

- Field types → HTML input types (`CharField` → `text`, `DecimalField` → `number`, `DateField` → `date`, `BooleanField` → yes/no/unknown select, etc.)
- `required` → HTML5 `required` attribute
- `help_text` → field hint
- `choices` (TextChoices / IntegerChoices) → `<select>` dropdown
- `read_only` fields (including field-group-restricted ones) → plaintext display, not a form input
- `FileField`/`ImageField` → file input with current-filename badge and a clear/replace control
- Related fields (`ForeignKey`) → plain `<select>` by default, or a TomSelect typeahead widget if configured (§4.7)

### 4.7 Advanced Widgets

Configured per-ViewSet via `Sebastian.ordering`, `Sebastian.field_config`, and `Sebastian.cascading_fields`; rendered with [Tom Select](https://tom-select.js.org/) in the htmx pack, plain `<select>`/sequential dropdowns in the plain pack.

**Ordering** — a multi-column sort widget for list views:

```python
class Sebastian:
    ordering = (
        ('title',   'Title ↑'),
        ('-title',  'Title ↓'),
        ('budget',  'Budget ↑'),
        ('-budget', 'Budget ↓'),
    )
    max_ordering_fields = 2   # cap on simultaneous sort keys
```

`GUIMixin.filter_queryset()` reads `?ordering=f1,f2` from the querystring; undeclared fields are ignored (falls back to the model's default `Meta.ordering`).

**Typeahead** — an async-search `<select>` for `ForeignKey` fields, backed by a `@typeahead`-decorated list action:

```python
from sebastian.decorators import typeahead

class SupplierViewSet(GUIMixin, viewsets.ModelViewSet):
    @typeahead(typeahead_chars=1, max_results=40)
    def suppliers_typeahead(self, request):
        q = request.query_params.get('q', '')
        return self.standard_typeahead(filter={'company_name__icontains': q}, order_by='company_name')

class RequestViewSet(GUIMixin, viewsets.ModelViewSet):
    class Sebastian:
        field_config = {'supplier': {'typeahead_url': '/api/suppliers/suppliers_typeahead/'}}
```

`standard_typeahead()` (provided by `GUIMixin`) is a helper that filters/orders/truncates a queryset and returns `[{'value': pk, 'label': str(obj)}, ...]`.

**Cascading dropdowns** — declare related typeahead fields whose options depend on a parent selection:

```python
class Sebastian:
    cascading_fields = [('country', 'region', 'city')]  # each must also be in field_config
```

Selecting `country` clears and reloads `region` and `city`; all fields in a cascade group must already be typeahead-enabled.

### 4.8 GUI-only Computed Fields

`@gui_field` marks a serializer method as a display-only column that never appears in the JSON API response — only in GUI-mode `to_representation()` output:

```python
from sebastian.serializers import gui_field

class RequestSerializer(GUISerializerMixin, serializers.ModelSerializer):
    @gui_field('Days open')
    def days_open(self, obj):
        return (timezone.now() - obj.created_at).days
```

Reference the method name (`'days_open'`) in `Sebastian.groups`/`FieldGroup.fields` like any regular field name. Unlike a plain `SerializerMethodField`, it is guaranteed absent from `/api/...` JSON — use a real `SerializerMethodField` instead if the computed value should also be part of the API contract.

### 4.9 Actions

Declared with Sebastian's `@action` decorator (drop-in for DRF's `@action`):

```python
from sebastian.decorators import action
from sebastian.permissions import perm_and, perm_is_admin

@action(
    detail=True,
    methods=['post'],
    permission_classes=[IsAdminUser],
    gui_config={
        'label':      'Approve',
        'icon':       'check-circle',   # Bootstrap Icons name
        'color':      'success',        # Bootstrap colour: primary|success|danger|warning|secondary
        'position':   'detail',         # 'detail' | 'list' | 'both'
        'permission': perm_and(perm_is_admin, some_other_check),
        'confirmation': {
            'prompt':     'Confirm approval of $OBJECT?',   # $OBJECT / $ACTION substituted
            'serializer': None,          # optional plain Serializer class collected in a modal first
            'icon':       'check-circle',
            'style':      'success',
        },
    },
)
def approve(self, request, pk=None):
    ...
```

`gui_config` is stored on the function as `func.gui_config`. All other DRF `@action` arguments pass through unchanged. `GUIRouter` only mirrors `@action` routes that carry `gui_config`; actions without it remain API-only.

When `gui_config['confirmation']['serializer']` is set, the button opens a modal collecting that serializer's fields first; the action method receives the validated data via `self._post_confirmation_action(action_name, instance)` and a pair of `{action}_get(instance)` / `{action}_valid(instance, serializer)` hooks. Without a `serializer`, `confirmation` is just a yes/no prompt (`hx-confirm` in the htmx pack, a confirm page in the plain pack).

Other `gui_config` keys seen in real usage: `hint` (tooltip), `link_field` (paired with `self.download_action()`/`self.preview_action()` for file fields), `row_visible_field` (a boolean serializer field gating per-row visibility in list actions), `open_url` (open the action's GET response in a new tab instead of swapping it in).

### 4.10 Permission → UI

**Record-level**: standard DRF `permission_classes` and `get_permissions()`.

**Field-level**: `FieldGroup.edit_permission` / `visible_permission` callables evaluated in `GUISerializerMixin` (applies to API and GUI alike).

**Action-level**: `GUIMixin.get_available_actions()` checks DRF `permission_classes` plus the optional `gui_config['permission']` callable/list, and returns only the permitted actions with their `gui_config` attached. Templates iterate this list to render buttons/links.

The `SEBASTIAN['HIDE_UNAUTHORIZED_ACTIONS']` setting (default `True`) controls whether unauthorised actions (and menu items) are hidden entirely or rendered disabled.

**Gotcha — method-sensitive object permissions and button visibility**: `GUIMixin.can_update()`/`can_delete()` decide whether to show the Edit/Delete button by calling `has_object_permission()` from `self.get_permissions()` against the *current* request — which, while rendering a page, is always a `GET`. A `BasePermission` that allows safe methods but blocks writes (e.g. "read-only once finalized") will therefore always report "allowed" through this path, even though the equivalent `PATCH`/`DELETE` would be rejected. If a permission's write/read behaviour actually differs, override `can_update()`/`can_delete()` directly to inspect the object instead of relying on the default DRF-permission-based check — see `testproject/demo/views.py:RequestViewSet` for a worked example (record-level lock once a Request is `approved`/`rejected`).

`testproject/demo/` also demonstrates composing role-based (`is_superuser`) and Django-`Group`-based checks side by side — see `testproject/demo/permissions.py` — including a case where "admin" and a named group (`MANAGERS`) grant *different*, only partially-overlapping sets of permissions (approving a request requires the group specifically; deleting one accepts either).

---

## 5. HTMX Integration

### Partial vs Full-Page Rendering

Sebastian detects HTMX requests via the `HX-Request` header. Full-page navigation renders the active pack's `base.html` (shell with navbar, content area, modal placeholder). HTMX requests return only the `{% block content %}` fragment.

### Nested Resource Sections

The parent detail page loads each inline section via `hx-trigger="load"` into `#inline-{mountpoint}`. Add/Edit forms load into the same target; after a successful save or delete, the server returns the freshly-rendered inline list HTML directly (no `HX-Redirect`), so the section updates in place without a browser navigation.

```html
<!-- New button in an inline section -->
<button hx-get="/gui/requests/123/attachments/new/"
        hx-target="#inline-attachments"
        hx-swap="innerHTML">
  New
</button>
```

### Action Buttons & Confirmation Modals

A plain confirm action uses `hx-confirm`; an action with `gui_config['confirmation']['serializer']` instead `hx-get`s a modal (`confirm.html`, loaded into `#sebastian-modal`) that `hx-post`s back to the action URL on submit:

```html
<button hx-post="/gui/requests/123/approve/"
        hx-target="#sebastian-content"
        hx-confirm="Confirm approval of Request #123?">
  Approve
</button>
```

---

## 6. Internal Dispatch

`sebastian.dispatch.call()` invokes another ViewSet's action directly, in-process, without an HTTP round-trip — useful when one workflow transition should trigger another (e.g. approving a request activates a linked resource), inside the same database transaction:

```python
from django.db import transaction
from sebastian.dispatch import call

class RequestViewSet(GUIMixin, viewsets.ModelViewSet):

    @action(detail=True, methods=['post'], ...)
    def approve(self, request, pk=None):
        with transaction.atomic():
            instance = self.get_object()
            instance.status = 'approved'
            instance.save()
            # Cascade: activate a linked resource in the same transaction
            call(OtherViewSet, 'activate', request, pk=instance.other_id)
        return Response(self.get_serializer(instance).data)
```

`call(viewset_class, action_name, request, **kwargs)` instantiates the target ViewSet and invokes the action method directly. Permission checks defined on the target ViewSet still run — enforcement is consistent whether the call originates from HTTP or internally; there is currently no mechanism to bypass them for a trusted internal call.

At the time of writing, this is a library primitive with a clean docstring and no consuming example yet in `testproject/demo/` or in production use — treat it as intentionally minimal rather than battle-tested.

---

## 7. Frontend Options

### 7.1 Server-Side (implemented — default)

Two template packs ship today, selected via `SEBASTIAN['TEMPLATE_PACK']`:

- **`htmx`** (default) — Bootstrap 5 + HTMX; each element maps to an API endpoint and loads/updates independently.
- **`plain`** — no HTMX, no JavaScript required; the same page data is assembled server-side via `{% include_resource %}`, which calls a GUI URL internally and inlines the rendered fragment.

A **skin** (`SEBASTIAN['SKIN']`) is independent of the pack and controls the CSS/icon library — currently `bootstrap5-bi` (Bootstrap Icons) is the maintained default. Consumers can add their own pack under their project's `templates/sebastian/{pack_name}/` and opt it into HTMX-aware behaviour via `SEBASTIAN['HTMX_PACKS']`.

### 7.2 SPA / Schema Mode (deferred idea, not implemented)

A previous draft of this spec described a `FRONTEND_MODE: 'spa'` setting and a `GET /api/{resource}/?_schema` endpoint returning UI metadata for a JS frontend to consume. **Neither exists in the codebase.** There is no `FRONTEND_MODE` setting and no schema endpoint. If this is ever built, it stays out of scope for the current server-rendered architecture and would be a genuinely separate feature, not a `SEBASTIAN` setting flip.

### 7.3 Translating the GUI chrome (i18n)

The library's own chrome — button labels, modal titles, confirmation prompts, the default "Yes"/"No" boolean rendering, and similar fixed UI text baked into `src/sebastian/templates/` and a handful of default strings in `mixins.py`/`serializers.py`/`renderers.py` — is wired through Django's standard translation machinery (`{% trans %}`/`{% blocktrans %}` in templates, `gettext`/`gettext_lazy` in Python), not a `SEBASTIAN` setting. This is deliberate: there were already ~15 independent hardcoded strings (Confirm, Cancel, Edit, New, Filter, Loading, Close, ...), and a dedicated setting per string doesn't scale the way a translation catalog does.

A ready-to-use **Italian** catalog ships with the package at `src/sebastian/locale/it/LC_MESSAGES/`. Any consumer Django project with `USE_I18N = True` (the Django default) and `LANGUAGE_CODE = 'it'` (or an active-language mechanism that resolves to `it`, e.g. `LocaleMiddleware`) gets the translated chrome automatically — Django auto-discovers an installed app's own `locale/` directory, no extra `LOCALE_PATHS` entry needed. No other configuration on the consumer side is required.

This covers only the library's own default UI text. Domain content — your model/serializer field labels, `Sebastian.label`, `MenuItem`/`MenuGroup` labels, `FieldGroup` labels, action `gui_config['label']`/`hint`, confirmation prompts — is defined by the consuming application and is the consuming application's own responsibility to translate (or not) using the same Django i18n primitives in its own code.

**Every one of these strings carries the translation context `"sebastian"`** rather than being a plain, context-less translation. This is not stylistic: Django merges translation catalogs from every installed app (`django.utils.translation.trans_real._add_installed_apps_translations()`), in **reverse** `INSTALLED_APPS` order, so an app listed *earlier* in `INSTALLED_APPS` is merged *later* and wins on a plain-msgid collision. `django.contrib.admin` ships its own Italian catalog defining plain msgids for common words too — "Delete" → "Cancella", "Home" → "Pagina iniziale", among others — and since `django.contrib.admin` is conventionally listed before a project's own apps, its translations silently shadowed sebastian's for any overlapping word, independent of app order the consumer chooses. `msgctxt`/`pgettext` keys the catalog lookup on `(context, msgid)` instead of `msgid` alone, so a plain "Delete" elsewhere can never collide with `("sebastian", "Delete")` — see `tests/test_i18n.py::test_translations_not_shadowed_by_django_contrib_admin` for the regression this protects against.

**Don't write `context "sebastian"` / `pgettext('sebastian', ...)` by hand** — use the two thin wrappers that bake the context in for you:

```python
# Python (mixins.py, serializers.py, renderers.py, ...)
from .i18n import sgettext
prompt = sgettext('Delete $OBJECT?')
```

```django
{# templates — {% load sebastian_tags %} #}
{% strans "Delete" %}
{% strans "Close" as close_label %}   {# 'as' works exactly like {% trans %} #}
```

`{% strans %}` (`templatetags/sebastian_tags.py`) and `sgettext()` (`i18n.py`) are both defined in terms of the single `CONTEXT = 'sebastian'` constant in `i18n.py`, so the literal string only exists in one place.

**The one thing to remember**: `django-admin makemessages` extracts strings by pattern-matching the built-in `{% trans %}`/`{% blocktrans %}` tags and a fixed list of real Python function names (`gettext`, `pgettext`, ...) — it has no idea `{% strans %}` or `sgettext()` exist, so a string that only ever appears through one of them **silently disappears from the .po file**, no warning. `src/sebastian/_translatable_strings.py` exists purely to work around this: it's a dead-code registry that calls the real `pgettext('sebastian', ...)` for every string used via `{% strans %}`/`sgettext()` elsewhere, so makemessages' ordinary Python-file scan picks them up. **Whenever you add or change a translatable string, add or update its line in that file too** — its own docstring explains why and links back here. `{% blocktrans context "sebastian" %}` (used for the pluralized record count in `list.html`) is the one exception: it's a built-in tag, so makemessages understands it natively and needs no registry entry.

To add or update translations, edit `src/sebastian/locale/it/LC_MESSAGES/django.po` (or add a new `<lang>/LC_MESSAGES/django.po`) and run, from inside `src/sebastian/`:

```bash
DJANGO_SETTINGS_MODULE=settings PYTHONPATH=../:../../testproject \
  django-admin makemessages -l it --no-location   # regenerate msgids after touching templates/strings
django-admin compilemessages                       # .po → .mo, required for translations to take effect
```

`compilemessages` requires GNU `gettext` (`msgfmt`) on the system — a build-time tool, not a runtime dependency of the library.

---

## 8. Configuration Reference

Every key below is optional; each has a hard-coded default read by `sebastian/app_settings.py`. This reflects the real accessor functions, not aspirational settings.

```python
# settings.py
SEBASTIAN = {
    # Template / skin
    'TEMPLATE_PACK': 'htmx',            # 'htmx' | 'plain' | a custom pack name
    'SKIN':          'bootstrap5-bi',
    'HTMX_PACKS':    ['htmx'],          # which pack names get HTMX-aware behaviour

    # Permission display
    'HIDE_UNAUTHORIZED_ACTIONS': True,  # False = render disabled instead of hiding

    # Confirmation dialogs
    'CONFIRM_DELETIONS': True,          # confirm before every delete (used by GUIMixin)
    'CONFIRM_ACTIONS':   False,         # declared but not yet consulted anywhere — see below

    # Branding / auth
    'BRAND':     'Sebastian',           # navbar product name
    'LOGIN_URL': '',                    # redirect target for unauthenticated /gui/ requests

    # Display formatting
    'BOOL_DISPLAY':      'yesno',       # 'yesno' | 'checkmark' | 'icon' | 'truefalse'
    'DATE_FORMAT':       '%d/%m/%Y',
    'DATETIME_FORMAT':   '%d/%m/%Y %H:%M',
}
```

**Known gap**: `CONFIRM_ACTIONS` is read by `app_settings.confirm_actions()` but that function is not called anywhere else in the library — unlike `CONFIRM_DELETIONS`, which `GUIMixin` does consult. Setting it currently has no effect. See the roadmap for tracking.

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
def usd(value):
    return f'${value:,.2f}'
```

### 9.3 ViewSet Hooks

`GUIMixin` provides overridable hooks, all with sensible defaults derived from `Sebastian`:

```python
class RequestViewSet(GUIMixin, viewsets.ModelViewSet):

    def get_sebastian_config(self):
        """Returns the ViewSet's Sebastian inner class, or None."""
        return super().get_sebastian_config()

    def get_groups(self):
        """Returns Sebastian.groups, or []."""
        return super().get_groups()

    def get_available_actions(self):
        """Returns gui_config metadata for @actions the current user may use."""
        return super().get_available_actions()
```

### 9.4 Template Override per ViewSet

```python
class RequestViewSet(GUIMixin, viewsets.ModelViewSet):

    class Sebastian:
        groups    = [...]
        templates = {
            'list':   'demo/custom_request_list.html',
            'detail': 'demo/custom_request_detail.html',
        }
```

### 9.5 Works with plain `APIView` / `GenericAPIView`

`GUIMixin` works with `GenericAPIView` and its subclasses (including all ViewSets and, via `SingletonGUIMixin`, plain `GenericAPIView` singletons) automatically — DRF places `view` in the serializer context via `get_serializer_context()`.

For a bare `APIView` outside that hierarchy, the developer must pass `context={'view': self, 'request': request}` when instantiating serializers — standard DRF practice.

`GUIRouter` mirrors ViewSets registered in the API router, and singleton/custom pages registered via `add_page()`. Anything else is wired manually in `urls.py`.

---

## 10. Technology Stack

### Core Dependencies

```
Django >= 5.0
djangorestframework >= 3.14
```

### Optional Dependencies

```
django-filter >= 23.0    # FilterSet-based list filtering (filter extra)
django-htmx >= 1.17      # enhanced HX-Request utilities (htmx extra)
```

### Frontend Assets (loaded via CDN in `base.html`)

```html
<link  href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
<link  href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/tom-select@2/dist/js/tom-select.complete.min.js"></script>
```

### Documentation Tooling

```
pdoc >= 14.0   # API reference generated to docs/api/ — see README and tools/gen-docs.sh
```

---

## 11. Package Layout

```
drf-sebastian/
├── pyproject.toml              distribution: drf-sebastian, import: sebastian
├── README.md
├── docs/
│   ├── roadmap.md
│   ├── sebastian-spec.md       this document
│   └── api/                    pdoc-generated API reference (docs/api/index.html)
├── src/sebastian/
│   ├── apps.py
│   ├── app_settings.py         SEBASTIAN settings accessors
│   ├── config.py                FieldGroup, MenuItem, MenuGroup, MenuDivider
│   ├── decorators.py            @action wrapper, @typeahead
│   ├── dispatch.py              call()
│   ├── mixins.py                GUIMixin, NestedGUIMixin, SingletonGUIMixin
│   ├── permissions.py           perm_is_admin, perm_is_staff, perm_is_action, perm_or, perm_and
│   ├── renderers.py             SebastianHTMLRenderer
│   ├── routers.py               SebastianRouter, GUIRouter
│   ├── serializers.py           GUISerializerMixin, gui_field, NullableFileField
│   ├── views.py                  SebastianMenuView
│   ├── static/sebastian/         widgets.js, sebastian.css
│   ├── templatetags/
│   │   └── sebastian_tags.py     icon, display_value, data_keys, input_type, field_value, ...
│   ├── templates/sebastian/
│   │   ├── htmx/                 default pack (list/detail/form/confirm/menu/...)
│   │   └── plain/                no-JS pack
│   └── locale/it/LC_MESSAGES/    bundled Italian translation of the GUI chrome (see §7.3)
├── testproject/                  runnable demo — see README Quick Start
│   ├── manage.py
│   ├── settings.py
│   ├── urls.py                  api_router + GUIRouter + add_page() wired
│   └── demo/
│       ├── models.py            Supplier, Request, Attachment, Settings
│       ├── serializers.py
│       ├── views.py             ViewSets/views with Sebastian inner class
│       ├── filters.py
│       ├── admin.py
│       └── management/commands/seed_demo_data.py
└── tests/
    └── conftest.py
```

---

## 12. Testing Strategy

### Unit Tests

- `GUIRouter`/`SebastianRouter` URL generation matches expected patterns (top-level and nested)
- `GUIMixin`/`SingletonGUIMixin` set `request.sebastian_gui` correctly and restrict renderers accordingly
- `GUISerializerMixin.get_fields()` respects `FieldGroup` permissions; `@gui_field` methods stay out of the API response
- `SebastianHTMLRenderer` selects the correct template per action and pack
- Template tag filters (`data_keys`, `display_value`, `input_type`, ...) — pure Python, no DB

### Integration Tests (`tests/`, run against `testproject/demo`)

- Full CRUD via GUI endpoints (list → detail → edit → save), top-level and nested
- `@action` execution via GUI route, including confirmation modals
- Filter/search functionality, ordering widget, typeahead endpoints
- Field group visibility/editability enforcement on `PUT`/`PATCH`
- App menu: JSON and HTML rendering, active-item matching, permission-gated items
- Both template packs (`htmx`, `plain`) exercised against the same ViewSets

### Browser Tests

Not implemented — current coverage is Django `Client`-based HTTP/HTML assertions (see `tests/test_gui_views.py`), not a real browser. A Playwright suite covering live HTMX interactions, modal focus/dismiss behaviour, and TomSelect widgets remains a gap (see roadmap).

---

## 13. Open Issues

1. **`CONFIRM_ACTIONS` setting is unwired**: declared and defaulted in `app_settings.py`, but no code path currently reads it — only `CONFIRM_DELETIONS` is consulted. Either wire it up (e.g. a global default for `gui_config['confirmation']` on non-destructive actions) or remove it.
2. **`dispatch.call()` has no real-world example yet**: works and is tested at the unit level conceptually via its docstring, but no ViewSet in `testproject/demo/` or in the author's other projects exercises it yet.
3. **Bulk actions**: acting on multiple selected list rows at once — not designed.
4. **Breadcrumbs**: auto-generating them from URL/menu structure — deferred.
5. **SPA / schema mode**: a `GET /api/{resource}/?_schema` endpoint for JS-frontend consumption — deferred idea, not designed, not started (see §7.2).
6. **Browser test coverage**: no Playwright/browser-level suite yet (see §12).
7. **`management` command for exporting/customizing templates**: proposed in earlier planning, not built.
8. **`modal.html` (both packs) is dead code**: leftover from the pre-Phase-3 `EntityGroup` design, superseded by `NestedGUIMixin` inline sections; nothing in `src/sebastian/*.py` references it anymore. Not removed yet — do so once confirmed nothing external depends on it.

---

## Glossary

- **API-first**: Design paradigm where the API is the primary interface; the GUI is derived from it.
- **Field group**: A named set of serializer fields sharing visibility and editability permissions. Declared in `ViewSet.Sebastian.groups` as a `FieldGroup`.
- **Nested resource**: A weak-entity relation (e.g. attachments on a request) implemented as an independent `NestedGUIMixin` ViewSet, declared in the parent's `Sebastian.inlines`, and rendered as an inline section in the parent's GUI.
- **Singleton resource**: A GUI page backed by at most one record per context, implemented with `SingletonGUIMixin` and registered via `GUIRouter.add_page()`.
- **GUIMixin**: ViewSet/`GenericAPIView` mixin that adds HTML rendering and GUI-only actions (`create_form`, `update_form`).
- **GUIRouter**: Takes an API router, mirrors its registry to generate parallel `/gui/` URL patterns, plus the app menu and any pages registered via `add_page()`.
- **GUISerializerMixin**: Serializer mixin that enforces field group permissions and adds GUI-only representation keys (`{field}__display`, `sebastian__str`) at the serializer layer.
- **`@gui_field`**: Decorator marking a serializer method as a GUI-only computed column, excluded from the JSON API response.
- **Sebastian inner class**: `class Sebastian:` declared inside a ViewSet or singleton view — holds `groups`, `inlines`, `menu`, template overrides, and other Sebastian metadata. Named `Sebastian` (not `GUIConfig`) because its configuration applies to both API and GUI layers.
- **Template pack**: A complete set of templates (`htmx` or `plain`) selected via `SEBASTIAN['TEMPLATE_PACK']`; a **skin** is the independent CSS/icon layer on top of it.
- **ViewSet**: DRF class grouping related API endpoints.
- **HTMX**: Library for dynamic HTML updates without JavaScript.
- **Content negotiation**: Automatic response format selection; in Sebastian, gated by the `request.sebastian_gui` flag rather than plain `Accept`-header negotiation (see §3.3).
- **Snap-in**: A component that adds functionality to existing code with minimal changes.
