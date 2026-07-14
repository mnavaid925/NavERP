"""CRM 1.6 Analytics & Reporting — Snapshots views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    ReportSnapshot,
)


# ----- Report snapshots -----------------------------------------------------
@login_required
def snapshot_detail(request, pk):
    snap = get_object_or_404(
        ReportSnapshot.objects.select_related("report", "generated_by"), pk=pk, tenant=request.tenant)
    return render(request, "crm/analytics/snapshot/detail.html", {"obj": snap})


@login_required
@require_POST
def snapshot_delete(request, pk):
    snap = get_object_or_404(ReportSnapshot, pk=pk, tenant=request.tenant)
    report_pk = snap.report_id
    write_audit_log(request.user, snap, "delete")
    snap.delete()
    messages.success(request, "Snapshot deleted.")
    return redirect("crm:report_detail", pk=report_pk)
