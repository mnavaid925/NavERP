"""Request middleware: tenant resolution + idle session timeout.

Order matters — both must run AFTER Django's AuthenticationMiddleware (see
config/settings.py MIDDLEWARE), because they read ``request.user``.
"""
import time

from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse


class TenantMiddleware:
    """Attach ``request.tenant`` from the logged-in user (None for anonymous / superuser).

    Shared-DB multi-tenancy: views filter ``Model.objects.filter(tenant=request.tenant)``.
    The superuser ``admin`` has ``tenant=None`` by design, so module data is empty for it.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        request.tenant = user.tenant if (user is not None and user.is_authenticated) else None
        return self.get_response(request)


class SessionTimeoutMiddleware:
    """Log out an authenticated session after it has been idle too long.

    Absolute lifetime is enforced separately by SESSION_COOKIE_AGE in settings; this
    handles the *idle* window (default 30 min). The Stripe webhook and static assets are
    anonymous and unaffected.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.idle = getattr(settings, "SESSION_IDLE_TIMEOUT", 1800)

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            now = int(time.time())
            last = request.session.get("_last_activity")
            if last is not None and (now - last) > self.idle:
                logout(request)
                return redirect(f"{reverse('accounts:login')}?timeout=1")
            request.session["_last_activity"] = now
        return self.get_response(request)
