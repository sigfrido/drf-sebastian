# drf-sebastian Framework Specification

See README.md for an introduction.

## 1. Problem Statement

**If we need both an API and a Web GUI for our application**, we may may choose between two approaches:

1. A traditional Django Web Application with a DRF API: we have duplication of logic between the API views and serializers, and the GUI views and forms. Some logic may live in the Models, as well.
2. A Javascript SPA with a Django DRF API: we have duplication of logic bewteen client and server side; SPA apps of course are powerful, but require more development time, a challenging pipeline and may give SEO problems too. Data-driven synchronization of the GUI (e.g. enabling/disabling controls) is time consuming and often litters the code with checks which are already made server-side.

In both cases, duplication raises the development cost and may produce inconsistencies and errors.


## The Sebastian solution

The **Sebastian** solution is pretty straightforward: **API-First** (single source of truth) with **Built-in GUI**

The idea behind Sebastian is to overload the original DRF Views, Viewsets, Filters and Serializers with GUI-specific data, so the same API endpoints can produce both JSON data and HTML GUI fragments; JSON data is enriched with GUI and context specific data in a standard way, so we may also have an SPA instructed about the available actions without littering the code with redundant checks.

This way, we can develop all the core and business logic in the API, without duplication, and be confident that it will work as expected regardless it's being called from API endponts or from the Sebastian GUI.

Based on HTMX, Sebastian provides a GUI framework with standard placeholders, like menu bar, status bar, content frame, and standard concepts like actions, lists, details, edit forms, custom pages and widgets.

Sebastian enriches the API data with GUI-related and context-related metadata:

- an entity's fields are grouped in field groups: each group can have visibility and editability rules for the current user; when no groups are defined for an entity, a default group is automatically created to keep all the fields with default permissions; group are by default grouped in the GUI's detail views with tabs or sections
- the API endpoints need to return, for each instance, the actions available for the current user, which may differ for list and detail views
- concepts like enabled or visible can be applied to actions or field groups and map directly to GUI controls' and fields' visibility and availability

Field groups are useful especially in workflows, where different users may be given access to different data in different work phases.

The GUI urls automagically mimic the API urls, like this:

- /api/resource-type/{pk}/action?param1=x,param2=y => operates and return JSON data
- /gui/resource-type/{pk}/action?param1=x,param2=y => operates and return detail page

A user may have the permission to edit and instance, but not certain field groups, which will be rendered either invisible or disabled in the generated form according to the GUI configuration.


```python

from sebastian.views import GUIMixin
from sebastian.serializer import GUISerializer

# GUISerializer mixin will serialize available actions & context, too
class RichiestaSerializer(GUISerializer, serializers.ModelSerializer):
    class Meta:
        model = Richiesta
        fields = '__all__'
        

# May easily apply to existing DRF code with minumim changes
class RichiestaViewSet(GUIMixin, viewsets.ModelViewSet):  # ← Just add mixin!
    queryset = Richiesta.objects.all()
    serializer_class = RichiestaSerializer
    filterset_fields = ['stato']
    
    @action(detail=True, methods=['post'], 
            permission_classes=[IsDirector],
            gui_config={
                'label': 'Approve',
                'icon': 'check',
                'color': 'success',
                'confirm': 'Confirm approval?'
            })
    def approve(self, request, pk=None):
        instance = self.get_object()
        instance.approve(request.user)
        return Response(self.get_serializer(instance).data)
```

**What you get automatically**:

**API** (standard DRF):
- `GET /api/richieste/` → JSON list
- `POST /api/richieste/` → JSON create
- `GET /api/richieste/123/` → JSON detail
- `POST /api/richieste/123/approve/` → JSON action

**GUI** (auto-generated):
- `GET /gui/richieste/` → HTML list with filters
- `GET /gui/richieste/new/` → HTML create form
- `GET /gui/richieste/123/` → HTML detail with action buttons
- `GET /gui/richieste/123/edit/` → HTML edit form
- `POST /gui/richieste/123/approve/` + HX-Request → HTML fragment

---

## 3. Architecture

### 3.1 Component Overview

```
SEBASTIAN Core
├── GUIMixin           - ViewSet mixin for HTML rendering
├── GUIRouter          - URL generator (API + GUI routes)
├── HTMLRenderer       - Serializer → HTML converter
├── ActionDecorator    - @action with GUI metadata
├── PermissionHelper   - Permission → UI visibility
└── Templates          - Auto-generated HTML templates
```

### 3.2 How It Works

#### Content Negotiation

