# drf-sebastian

A server-side HTML GUI generator for Django Rest Framework API-First applications.

Sebastian is **S**mart **E**asy **B**ackend **A**pplication **S**tack for **T**ight **I**ntegration of **A**PI and **N**avigation

**Note**: This is a third-party extension for Django REST Framework, and is not an official Django REST Framework project.

> *"I'm DRF Sebastian. I make friends. They're GUI elements.  
> My friends are GUI elements. I make them."*


## Summary

Sebastian is a Django/DRF snap-in that eliminates API/GUI logic duplication by auto-generating server-side HTML interfaces and interface abstraction data from existing DRF ViewSets and Serializers.

It provides a declarative mapping between API endpoints and GUI elements (lists, details, forms, actions) without requiring separate forms, views, or templates, except where customization is needed.

The main concept with Sebastian is: Implement your business logic in your DRF API, enrich it with GUI context metadata, and get both JSON endpoints and HTML interface automatically.


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

