"""
Sebastian Permissions for field editing and actions
"""

def perm_fail(request, _obj):
    """Always fail"""
    return False

def perm_is_admin(request, _obj):
    """User is admin"""
    return request.user.is_superuser

def perm_is_staff(request, _obj):
    """User is staff"""
    return request.user.is_staff

def perm_is_action(action: str):
    """Current request is an action"""
    def _has_perm(request, _obj):
        view = request.parser_context.get('view')
        return getattr(view, 'action', None) == action
    return _has_perm

def perm_or(*perms):
    """Logical OR — delegates to each permission; obj=None handling is up to each callable."""
    def _has_perm(request, obj):
        return any(perm(request, obj) for perm in perms)
    return _has_perm

def perm_and(*perms):
    """Logical AND — delegates to each permission; obj=None handling is up to each callable."""
    def _has_perm(request, obj):
        return all(perm(request, obj) for perm in perms)
    return _has_perm
