"""CRM 1.6 Analytics & Reporting — Reports views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    AnalyticsReport,
    ReportSnapshot,
)
from apps.crm.forms import (
    AnalyticsReportForm,
)
from apps.crm.analytics import compute_report


# ----- Standard reports -----------------------------------------------------
@login_required
def report_list(request):
    qs = AnalyticsReport.objects.filter(tenant=request.tenant).select_related("owner")
    return crud_list(
        request, qs, "crm/analytics/report/list.html",
        search_fields=["name", "number", "description"],
        filters=[("report_type", "report_type", False)],
        extra_context={"report_type_choices": AnalyticsReport._meta.get_field("report_type").choices},
    )


@login_required
def report_create(request):
    return crud_create(
        request, form_class=AnalyticsReportForm,
        template="crm/analytics/report/form.html", success_url="crm:report_list")


@login_required
def report_detail(request, pk):
    report = get_object_or_404(
        AnalyticsReport.objects.select_related("owner"), pk=pk, tenant=request.tenant)
    result = compute_report(report)
    # Stamp last_run_at without bumping updated_at (system field; .update() bypasses auto_now).
    now = timezone.now()
    AnalyticsReport.objects.filter(pk=report.pk).update(last_run_at=now)
    report.last_run_at = now
    # Cap + defer the heavy summary/data JSON columns — the list panel only needs the header fields.
    snapshots = (report.snapshots.filter(tenant=request.tenant)
                 .select_related("generated_by")
                 .only("pk", "title", "generated_at", "generated_by__username",
                       "generated_by__first_name", "generated_by__last_name")[:50])
    return render(request, "crm/analytics/report/detail.html",
                  {"obj": report, "result": result, "snapshots": snapshots})


@login_required
def report_edit(request, pk):
    return crud_edit(
        request, model=AnalyticsReport, pk=pk, form_class=AnalyticsReportForm,
        template="crm/analytics/report/form.html",
        success_url=reverse("crm:report_detail", args=[pk]))


@login_required
@require_POST
def report_delete(request, pk):
    return crud_delete(request, model=AnalyticsReport, pk=pk, success_url="crm:report_list")


@login_required
@require_POST
def report_favorite(request, pk):
    report = get_object_or_404(AnalyticsReport, pk=pk, tenant=request.tenant)
    report.is_favorite = not report.is_favorite
    report.save(update_fields=["is_favorite", "updated_at"])
    write_audit_log(request.user, report, "update", {"is_favorite": report.is_favorite})
    messages.success(request, "Pinned to top." if report.is_favorite else "Unpinned.")
    return redirect("crm:report_detail", pk=report.pk)


@login_required
@require_POST
def report_snapshot(request, pk):
    report = get_object_or_404(AnalyticsReport, pk=pk, tenant=request.tenant)
    result = compute_report(report)
    with transaction.atomic():
        snap = ReportSnapshot.objects.create(
            tenant=request.tenant, report=report,
            title="{} — {:%Y-%m-%d %H:%M}".format(report.name, timezone.now()),
            generated_by=request.user if request.user.is_authenticated else None,
            summary=result.get("summary", []),
            data={k: result.get(k) for k in
                  ("columns", "rows", "chart_type", "chart_label", "chart_labels", "chart_data")},
        )
        AnalyticsReport.objects.filter(pk=report.pk).update(last_run_at=timezone.now())
        write_audit_log(request.user, snap, "create")
    messages.success(request, "Snapshot saved.")
    return redirect("crm:snapshot_detail", pk=snap.pk)
