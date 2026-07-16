"""HRM 3.18 Goal Setting — Goalperiod views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    GoalPeriod,
    Objective,
)
from apps.hrm.forms import (
    GoalPeriodForm,
)


# ---------------------------------------------------------------- GoalPeriod (3.18.4 Goal Timeline)
@login_required
def goalperiod_list(request):
    return crud_list(
        request,
        # O(1) objective count per row via annotation (no N+1 on GoalPeriod.objective_count).
        # Explicit order_by — the Count() GROUP BY otherwise drops Meta.ordering (paginator warning).
        GoalPeriod.objects.filter(tenant=request.tenant)
        .annotate(num_objectives=Count("objectives")).order_by("-start_date", "name"),
        "hrm/performance/goalperiod/list.html",
        search_fields=("name",),
        filters=[("status", "status", False), ("period_type", "period_type", False)],
        extra_context={
            "status_choices": GoalPeriod.STATUS_CHOICES,
            "period_type_choices": GoalPeriod.PERIOD_TYPE_CHOICES,
        },
    )


@login_required
def goalperiod_create(request):
    return crud_create(request, form_class=GoalPeriodForm,
                       template="hrm/performance/goalperiod/form.html",
                       success_url="hrm:goalperiod_list")


@login_required
def goalperiod_detail(request, pk):
    # Prefetch objectives + their key results so avg_progress_pct / per-objective progress_pct
    # stay a bounded number of queries (not N+1 across objectives).
    obj = get_object_or_404(
        GoalPeriod.objects.prefetch_related(
            Prefetch("objectives",
                     queryset=Objective.objects.filter(tenant=request.tenant)
                     .select_related("owner__party", "goal_period", "department")
                     .prefetch_related("key_results"))),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/performance/goalperiod/detail.html", {
        "obj": obj,
        "objectives": obj.objectives.all(),  # prefetched above
    })


@login_required
def goalperiod_edit(request, pk):
    return crud_edit(request, model=GoalPeriod, pk=pk, form_class=GoalPeriodForm,
                     template="hrm/performance/goalperiod/form.html",
                     success_url="hrm:goalperiod_list")


@login_required
@require_POST
def goalperiod_delete(request, pk):
    obj = get_object_or_404(GoalPeriod, pk=pk, tenant=request.tenant)
    # goal_period is PROTECT on Objective — pre-check for a friendly message instead of a 500.
    if obj.objectives.exists():
        messages.error(request, "This goal period has objectives and cannot be deleted.")
        return redirect("hrm:goalperiod_detail", pk=obj.pk)
    return crud_delete(request, model=GoalPeriod, pk=pk, success_url="hrm:goalperiod_list")


@tenant_admin_required
@require_POST
def goalperiod_activate(request, pk):
    obj = get_object_or_404(GoalPeriod, pk=pk, tenant=request.tenant)
    if obj.status in ("draft", "closed"):
        obj.status = "active"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "activate"})
        messages.success(request, f"Goal period '{obj.name}' activated.")
    else:
        messages.error(request, "Only a draft or closed goal period can be activated.")
    return redirect("hrm:goalperiod_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def goalperiod_close(request, pk):
    obj = get_object_or_404(GoalPeriod, pk=pk, tenant=request.tenant)
    if obj.status == "active":
        obj.status = "closed"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "close"})
        messages.success(request, f"Goal period '{obj.name}' closed.")
    else:
        messages.error(request, "Only an active goal period can be closed.")
    return redirect("hrm:goalperiod_detail", pk=obj.pk)
