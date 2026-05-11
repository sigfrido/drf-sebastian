"""
Sebasian Permissions for field editing and actions
"""

def perm_fail(request, _obj):
    """
    Always fail
    """
    return False

def perm_is_admin(request, _obj):
    """User is admin"""
    return request.user.is_superuser

def perm_is_staff(request, _obj):
    """User is staff"""
    return request.user.is_staff

def perm_is_action(action:str):
    """Current request is an action"""
    def _has_perm(request, _obj):
        view = request.parser_context.get('view')
        return getattr(view, 'action', None) == action
    return _has_perm

def perm_or(*perms):
    """Logical OR"""
    def _has_perm(request, _obj):
        if _obj:
            for perm in perms:
                if perm(request, _obj):
                    return True
        return False
    return _has_perm

def perm_and(*perms):
    """Logical AND"""
    def _has_perm(request, _obj):
        if not _obj:
            return False
        for perm in perms:
            if not perm(request, _obj):
                return False
        return True
    return _has_perm
