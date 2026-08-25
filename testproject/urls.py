from django.contrib import admin
from django.urls import path, include
from sebastian.routers import SebastianRouter, GUIRouter
from demo.views import SupplierViewSet, RequestViewSet, SettingsView

api_router = SebastianRouter()
api_router.register('suppliers', SupplierViewSet, basename='supplier')
api_router.register('requests', RequestViewSet, basename='request')

gui_router = GUIRouter(api_router)
gui_router.add_page('settings/', SettingsView.as_view(), name='settings')
gui_router.add_page('settings/edit/', SettingsView.as_view(edit_mode=True), name='settings-edit')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(api_router.urls)),
    path('gui/', include(gui_router.urls)),
]
