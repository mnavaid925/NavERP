"""HRM 3.40 Workforce Planning — Workforcescenario views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.WorkforcePlanning._helpers import _normalize_baseline
from apps.hrm.models import (
    WorkforcePlan,
    WorkforceScenario,
)
from apps.hrm.forms import (
    WorkforceScenarioForm,
)
from apps.hrm.views.WorkforcePlanning._helpers import _normalize_baseline
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._common import _changed


# ---- Scenarios (admin-only) --------------------------------------------------------------------
@tenant_admin_required
def workforcescenario_list(request):
    qs = (WorkforceScenario.objects.filter(tenant=request.tenant)
          .select_related("plan", "affected_org_unit").defer("description", "notes"))
    return crud_list(request, qs, "hrm/workforce/workforcescenario/list.html",
                     search_fields=["number", "name", "plan__name"],
                     filters=[("status", "status", False), ("scenario_type", "scenario_type", False),
                              ("plan", "plan_id", True)],
                     extra_context={"status_choices": WorkforceScenario.STATUS_CHOICES,
                                    "scenario_type_choices": WorkforceScenario.SCENARIO_TYPE_CHOICES,
                                    "plans": WorkforcePlan.objects.filter(tenant=request.tenant)
                                    .order_by("-created_at")})


@tenant_admin_required
def workforcescenario_create(request):
    # Bespoke (not crud_create) so a new baseline demotes the plan's other baselines atomically, and
    # so ?plan=<id> from a plan's "New Scenario" link pre-selects the plan.
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = WorkforceScenarioForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                obj.tenant = request.tenant
                obj.save()
                _normalize_baseline(obj)
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Scenario created.")
            return redirect("hrm:workforcescenario_list")
    else:
        initial = {}
        plan_id = request.GET.get("plan", "").strip()
        if plan_id.isdigit() and WorkforcePlan.objects.filter(
                tenant=request.tenant, pk=int(plan_id)).exists():
            initial["plan"] = int(plan_id)
        form = WorkforceScenarioForm(tenant=request.tenant, initial=initial)
    return render(request, "hrm/workforce/workforcescenario/form.html",
                  {"form": form, "is_edit": False})


@tenant_admin_required
def workforcescenario_detail(request, pk):
    obj = get_object_or_404(
        WorkforceScenario.objects.select_related("plan__currency", "affected_org_unit"),
        pk=pk, tenant=request.tenant)
    # The plan's planned headcount is an un-cached aggregate — resolve it ONCE here. Reading
    # obj.resulting_headcount and obj.plan.total_planned_headcount straight from the template would
    # re-run the same SUM twice.
    planned = obj.plan.total_planned_headcount
    return render(request, "hrm/workforce/workforcescenario/detail.html", {
        "obj": obj, "plan_planned_headcount": planned,
        "resulting_headcount": planned + obj.headcount_delta})


@tenant_admin_required
def workforcescenario_edit(request, pk):
    obj = get_object_or_404(WorkforceScenario, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = WorkforceScenarioForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save()
                _normalize_baseline(obj)
            write_audit_log(request.user, obj, "update", changes=_changed(form))
            messages.success(request, "Scenario updated.")
            return redirect("hrm:workforcescenario_list")
    else:
        form = WorkforceScenarioForm(instance=obj, tenant=request.tenant)
    return render(request, "hrm/workforce/workforcescenario/form.html",
                  {"form": form, "is_edit": True, "obj": obj})


@tenant_admin_required
@require_POST
def workforcescenario_delete(request, pk):
    return crud_delete(request, model=WorkforceScenario, pk=pk, success_url="hrm:workforcescenario_list")