```python
# sebastian/views.py
class GUIMixin:
    renderer_classes = [JSONRenderer, SebastianHTMLRenderer]
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        
        # DRF handles format negotiation automatically
        # Accept: application/json → JSONRenderer
        # Accept: text/html → SebastianHTMLRenderer
        return Response(serializer.data)
```

#### Router Extensions

```python
# sebastian/routers.py
class GUIRouter(DefaultRouter):
    """Extends DRF router with GUI routes"""
    
    def get_urls(self):
        urls = super().get_urls()  # Standard API routes
        
        # Add parallel GUI routes
        for prefix, viewset, basename in self.registry:
            urls.extend([
                path(f'{prefix}/', 
                     viewset.as_view({'get': 'list', 'post': 'create'}),
                     name=f'{basename}-list-gui'),
                path(f'{prefix}/<pk>/', 
                     viewset.as_view({'get': 'retrieve'}),
                     name=f'{basename}-detail-gui'),
                path(f'{prefix}/new/', 
                     viewset.as_view({'get': 'create_form'}),
                     name=f'{basename}-create-form'),
                path(f'{prefix}/<pk>/edit/', 
                     viewset.as_view({'get': 'update_form'}),
                     name=f'{basename}-update-form'),
            ])
        
        return urls
```

#### Action Metadata

```python
# sebastian/decorators.py
def action(detail=True, methods=None, gui_config=None, **kwargs):
    """
    Extends DRF @action with GUI metadata
    
    gui_config = {
        'label': str,      # Button label
        'icon': str,       # Icon name
        'color': str,      # Button color (primary, success, danger, etc)
        'confirm': str,    # Confirmation message
        'position': str,   # 'detail' | 'list' | 'both'
    }
    """
    def decorator(func):
        func.gui_config = gui_config or {}
        return drf_action(detail=detail, methods=methods, **kwargs)(func)
    return decorator
```

### 3.3 Template System

#### Auto-Generated Templates

Sebastian provides default templates that render any ViewSet:

**List Template** (`sebastian/list.html`):

```django
<div class="sebastian-list">
  {# Filters (auto-generated from filterset_fields) #}
  <form class="filters" hx-get="{{ request.path }}" hx-target="#list-content">
    {% for filter in view.filterset_class.filters %}
      <label>{{ filter.label }}</label>
      <input name="{{ filter.field_name }}" />
    {% endfor %}
  </form>
  
  {# List table #}
  <table id="list-content">
    <thead>
      <tr>
        {% for field in serializer.fields.values %}
          <th>{{ field.label }}</th>
        {% endfor %}
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {% for item in object_list %}
        <tr>
          {% for field_name in serializer.fields %}
            <td>{{ item|get_item:field_name }}</td>
          {% endfor %}
          <td>
            <a href="{% url view.basename|add:'-detail-gui' item.id %}">
              View
            </a>
          </td>
        </tr>
      {% endfor %}
    </tbody>
  </table>
  
  {# Pagination #}
  {% include "sebastian/pagination.html" %}
</div>
```

**Detail Template** (`sebastian/detail.html`):

```django
<div class="sebastian-detail">
  {# Field display #}
  {% for field_name, field in serializer.fields.items %}
    <div class="field">
      <label>{{ field.label }}</label>
      <div class="value">{{ object|get_item:field_name }}</div>
    </div>
  {% endfor %}
  
  {# Actions (auto-generated from ViewSet @actions) #}
  <div class="actions">
    {# Edit button (if has permission) #}
    {% if view.has_update_permission %}
      <a href="{% url view.basename|add:'-update-form' object.id %}"
         class="btn btn-secondary">
        Edit
      </a>
    {% endif %}
    
    {# Custom actions #}
    {% for action in view.get_available_actions %}
      <button hx-post="{% url view.basename|add:'-'|add:action.name object.id %}"
              hx-target="#detail-content"
              class="btn btn-{{ action.gui_config.color }}"
              {% if action.gui_config.confirm %}
                hx-confirm="{{ action.gui_config.confirm }}"
              {% endif %}>
        {% if action.gui_config.icon %}
          <i class="icon-{{ action.gui_config.icon }}"></i>
        {% endif %}
        {{ action.gui_config.label }}
      </button>
    {% endfor %}
  </div>
</div>
```

**Form Template** (`sebastian/form.html`):

