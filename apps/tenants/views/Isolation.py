"""tenants — Tenant Isolation & Security overview (0.1 bullet 3, COMPUTED — no model).

NavERP.md 0.1 bullet 3 is "Tenant Isolation & Security — Database/schema isolation, encryption
keys, and cross-tenant data leak prevention". Two of those three have no *page* anywhere: the
isolation model is architectural (shared schema + a tenant FK on every table, resolved by
`core.middleware.TenantMiddleware`) and cross-tenant prevention is a per-view scoping discipline
covered by each module's own security lane. The third — encryption keys — does have a register,
but it is surfaced under 0.7's "Key & Secret Management".

This page therefore holds no table and computes everything on read: it reports the actual
posture rather than restating the marketing bullet, and says plainly what it cannot prove.
"""
from django.db.models import Count

from apps.core.models import AuditLog, OrgUnit, Party

from apps.tenants.views._common import *  # noqa: F401,F403
from apps.tenants.models import (
    BrandingSetting,
    EncryptionKey,
    HealthMetric,
    Subscription,
    SubscriptionInvoice,
    UsageRecord,
)


@tenant_admin_required
def isolation_overview(request):
    tenant = request.tenant
    if tenant is None:
        messages.info(request, "Isolation applies to a tenant workspace. Sign in as a tenant admin.")
        return redirect("dashboard:home")

    # Encryption-key posture. Counted in the DB, not in Python, so the page stays flat regardless
    # of how many keys a tenant holds.
    key_counts = dict(
        EncryptionKey.objects.filter(tenant=tenant)
        .values_list("status")
        .annotate(n=Count("id"))
    )
    active_keys = key_counts.get("active", 0)
    latest_key = EncryptionKey.objects.filter(tenant=tenant).order_by("-created_at").first()

    # The honest measure of "isolation" in a shared-schema design is that every table holding this
    # tenant's data carries a tenant FK and is filtered by it. So list the tables and count the
    # rows scoped to THIS tenant — and assert the FK rather than assuming it, because a model that
    # lost its tenant column would be a cross-tenant leak and should show up here.
    scoped_models = [
        ("core.Party", Party),
        ("core.AuditLog", AuditLog),
        ("core.OrgUnit", OrgUnit),
        ("tenants.Subscription", Subscription),
        ("tenants.SubscriptionInvoice", SubscriptionInvoice),
        ("tenants.UsageRecord", UsageRecord),
        ("tenants.HealthMetric", HealthMetric),
        ("tenants.BrandingSetting", BrandingSetting),
        ("tenants.EncryptionKey", EncryptionKey),
    ]
    scoped_rows = []
    for label, model in scoped_models:
        has_tenant_fk = any(f.name == "tenant" for f in model._meta.get_fields())
        scoped_rows.append({
            "label": label,
            "count": model.objects.filter(tenant=tenant).count() if has_tenant_fk else 0,
            "has_tenant_fk": has_tenant_fk,
        })

    context = {
        "tenant": tenant,
        "subscription": Subscription.objects.filter(tenant=tenant).order_by("-created_at").first(),
        "key_counts": key_counts,
        "active_keys": active_keys,
        "latest_key": latest_key,
        "scoped_rows": scoped_rows,
        "unscoped_models": [r["label"] for r in scoped_rows if not r["has_tenant_fk"]],
        "usage_count": UsageRecord.objects.filter(tenant=tenant).count(),
        "billed_usage_count": UsageRecord.objects.filter(tenant=tenant, is_billed=True).count(),
    }
    return render(request, "tenants/isolation.html", context)
