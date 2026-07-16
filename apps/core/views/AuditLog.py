"""core — AuditLog views (split from apps/core/views.py)."""
from apps.core.views._common import *  # noqa: F401,F403
from apps.core.models import (
    AuditLog,
)


# -------------------------------------------------------------- AuditLog (read-only)
@tenant_admin_required
def auditlog_list(request):
    return crud_list(
        request, AuditLog.objects.filter(tenant=request.tenant).select_related("user"),
        "core/auditlog/list.html",
        search_fields=["target"],
        filters=[("action", "action", False)],
        extra_context={"action_choices": AuditLog.ACTION_CHOICES,
                       "users": User.objects.filter(tenant=request.tenant)
                       .only("id", "email", "first_name", "last_name")},
    )


@tenant_admin_required
def auditlog_detail(request, pk):
    obj = get_object_or_404(AuditLog.objects.select_related("user"), pk=pk, tenant=request.tenant)
    return render(request, "core/auditlog/detail.html", {"obj": obj})