```django
<form hx-post="{{ form_action }}" hx-target="#result">
  {% csrf_token %}
  
  {% for field_name, field in serializer.fields.items %}
    {% if not field.read_only %}
      <div class="field {% if field.required %}required{% endif %}">
        <label>{{ field.label }}</label>
        
        {# Auto-detect input type from field type #}
        {% if field.style.base_template == 'textarea.html' %}
          <textarea name="{{ field_name }}" 
                    {% if field.required %}required{% endif %}>
            {{ field.initial }}
          </textarea>
        {% elif field.choices %}
          <select name="{{ field_name }}"
                  {% if field.required %}required{% endif %}>
            {% for value, label in field.choices.items %}
              <option value="{{ value }}">{{ label }}</option>
            {% endfor %}
          </select>
        {% else %}
          <input type="{{ field|input_type }}" 
                 name="{{ field_name }}"
                 value="{{ field.initial }}"
                 {% if field.required %}required{% endif %} />
        {% endif %}
        
        {% if field.help_text %}
          <small class="help-text">{{ field.help_text }}</small>
        {% endif %}
      </div>
    {% endif %}
  {% endfor %}
  
  <button type="submit" class="btn btn-primary">Save</button>
</form>
```

#### Template Override

Users can override default templates per-ViewSet:

```python
class RichiestaViewSet(GUIMixin, viewsets.ModelViewSet):
    
    class GUIConfig:
        list_template = 'richieste/custom_list.html'
        detail_template = 'richieste/custom_detail.html'
        form_template = 'richieste/custom_form.html'
```

---

## 4. Core Features

### 4.1 List Views

**Auto-generated from**:

- Serializer fields → table columns
- `filterset_fields` → filter form
- Pagination → page controls
- `ordering` → sortable columns

**Example**:

```python
class RichiestaViewSet(GUIMixin, viewsets.ModelViewSet):
    queryset = Richiesta.objects.all()
    serializer_class = RichiestaSerializer
    filterset_fields = ['stato', 'rup']
    ordering_fields = ['created_at', 'budget']
    search_fields = ['titolo', 'descrizione']
```

Generates:

- Filter dropdowns for `stato` and `rup`
- Search box for `titolo` and `descrizione`
- Sort cascading dropdowns for `created_at` and `budget` (we can order for maximum n fields)
- Pagination controls (show current position, total records, filtered records): e. g.
  "rows 26-50 of 128 (filtered) / 1232 (total)"

### 4.2 Detail Views

**Auto-generated from**:

- Serializer fields → field display
- `@action` methods → action buttons
- Permissions → button visibility

**Features**:

- Read-only field display
- Related object links
- Action buttons with confirmation
- Edit button (if has permission)

### 4.3 Forms (Create/Update)

**Auto-generated from**:

- Serializer fields → form inputs
- Field types → input types (text, number, select, textarea, date, etc)
- `required` → HTML5 validation
- `help_text` → field hints
- Choices → select dropdowns
- Related fields → select with API search

**Client-side validation**:

```python
# Serializer validation is auto-converted to HTML5 attributes
class RichiestaSerializer(serializers.ModelSerializer):
    budget = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2,
        min_value=0,  # → min="0" in HTML
        max_value=100000,  # → max="100000" in HTML
    )
    titolo = serializers.CharField(
        max_length=200,  # → maxlength="200" in HTML
        required=True,  # → required in HTML
    )
```

### 4.4 Actions

**Declaration**:

```python
from sebastian.decorators import action

class RichiestaViewSet(GUIMixin, viewsets.ModelViewSet):
    
    @action(detail=True, methods=['post'],
            permission_classes=[IsDirector],
            gui_config={
                'label': 'Approve Request',
                'icon': 'check-circle',
                'color': 'success',
                'confirm': 'Are you sure you want to approve this request?',
                'position': 'detail',  # Show in detail view
            })
    def approve(self, request, pk=None):
        instance = self.get_object()
        instance.workflow_state = 'approved'
        instance.save()
        return Response(self.get_serializer(instance).data)
    
    @action(detail=False, methods=['post'],
            permission_classes=[IsAuthenticated],
            gui_config={
                'label': 'Export CSV',
                'icon': 'download',
                'color': 'secondary',
                'position': 'list',  # Show in list view
            })
    def export_csv(self, request):
        # Export logic
        pass
```

**Renders as**:

- In detail view: Button "Approve Request" (green, with confirmation)
- In list view: Button "Export CSV" (gray, downloads file)

### 4.5 Permissions → UI

**Automatic permission checking**:

```python

# Permissions work at record-level; field groups' permissions will be handled by GUI and serializers
class RichiestaViewSet(GUIMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        if self.action in ['update', 'partial_update']:
            return [IsRUP()]
        elif self.action == 'approve':
            return [IsDirector()]
        return super().get_permissions()
```

