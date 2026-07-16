"""HRM 3.40 Workforce Planning — Workforceplan views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.WorkforcePlanning._helpers import _annotate_plan_totals
from apps.hrm.models import (
    WorkforcePlan,
)
from apps.hrm.forms import (
    WorkforcePlanForm,
    WorkforcePlanLineForm,
)
from apps.hrm.views.WorkforcePlanning._helpers import _annotate_plan_totals


# ---- Workforce plans (admin-only) --------------------------------------------------------------
@tenant_admin_required
def workforceplan_list(request):
    # Explicit order_by: annotate() adds a GROUP BY which drops Meta.ordering and would leave the
    # paginator unordered (rows duplicate/skip across pages).
    qs = (_annotate_plan_totals(
              WorkforcePlan.objects.filter(tenant=request.tenant)
              .select_related("org_unit", "owner__party", "currency").defer("notes"))
          .order_by("-created_at"))
    return crud_list(request, qs, "hrm/workforce/workforceplan/list.html",
                     search_fields=["number", "name", "org_unit__name"],
                     filters=[("status", "status", False), ("plan_type", "plan_type", False)],
                     extra_context={"status_choices": WorkforcePlan.STATUS_CHOICES,
                                    "plan_type_choices": WorkforcePlan.PLAN_TYPE_CHOICES})


@tenant_admin_required
def workforceplan_create(request):
    return crud_create(request, form_class=WorkforcePlanForm,
                       template="hrm/workforce/workforceplan/form.html",
                       success_url="hrm:workforceplan_list")


@tenant_admin_required
def workforceplan_detail(request, pk):
    obj = get_object_or_404(
        WorkforcePlan.objects.select_related("org_unit", "owner__party", "currency")
        .prefetch_related("lines__org_unit", "lines__designation", "scenarios"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/workforce/workforceplan/detail.html", {
        "obj": obj, "lines": obj.lines.all(), "scenarios": obj.scenarios.all(),
        "line_form": WorkforcePlanLineForm(tenant=request.tenant)})


@tenant_admin_required
def workforceplan_edit(request, pk):
    return crud_edit(request, model=WorkforcePlan, pk=pk, form_class=WorkforcePlanForm,
                     template="hrm/workforce/workforceplan/form.html",
                     success_url="hrm:workforceplan_list")


@tenant_admin_required
@require_POST
def workforceplan_delete(request, pk):
    return crud_delete(request, model=WorkforcePlan, pk=pk, success_url="hrm:workforceplan_list")
