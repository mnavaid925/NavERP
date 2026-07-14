"""Accounting 2.12 Reporting & Compliance — ScheduledReports views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    ScheduledReport,
)
from apps.accounting.forms import (
    ScheduledReportForm,
)


# --------------------------------------------------------------- Scheduled reports
@login_required
def scheduled_report_list(request):
    return crud_list(
        request, ScheduledReport.objects.filter(tenant=request.tenant),
        "accounting/reports/scheduled_report/list.html",
        search_fields=["name"],
        filters=[("report_type", "report_type", False), ("frequency", "frequency", False),
                 ("is_active", "is_active", False)],
        extra_context={"report_choices": ScheduledReport.REPORT_CHOICES,
                       "frequency_choices": ScheduledReport.FREQUENCY_CHOICES},
    )


@login_required
def scheduled_report_create(request):
    return crud_create(request, form_class=ScheduledReportForm, template="accounting/reports/scheduled_report/form.html",
                       success_url="accounting:scheduled_report_list")


@login_required
def scheduled_report_detail(request, pk):
    obj = get_object_or_404(ScheduledReport, pk=pk, tenant=request.tenant)
    return render(request, "accounting/reports/scheduled_report/detail.html", {"obj": obj})


@login_required
def scheduled_report_edit(request, pk):
    return crud_edit(request, model=ScheduledReport, pk=pk, form_class=ScheduledReportForm,
                     template="accounting/reports/scheduled_report/form.html", success_url="accounting:scheduled_report_list")


@login_required
@require_POST
def scheduled_report_delete(request, pk):
    return crud_delete(request, model=ScheduledReport, pk=pk, success_url="accounting:scheduled_report_list")
