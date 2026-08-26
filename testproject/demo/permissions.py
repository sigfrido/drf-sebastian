"""
Group-based permissions for the demo project.

Two flavours of the same checks, mirroring the split in sebastian.permissions:
- Sebastian-style ``(request, obj=None) -> bool`` callables, for
  ``FieldGroup``/``MenuItem``/``gui_config['permission']``.
- DRF ``BasePermission`` subclasses, for ``ViewSet.permission_classes`` /
  ``@action(permission_classes=[...])`` — actual API-level enforcement.

"Admin" consistently means ``is_superuser`` throughout this project, matching
``sebastian.permissions.perm_is_admin`` — not DRF's built-in ``IsAdminUser``,
which checks ``is_staff`` instead and would be a different (and here, unused)
population of users.
"""
from rest_framework.permissions import BasePermission

MANAGERS = 'MANAGERS'
USERS = 'USERS'


def _in_group(user, group_name):
    return user.is_authenticated and user.groups.filter(name=group_name).exists()


def perm_is_manager(request, _obj=None):
    return _in_group(request.user, MANAGERS)


def perm_is_manager_or_admin(request, _obj=None):
    user = request.user
    return user.is_authenticated and (user.is_superuser or _in_group(user, MANAGERS))


class IsManager(BasePermission):
    """Grants access only to authenticated users in the MANAGERS group."""

    def has_permission(self, request, view):
        return perm_is_manager(request)


class IsManagerOrAdmin(BasePermission):
    """Grants access to MANAGERS group members or superusers."""

    def has_permission(self, request, view):
        return perm_is_manager_or_admin(request)


class IsManagerOrAdminForUnsafeMethods(BasePermission):
    """Read access for anyone; write access (POST/PUT/PATCH/DELETE) requires
    MANAGERS membership or superuser status."""

    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return perm_is_manager_or_admin(request)
