# drf-sebastian

A server-side HTML GUI generator for Django Rest Framework API-First applications.

Sebastian is **S**mart **E**asy **B**ackend **A**pplication **S**tack for **T**ight **I**ntegration of **A**PI and **N**avigation

**Note**: This is a third-party extension for Django REST Framework, and is not an official Django REST Framework project.

> "I make... friends. They're GUIs. My friends are GUIs. I make them."
D. R. F. Sebastian

> "If we give them custom templates, we’d create a cushion, a pillow for their functionalities and consequently we can control them better."
E. Tyrell

> "Skin jobs - API endpoints with a skin."
H. Bryant

## Summary

Sebastian is a Django/DRF snap-in that eliminates API/GUI logic duplication by auto-generating server-side HTML interfaces and interface abstraction data from DRF ViewSets and Serializers. The GUI endpoints are "replicants" of the corresponding API endpoints.

Sebastian provides a declarative mapping between API endpoints and GUI elements (lists, details, forms, actions) without requiring separate forms, views, or templates, except where specialized customization is needed.

The main concept with Sebastian is: Implement your business logic in your DRF API, enrich it with GUI context metadata, and get an HTML GUI automatically.


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

