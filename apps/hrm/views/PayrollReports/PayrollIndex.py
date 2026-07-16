"""HRM 3.31 Payroll Reports — PayrollIndex views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    PayrollCycle,
    StatutoryReturn,
    TaxComputation,
)


@tenant_admin_required
def payroll_reports_index(request):
    tenant = request.tenant
    tiles = []
    if tenant is not None:
        today = timezone.localdate()
        cycle = PayrollCycle.objects.filter(tenant=tenant).order_by("-pay_date").first()
        gross = float(cycle.total_gross) if cycle else 0
        net = float(cycle.total_net) if cycle else 0
        hc = cycle.headcount if cycle else 0
        pending_form16 = TaxComputation.objects.filter(tenant=tenant, statutory_return__isnull=True).count()
        overdue = StatutoryReturn.objects.filter(tenant=tenant, status="pending", due_date__lt=today).count()
        tiles = [
            {"label": "Latest Cycle Headcount", "value": hc, "url": "hrm:salary_register_report", "icon": "users"},
            {"label": "Latest Cycle Gross", "value": f"{gross:,.0f}", "url": "hrm:salary_register_report", "icon": "wallet"},
            {"label": "Latest Cycle Net", "value": f"{net:,.0f}", "url": "hrm:salary_register_report", "icon": "banknote"},
            {"label": "Pending Form 16", "value": pending_form16, "url": "hrm:tax_report", "icon": "file-text"},
            {"label": "Overdue Statutory", "value": overdue, "url": "hrm:statutory_report", "icon": "alert-triangle"},
        ]
    return render(request, "hrm/reports/payroll_index.html", {"tiles": tiles})
