"""Access-control decorators for Module-0 (lesson L27).

``@tenant_admin_required`` gates privileged workspace-config writes (billing, keys,
branding, user/role admin) so a non-admin member can't mutate them; plain
``@login_required`` is fine for reads/profile.
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def tenant_admin_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or getattr(user, "is_tenant_admin", False)):
            raise PermissionDenied("Tenant administrator access required.")
        return view_func(request, *args, **kwargs)

    return _wrapped