**UI automatically hides/shows**:

- Edit button (only if user has update permission)
- Action buttons (only if user passes permission check)
- Create button (only if user has create permission)

**Implementation**:

```python
# sebastian/views.py
class GUIMixin:
    
    def get_available_actions(self):
        """Returns only actions user has permission for"""
        available = []
        
        for name in dir(self):
            attr = getattr(self, name)
            if hasattr(attr, 'mapping'):  # Is a DRF @action
                # Check permissions
                permission_classes = getattr(attr, 'permission_classes', [])
                try:
                    for perm_class in permission_classes:
                        perm = perm_class()
                        perm.has_permission(self.request, self)
                    
                    # User has permission
                    available.append({
                        'name': name,
                        'url_name': f'{self.basename}-{name}',
                        'gui_config': getattr(attr, 'gui_config', {}),
                    })
                except PermissionDenied:
                    pass  # Skip this action
        
        return available
```

---

## 5. HTMX Integration

Sebastian is built with HTMX in mind for dynamic updates without full page reloads.

### Partial Rendering

```python
# sebastian/views.py
class GUIMixin:
    
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        
        # If HTMX request, return only content fragment
        if request.headers.get('HX-Request'):
            response.template_name = self._get_partial_template()
        
        return response
```

**Example**:

```html
<!-- Clicking this row updates #detail-panel without page reload -->
<tr hx-get="/richieste/123/" 
    hx-target="#detail-panel"
    hx-swap="innerHTML">
  <td>Richiesta Title</td>
</tr>

<div id="detail-panel">
  <!-- Detail view loads here -->
</div>
```

### Form Submission

```html
<!-- Form submits via HTMX, gets HTML fragment back -->
<form hx-post="/richieste/" 
      hx-target="#result"
      hx-swap="outerHTML">
  <!-- Form fields -->
</form>

<div id="result">
  <!-- Success message or validation errors appear here -->
</div>
```

### Action Buttons

```html
<!-- Action button with confirmation -->
<button hx-post="/richieste/123/approve/"
        hx-target="#detail-content"
        hx-confirm="Confirm approval?">
  Approve
</button>
```

---

## 6. Frontend Options

Sebastian supports multiple frontend strategies:

### 6.1 Server-Side (Default - HTMX)

**Configuration**:
```python
# settings.py
SEBASTIAN = {
    'FRONTEND_MODE': 'server',  # Default
    'HTMX_VERSION': '1.9.10',
}
```

**Features**:

- Auto-generated HTML templates
- HTMX for dynamic updates
- Server-side rendering
- SEO-friendly
- Progressive enhancement

**Best for**:

- Traditional web apps
- SEO-critical applications
- Teams comfortable with Django templates

### 6.2 SPA Mode (React/Vue/etc)

**Configuration**:
```python
# settings.py
SEBASTIAN = {
    'FRONTEND_MODE': 'spa',
    'SCHEMA_ENDPOINT': True,  # Enable schema endpoint
}
```

**Features**:
- API returns JSON only (no HTML)
- Additional schema endpoint for UI metadata
- Frontend builds UI from schema
- Instance data is enriched with available actions

**Schema endpoint**:
```python
GET /api/richieste/?_schema

{
  "model": "Richiesta",
  "fields": [
    {
      "name": "titolo",
      "type": "string",
      "label": "Titolo",
      "required": true,
      "max_length": 200
    },
    {
      "name": "budget",
      "type": "decimal",
      "label": "Budget",
      "min_value": 0
    }
  ],
  "actions": [
    {
      "name": "approve",
      "label": "Approve Request",
      "method": "POST",
      "url": "/api/richieste/{id}/approve/",
      "permissions": ["can_approve"],
      "gui_config": {
        "icon": "check-circle",
        "color": "success",
        "confirm": "Confirm approval?"
      }
    }
  ],
  "filters": ["stato", "rup"],
  "permissions": {
    "create": true,
    "update": false,
    "delete": false
  }
}
```

The effective availability of defined actions will be returned by the API data endpoints for each instance.

**Best for**:
- Complex interactive UIs
- Mobile apps (React Native)
- Teams with strong frontend expertise

---


## 7. Configuration Reference

