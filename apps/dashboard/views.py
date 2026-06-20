"""Dashboard home — tenant-scoped KPI aggregation (no models of its own)."""
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render

from apps.core.models import Activity, AuditLog, Party, PartyRole
from apps.tenants.models import HealthMetric, Subscription, SubscriptionInvoice

User = get_user_model()


@login_required
def home(request):
    tenant = request.tenant
    stats = {
        "users_count": 0, "active_users": 0, "parties_count": 0,
        "open_invoices": 0, "subscription": None,
    }
    role_rows = []
    activity_rows = []
    health = []
    recent_audit = []

    if tenant is not None:
        stats["users_count"] = User.objects.filter(tenant=tenant).count()
        stats["active_users"] = User.objects.filter(tenant=tenant, status="active").count()
        stats["parties_count"] = Party.objects.filter(tenant=tenant).count()
        stats["open_invoices"] = SubscriptionInvoice.objects.filter(tenant=tenant, status="open").count()

        subscription = Subscription.objects.filter(tenant=tenant).order_by("-created_at").first()
        stats["subscription"] = subscription

        role_rows = list(
            PartyRole.objects.filter(tenant=tenant).values("role").annotate(c=Count("id")).order_by("-c")
        )
        activity_rows = list(
            Activity.objects.filter(tenant=tenant).values("status").annotate(c=Count("id")).order_by("status")
        )

        # Latest value per health metric (for progress bars / bar chart)
        seen = set()
        for hm in HealthMetric.objects.filter(tenant=tenant).order_by("-created_at"):
            if hm.metric in seen:
                continue
            seen.add(hm.metric)
            health.append(hm)

        recent_audit = list(
            AuditLog.objects.filter(tenant=tenant).select_related("user").order_by("-at")[:8]
        )

    role_display = dict(PartyRole.ROLE_CHOICES)
    status_display = dict(Activity.STATUS_CHOICES)

    context = {
        "stats": stats,
        "health": health,
        "recent_audit": recent_audit,
        "chart_roles_labels": [role_display.get(r["role"], r["role"]) for r in role_rows],
        "chart_roles_data": [r["c"] for r in role_rows],
        "chart_activity_labels": [status_display.get(r["status"], r["status"]) for r in activity_rows],
        "chart_activity_data": [r["c"] for r in activity_rows],
    }
    return render(request, "dashboard/home.html", context)
