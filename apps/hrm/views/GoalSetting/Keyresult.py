"""HRM 3.18 Goal Setting — Keyresult views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    KeyResult,
    Objective,
)
from apps.hrm.forms import (
    GoalCheckInForm,
    KeyResultForm,
)


# ------------------------------------------------------------- KeyResult (3.18.1/3.18.3 the "KR")
@login_required
def keyresult_create(request, objective_pk):
    objective = get_object_or_404(Objective, pk=objective_pk, tenant=request.tenant)
    if request.method == "POST":
        form = KeyResultForm(request.POST,
                             instance=KeyResult(tenant=request.tenant, objective=objective),
                             tenant=request.tenant)
        if form.is_valid():
            kr = form.save()
            write_audit_log(request.user, kr, "create")
            messages.success(request, "Key result added.")
            return redirect("hrm:objective_detail", pk=objective.pk)
    else:
        # Default the weight to an equal split among existing siblings (overridable — Lattice pattern).
        sibling_count = objective.key_results.count()
        default_weight = (Decimal("100") / (sibling_count + 1)).quantize(Decimal("0.01"))
        form = KeyResultForm(instance=KeyResult(tenant=request.tenant, objective=objective),
                             initial={"weight": default_weight}, tenant=request.tenant)
    return render(request, "hrm/performance/keyresult/form.html", {
        "form": form, "is_edit": False, "objective": objective})


@login_required
def keyresult_detail(request, pk):
    kr = get_object_or_404(
        KeyResult.objects.select_related("objective__goal_period", "objective__owner__party"),
        pk=pk, tenant=request.tenant)
    checkins = kr.checkins.select_related("created_by__party").order_by("-checkin_date", "-created_at")
    return render(request, "hrm/performance/keyresult/detail.html", {
        "obj": kr,
        "objective": kr.objective,
        "checkins": checkins,
        "checkin_form": GoalCheckInForm(tenant=request.tenant),
    })


@login_required
def keyresult_edit(request, pk):
    kr = get_object_or_404(KeyResult.objects.select_related("objective"), pk=pk, tenant=request.tenant)
    objective = kr.objective
    if request.method == "POST":
        form = KeyResultForm(request.POST, instance=kr, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, kr, "update")
            messages.success(request, "Key result updated.")
            return redirect("hrm:objective_detail", pk=objective.pk)
    else:
        form = KeyResultForm(instance=kr, tenant=request.tenant)
    return render(request, "hrm/performance/keyresult/form.html", {
        "form": form, "is_edit": True, "obj": kr, "objective": objective})


@login_required
@require_POST
def keyresult_delete(request, pk):
    kr = get_object_or_404(KeyResult.objects.select_related("objective"), pk=pk, tenant=request.tenant)
    objective_pk = kr.objective_id
    write_audit_log(request.user, kr, "delete")
    kr.delete()
    messages.success(request, "Key result deleted.")
    return redirect("hrm:objective_detail", pk=objective_pk)
