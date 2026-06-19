"""Small shared helpers: audit logging + per-tenant document numbering."""
from django.contrib.contenttypes.models import ContentType


def write_audit_log(user, obj, action, changes=None, tenant=None):
    """Append an immutable AuditLog row. Safe to call from any view.

    ``user`` may be an AnonymousUser (stored as NULL). ``obj`` is the affected
    model instance; its tenant/pk/str() are captured for traceability.
    """
    from .models import AuditLog

    content_type = None
    object_id = None
    target = ""
    if obj is not None:
        content_type = ContentType.objects.get_for_model(obj.__class__)
        object_id = getattr(obj, "pk", None)
        target = str(obj)[:255]

    resolved_tenant = tenant or getattr(obj, "tenant", None) or getattr(user, "tenant", None)
    return AuditLog.objects.create(
        tenant=resolved_tenant,
        user=user if getattr(user, "is_authenticated", False) else None,
        content_type=content_type,
        object_id=object_id,
        target=target,
        action=action,
        changes=changes or {},
    )


def next_number(model, tenant, prefix, width=5, field="number"):
    """Generate the next per-tenant human-readable number, e.g. ``SINV-00001``.

    Existence-guarded max+1 (the app-wide reference pattern). Note: not atomic under
    concurrency — acceptable for the seed/admin workloads here; an app-wide hardening
    (select_for_update / sequence table) is tracked as a cross-module follow-up.
    """
    last = (
        model.objects.filter(tenant=tenant, **{f"{field}__startswith": f"{prefix}-"})
        .order_by("-id")
        .first()
    )
    seq = 1
    if last is not None:
        try:
            seq = int(str(getattr(last, field)).split("-")[-1]) + 1
        except (ValueError, AttributeError):
            seq = model.objects.filter(tenant=tenant).count() + 1
    return f"{prefix}-{seq:0{width}d}"
