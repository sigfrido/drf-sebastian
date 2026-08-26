from django.contrib import admin
from django.contrib.auth import views as auth_views
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
    # Not registered via gui_router.add_page(): that wrapper redirects
    # unauthenticated requests to LOGIN_URL, which is this same page.
    # template_name is omitted: 'registration/login.html' is both Django's
    # own default and the template sebastian ships at that same path.
    path('gui/login/', auth_views.LoginView.as_view(
        redirect_authenticated_user=True,
    ), name='login'),
    path('gui/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('api/', include(api_router.urls)),
    path('gui/', include(gui_router.urls)),
]
