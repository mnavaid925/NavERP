"""HRM 3.18 Goal Setting — Objective views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.models import (
    EmployeeProfile,
    GoalCheckIn,
    GoalPeriod,
    Objective,
)
from apps.hrm.forms import (
    KeyResultForm,
    ObjectiveForm,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile


# ---------------------------------------------------------- Objective (3.18.1/3.18.2/3.18.3 the "O")
@login_required
def objective_list(request):
    qs = (Objective.objects.filter(tenant=request.tenant)
          .select_related("owner__party", "goal_period", "department", "parent_objective")
          .prefetch_related("key_results"))
    # ?mine=1 — my own objectives + my direct reports' (via the derived reporting line), 3.18.2.
    if request.GET.get("mine") == "1":
        profile = _current_employee_profile(request)
        if profile is not None:
            qs = qs.filter(Q(owner=profile) | Q(owner__employment__manager=profile.party))
        else:
            qs = qs.none()
    return crud_list(
        request, qs,
        "hrm/performance/objective/list.html",
        search_fields=("title", "number", "owner__party__name"),
        filters=[("status", "status", False), ("scope", "scope", False),
                 ("target_type", "target_type", False), ("goal_period", "goal_period_id", True),
                 ("owner", "owner_id", True), ("department", "department_id", True)],
        extra_context={
            "status_choices": Objective.STATUS_CHOICES,
            "scope_choices": Objective.SCOPE_CHOICES,
            "target_type_choices": Objective.TARGET_TYPE_CHOICES,
            "goal_periods": GoalPeriod.objects.filter(tenant=request.tenant).order_by("-start_date"),
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
            "departments": OrgUnit.objects.filter(tenant=request.tenant, kind="department").order_by("name"),
            "mine": request.GET.get("mine") == "1",
        },
    )


@login_required
def objective_tree(request):
    """Alignment/cascade tree (3.18.2) — top-level objectives with nested children, bounded depth.
    Prefetches three levels so the recursive template stays query-bounded."""
    # goal_period is in select_related because health_status falls back to the period window when an
    # objective's own start/due are null (the common case) — else it re-queries per node (N+1).
    grandchild = Prefetch("child_objectives",
                          queryset=Objective.objects.filter(tenant=request.tenant)
                          .select_related("owner__party", "goal_period").prefetch_related("key_results"))
    child = Prefetch("child_objectives",
                     queryset=Objective.objects.filter(tenant=request.tenant)
                     .select_related("owner__party", "goal_period").prefetch_related("key_results", grandchild))
    top = (Objective.objects.filter(tenant=request.tenant, parent_objective__isnull=True)
           .select_related("owner__party", "goal_period")
           .prefetch_related("key_results", child))
    period_id = request.GET.get("goal_period", "").strip()
    if period_id.isdigit():
        top = top.filter(goal_period_id=int(period_id))
    return render(request, "hrm/performance/objective/tree.html", {
        "objectives": top,
        "goal_periods": GoalPeriod.objects.filter(tenant=request.tenant).order_by("-start_date"),
        # Matches the 3 prefetched levels above (company→department→individual) — a 4th level would
        # fall outside the prefetch and re-query per node.
        "tree_max_depth": 3,
    })


@login_required
def objective_create(request):
    return crud_create(request, form_class=ObjectiveForm,
                       template="hrm/performance/objective/form.html",
                       success_url="hrm:objective_list")


@login_required
def objective_detail(request, pk):
    obj = get_object_or_404(
        Objective.objects.select_related("owner__party", "goal_period", "department", "parent_objective__owner__party")
        .prefetch_related("key_results"),
        pk=pk, tenant=request.tenant)
    key_results = list(obj.key_results.all())
    for kr in key_results:
        kr.objective = obj  # wire the parent so kr.health_status doesn't re-query goal_period
    child_objectives = (obj.child_objectives.filter(tenant=request.tenant)
                        .select_related("owner__party", "goal_period")  # goal_period: health_status fallback
                        .prefetch_related("key_results").order_by("title"))
    recent_checkins = (GoalCheckIn.objects.filter(tenant=request.tenant, key_result__objective=obj)
                       .select_related("key_result", "created_by__party")
                       .order_by("-checkin_date", "-created_at")[:20])
    return render(request, "hrm/performance/objective/detail.html", {
        "obj": obj,
        "key_results": key_results,
        "child_objectives": child_objectives,
        "recent_checkins": recent_checkins,
        "kr_form": KeyResultForm(tenant=request.tenant),
    })


@login_required
def objective_edit(request, pk):
    return crud_edit(request, model=Objective, pk=pk, form_class=ObjectiveForm,
                     template="hrm/performance/objective/form.html",
                     success_url="hrm:objective_list")


@login_required
@require_POST
def objective_delete(request, pk):
    # child_objectives are SET_NULL, key_results (+ their check-ins) CASCADE — a clean delete.
    return crud_delete(request, model=Objective, pk=pk, success_url="hrm:objective_list")
