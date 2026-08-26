![SEBASTIAN Logo](assets/sebastian-logo-big.png)

A server-side HTML GUI generator for Django Rest Framework API-First applications.

Sebastian is **S**mart **E**asy **B**ackend **A**pplication **S**tack for **T**ight **I**ntegration of **A**PI and **N**avigation

**Note**: This is a third-party extension for Django REST Framework, and is not an official Django REST Framework project.

> "I make... friends. They're GUIs. My friends are GUIs. I make them."

D. R. F. Sebastian

## Summary

Sebastian is a _DRY_ Django/DRF snap-in that eliminates API/GUI and backend/frontend logic duplication by auto-generating **server-side HTML interfaces** and interface abstraction data **from DRF ViewSets and Serializers**. The GUI endpoints are "replicants" of the corresponding API endpoints. Every element of the interface, even the main menu, is a HTML-rendered API endpoint. 

Sebastian provides a declarative mapping between API endpoints and GUI elements (lists, details, forms, actions) without requiring you to write separate forms, views, or templates.

With Sebastian, you implement your business logic in your DRF API's Views and Serializers, enrich it with GUI context metadata, and get an HTML GUI automatically. You can always customize the templates or add traditional Django views if you need to do so.

Sebastian has been written with **HTMX** in mind. The _htmx_ template pack allows for more dynamic pages where each element maps to an API endpoint and can be loaded autonomously - which makes master/detail forms more responsive. But there is also a _plain_ template pack which does not rely on HTMX, and handles the web page as a whole, building it via internal calls to the different enpoints which yield the page data.

