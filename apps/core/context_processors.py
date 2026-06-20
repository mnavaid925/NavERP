"""Template context processors: sidebar nav, tenant branding, and DEBUG flag."""
from django.conf import settings

from .navigation import resolve_nav


def navigation(request):
    """Expose the resolved sidebar to authenticated pages."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"nav_sections": []}
    return {"nav_sections": resolve_nav(request)}


def branding(request):
    """Per-tenant white-label colors/logo (falls back to NavERP defaults)."""
    data = {
        "brand_name": "NavERP",
        "brand_primary": "#2563eb",
        "brand_accent": "#1d4ed8",
        "tenant_branding": None,
    }
    tenant = getattr(request, "tenant", None)
    if tenant is not None:
        try:
            # OneToOne accessor hits the unique index directly (no LIMIT 1 scan).
            setting = tenant.branding
            data["brand_primary"] = setting.primary_color
            data["brand_accent"] = setting.accent_color
            data["tenant_branding"] = setting
        except Exception:  # pragma: no cover - no branding row / table not ready
            pass
    return data


def debug_flag(request):
    """Expose settings.DEBUG explicitly (the built-in `debug` var needs INTERNAL_IPS)."""
    return {"DEBUG": settings.DEBUG}
