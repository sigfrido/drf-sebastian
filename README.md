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

## Project status

Still in active development.

Sebastian started as a side-project for handling the GUI of my Django-DRF-based BPM Framework; I expect to introduce many changes and - hopefully - improvements as soon as new use cases or problems may surface.

A first official release should see the light by the end of july 2026.

## Project docs

- [Project roadmap](docs/roadmap.md)
- [drf-sebastian framework specifications](docs/sebastian-spec.md)

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

Uses [HTMX](https://htmx.org/) and [bootstrap 5](https://getbootstrap.com/)

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

