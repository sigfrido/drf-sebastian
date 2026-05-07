from django.contrib import admin
from django.urls import path, include
from sebastian.routers import SebastianRouter, GUIRouter
from selco.views import FornitoreViewSet, RichiestaViewSet

api_router = SebastianRouter()
api_router.register('fornitori', FornitoreViewSet, basename='fornitore')
api_router.register('richieste', RichiestaViewSet, basename='richiesta')

gui_router = GUIRouter(api_router)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(api_router.urls)),
    path('gui/', include(gui_router.urls)),
]