```python
# settings.py
SEBASTIAN = {
    # Frontend mode
    'FRONTEND_MODE': 'server',  # 'server' | 'spa'
    
    # Template settings
    'TEMPLATE_PACK': 'bootstrap5',  # 'bootstrap5' | 'tailwind' | 'custom'
    'BASE_TEMPLATE': 'base.html',  # Your base template
    
    # HTMX settings (server mode)
    'HTMX_VERSION': '1.9.10',
    'HTMX_ENABLED': True,
    
    # Schema settings (SPA mode)
    'SCHEMA_ENDPOINT': True,
    'SCHEMA_CACHE_TIMEOUT': 3600,
    
    # UI defaults
    'DEFAULT_PAGE_SIZE': 25,
    'MAX_PAGE_SIZE': 100,
    'SHOW_FIELD_HELP_TEXT': True,
    
    # Action button defaults
    'DEFAULT_ACTION_COLOR': 'primary',
    'DEFAULT_CONFIRM_ACTIONS': ['delete', 'remove'],
    
    # Permission display - global, may be overridden locally
    'HIDE_UNAUTHORIZED_ACTIONS': True,  # vs show disabled
}
```

---

## 8. Extension Points

### 8.1 Custom Renderers

```python
from sebastian.renderers import SebastianHTMLRenderer

class CustomHTMLRenderer(SebastianHTMLRenderer):
    """Custom rendering logic"""
    
    def render_field(self, field, value):
        # Custom field rendering
        if isinstance(field, DateTimeField):
            return self.render_datetime(value)
        return super().render_field(field, value)
```

### 8.2 Custom Template Tags

```python
# myapp/templatetags/custom_sebastian.py
from django import template
from sebastian.templatetags.sebastian_tags import register

@register.filter
def custom_field_display(value, field):
    """Custom field display logic"""
    pass
```

### 8.3 ViewSet Hooks

```python
class RichiestaViewSet(GUIMixin, viewsets.ModelViewSet):
    
    def get_gui_context(self, context):
        """Add custom context for templates"""
        context['extra_data'] = self.get_extra_data()
        return context
    
    def get_list_queryset_gui(self):
        """Different queryset for GUI vs API"""
        qs = super().get_list_queryset_gui()
        return qs.select_related('extra_data_for_gui')
```

---

## 9. Technology Stack

### Core Dependencies

```
Django >= 5.0
djangorestframework >= 3.14
```

### Optional Dependencies

```
# For HTMX mode (server-side)
django-htmx >= 1.17

# For enhanced filtering
django-filter >= 23.0

# For API schema (SPA mode)
drf-spectacular >= 0.27

# For enhanced serialization
djangorestframework-camel-case >= 1.4  # If you want camelCase JSON
```

### Frontend Assets (server mode)

```html
<!-- HTMX -->
<script src="https://unpkg.com/htmx.org@1.9.10"></script>

<!-- Optional: Alpine.js for client-side interactivity -->
<script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js"></script>

<!-- Optional: Tom Select for client-side interactivity -->
<script src="tom-select.css"></script>

<!-- CSS Framework (your choice) -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
<!-- or -->
<link href="https://cdn.jsdelivr.net/npm/tailwindcss@3.x/dist/tailwind.min.css">
```

---

## 10. Success Criteria

Sebastian is successful if:

1. ✅ **Zero duplication**: Write API once, get GUI free
2. ✅ **Snap-in compatible**: Works with existing DRF projects with minimal changes
3. ✅ **Convention over configuration**: 80% use cases work with zero config
4. ✅ **Customizable**: Can override any template, any behavior
5. ✅ **Performance**: GUI rendering adds <50ms overhead vs pure DRF
6. ✅ **DRF compatible**: Doesn't break any DRF features
7. ✅ **Frontend agnostic**: Can switch from server-side to SPA without backend changes

---

## 11. Testing Strategy

### Unit Tests

- Mixin behavior
- Router URL generation
- Renderer output
- Permission checking

### Integration Tests

- Full CRUD via GUI
- Action execution
- Filter/search functionality

### Browser Tests (Playwright/Selenium)

- HTMX interactions
- Form validation
- Action confirmations

---


## Glossary

- **API-first**: Design paradigm where API is primary interface, GUI is derived
- **ViewSet**: DRF class that groups related API endpoints
- **Serializer**: DRF class that converts models to/from JSON
- **HTMX**: Library for dynamic HTML without JavaScript
- **Content negotiation**: Automatic response format selection based on Accept header
- **Snap-in**: Component that adds functionality without requiring refactoring

---

## Document Control

**Version**: 0.1.0 (Draft)  
**Last Updated**: 2025-01-27  
**Author**: Sig  
**Status**: For Review


---