Sebastian's own GUI chrome (buttons, modal titles, confirmation prompts, ...) is translatable via Django's standard i18n — set `LANGUAGE_CODE` in your project and it picks up the bundled translation automatically, no extra config. An Italian catalog ships with the package; see [drf-sebastian framework specifications §7.3](docs/sebastian-spec.md#73-translating-the-gui-chrome-i18n) for details and for how to add another language.

## Quick Start

### Try the bundled demo

The fastest way to see Sebastian in action is to run the demo project shipped in this repo (`testproject/`):

```bash
git clone https://github.com/sigfrido/drf-sebastian.git
cd drf-sebastian
python -m venv .venv && source .venv/bin/activate
pip install -e ".[filter,htmx,dev]"

cd testproject
python manage.py migrate
python manage.py seed_demo_data   # creates sample suppliers, requests, attachments, and three demo accounts
python manage.py runserver
```

Every `/gui/` page requires login (`SEBASTIAN['LOGIN_URL']`, see [spec §4.10](docs/sebastian-spec.md#410-permission--ui)); open [http://127.0.0.1:8000/gui/](http://127.0.0.1:8000/gui/) and sign in with one of the seeded accounts (password = username):

| Account | Group | Can do |
|---|---|---|
| `admin` | superuser | Everything except approve/reject a Request (see note below); manages Settings |
| `manager` | `MANAGERS` | Approve/reject submitted Requests; delete submitted Requests; create/edit Suppliers |
| `user` | `USERS` | Create/edit Requests while in draft, submit them; nothing beyond that |

This intentionally demonstrates that "admin" and "has elevated permissions" aren't the same thing in Sebastian — the demo's `Request` workflow (`testproject/demo/views.py`) restricts **approve**/**reject** to the `MANAGERS` group specifically (`admin`, a superuser but not a manager, is correctly refused), while **deleting** a non-draft Request and editing **Suppliers** accept managers *or* admin. Field-level rules follow the same phase-based pattern: the "General" tab is only editable while a Request is `draft`, "Management" only once it's `submitted`, and the whole record becomes read-only (no field, no action, no delete) once `approved`/`rejected`.

### Add Sebastian to your own project

```bash
pip install drf-sebastian[filter,htmx]
```

```python
# settings.py
INSTALLED_APPS = [
    ...,
    "rest_framework",
    "django_filters",
    "sebastian",
    "library",
]

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "sebastian.renderers.SebastianHTMLRenderer",
    ],
}

SEBASTIAN = {
    "TEMPLATE_PACK": "htmx",
}
```

```python
# library/models.py
from django.db import models

class Book(models.Model):
    title  = models.CharField(max_length=200)
    author = models.CharField(max_length=200)
```

```python
# library/serializers.py
from rest_framework import serializers
from sebastian.serializers import GUISerializerMixin
from .models import Book

class BookSerializer(GUISerializerMixin, serializers.ModelSerializer):
    class Meta:
        model  = Book
        fields = ["id", "title", "author"]
```

```python
# library/views.py
from rest_framework import viewsets
from sebastian.mixins import GUIMixin
from .models import Book
from .serializers import BookSerializer

class BookViewSet(GUIMixin, viewsets.ModelViewSet):
    queryset         = Book.objects.all()
    serializer_class = BookSerializer

    class Sebastian:
        label = "Books"
```

```python
# urls.py
from django.urls import path, include
from sebastian.routers import SebastianRouter, GUIRouter
from library.views import BookViewSet

api_router = SebastianRouter()
api_router.register("books", BookViewSet, basename="book")

gui_router = GUIRouter(api_router)

urlpatterns = [
    path("api/", include(api_router.urls)),  # JSON API
    path("gui/", include(gui_router.urls)),  # HTML GUI
]
```

```bash
python manage.py migrate
python manage.py runserver
```

Visit `/gui/` for the auto-generated list/detail/form pages, or `/api/` for the plain JSON API — same ViewSet, same Serializer, no duplicated logic.

From here, see [drf-sebastian framework specifications](docs/sebastian-spec.md) for field groups, permissions, nested resources, actions, the app menu, and the other features demonstrated in `testproject/demo/`.

## Project status

Still in active development, but stable enough for real-world use — it already powers the GUI of another project of mine in daily use.

Sebastian started as a side-project for handling the GUI of my Django-DRF-based BPM Framework; I expect to introduce many changes and - hopefully - improvements as soon as new use cases or problems may surface.

## Project docs

- [Project roadmap](docs/roadmap.md)
- [drf-sebastian framework specifications](docs/sebastian-spec.md)
- [API reference](docs/api/index.html) (generated with [pdoc](https://pdoc.dev/); regenerate with `tools/gen-docs.sh`)

## Comparison to Alternatives

| Feature | Sebastian | Django Admin | Wagtail | React Admin | FastAPI |
|---------|-----------|--------------|---------|-------------|---------|
| API-first | ✅ Yes | ❌ No | ❌ No | ✅ Yes | ✅ Yes |
| Auto GUI | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ❌ No |
| DRF Compatible | ✅ Yes | ❌ No | ❌ No | ⚠️ Partial | ❌ No |
| Customizable | ✅ High | ⚠️ Medium | ✅ High | ⚠️ Medium | N/A |
| Learning Curve | ✅ Low | ✅ Low | ⚠️ High | ⚠️ Medium | ⚠️ Medium |
| SPA Support | ✅ Yes | ❌ No | ❌ No | ✅ Yes | ✅ Yes |
| Server-side GUI| ✅ Yes | ✅ Yes | ✅ Yes | ❌ No | ⚠️ Via Jinja |


## Credits

(C) 2026 Luca Sigfrido Percich - https://github.com/sigfrido

Based on [Django](https://www.djangoproject.com/) and [Django Rest Framework](https://www.django-rest-framework.org/)

Uses [HTMX](https://htmx.org/), [bootstrap 5](https://getbootstrap.com/) and [Tom Select](https://tom-select.js.org/)

SEBASTIAN's name and tagline are freely inspired by the character J.F. Sebastian 
from Blade Runner (1982), directed by Ridley Scott.

_The project is an independent open-source software tool and is not affiliated with or endorsed by the Blade Runner franchise._

Project logo uses [Blade Runner Font](https://www.dafont.com/blade-runner-movie-font.font) by Phil Steinschneider

Source code authored with [Claude Code](https://claude.ai/)


## What do people say about SEBASTIAN

> "If we give them custom templates, we’d create a cushion, a pillow for their functionalities and consequently we can control them better."

E. Tyrell

> "Your GUIs are nothing but skin jobs<sup>*</sup>"

H. Bryant

_<sup>*</sup>Replicants of API endpoints with a skin_

