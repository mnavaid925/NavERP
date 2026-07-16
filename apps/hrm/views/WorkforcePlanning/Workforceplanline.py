"""HRM 3.40 Workforce Planning — Workforceplanline views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    WorkforcePlan,
    WorkforcePlanLine,
)
from apps.hrm.forms import (
    WorkforcePlanLineForm,
)


# ---- Plan lines (inline on the plan) -----------------------------------------------------------
@tenant_admin_required
@require_POST
def workforceplanline_add(request, plan_pk):
    plan = get_object_or_404(WorkforcePlan, pk=plan_pk, tenant=request.tenant)
    form = WorkforcePlanLineForm(request.POST,
                                 instance=WorkforcePlanLine(tenant=request.tenant, plan=plan),
                                 tenant=request.tenant)
    if form.is_valid():
        form.save()
        write_audit_log(request.user, plan, "update", {"action": "line_add"})
        messages.success(request, "Line added to the plan.")
    else:
        messages.error(request, "; ".join(f"{fld}: {errs[0]}" for fld, errs in form.errors.items()))
    return redirect("hrm:workforceplan_detail", pk=plan.pk)


@tenant_admin_required
def workforceplanline_edit(request, pk):
    obj = get_object_or_404(WorkforcePlanLine.objects.select_related("plan"), pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = WorkforcePlanLineForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, obj.plan, "update", {"action": "line_edit"})
            messages.success(request, "Line updated.")
            return redirect("hrm:workforceplan_detail", pk=obj.plan_id)
    else:
        form = WorkforcePlanLineForm(instance=obj, tenant=request.tenant)
    return render(request, "hrm/workforce/workforceplanline/form.html",
                  {"form": form, "obj": obj, "plan": obj.plan, "is_edit": True})


@tenant_admin_required
@require_POST
def workforceplanline_delete(request, pk):
    obj = get_object_or_404(WorkforcePlanLine.objects.select_related("plan"), pk=pk, tenant=request.tenant)
    plan_pk = obj.plan_id
    obj.delete()
    write_audit_log(request.user, obj.plan, "update", {"action": "line_delete"})
    messages.success(request, "Line removed.")
    return redirect("hrm:workforceplan_detail", pk=plan_pk)
