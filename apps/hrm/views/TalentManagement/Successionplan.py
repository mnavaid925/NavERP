"""HRM 3.38 Talent Management & Succession — Successionplan views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    Designation,
    SuccessionPlan,
)
from apps.hrm.forms import (
    SuccessionCandidateForm,
    SuccessionPlanForm,
)


# ---- Succession plans + their ranked candidate bench ------------------------------------------
@tenant_admin_required
def successionplan_list(request):
    # bench_strength renders on EVERY row and reads both counts — annotate them (the model properties
    # prefer the annotation), otherwise each row would fire 2 COUNT queries.
    qs = (SuccessionPlan.objects.filter(tenant=request.tenant)
          .select_related("critical_role", "department", "incumbent__party")
          .annotate(_candidate_count=Count("candidates", distinct=True),
                    _ready_now_count=Count("candidates",
                                           filter=Q(candidates__readiness="ready_now"), distinct=True))
          # Explicit order_by — annotate()'s GROUP BY drops Meta.ordering, leaving pagination unordered.
          .order_by("-created_at"))
    return crud_list(request, qs, "hrm/talent/successionplan/list.html",
                     search_fields=["number", "critical_role__name", "incumbent__party__name", "notes"],
                     filters=[("status", "status", False), ("vacancy_risk", "vacancy_risk", False),
                              ("critical_role", "critical_role_id", True)],
                     extra_context={"status_choices": SuccessionPlan.STATUS_CHOICES,
                                    "vacancy_risk_choices": SuccessionPlan.VACANCY_RISK_CHOICES,
                                    "designations": Designation.objects.filter(tenant=request.tenant)
                                    .order_by("name")})


@tenant_admin_required
def successionplan_create(request):
    return crud_create(request, form_class=SuccessionPlanForm,
                       template="hrm/talent/successionplan/form.html", success_url="hrm:successionplan_list")


@tenant_admin_required
def successionplan_detail(request, pk):
    obj = get_object_or_404(
        SuccessionPlan.objects.select_related("critical_role", "department", "incumbent__party"),
        pk=pk, tenant=request.tenant)
    candidates = obj.candidates.select_related("candidate__party").all()
    return render(request, "hrm/talent/successionplan/detail.html", {
        "obj": obj, "candidates": candidates,
        "candidate_form": SuccessionCandidateForm(tenant=request.tenant)})


@tenant_admin_required
def successionplan_edit(request, pk):
    return crud_edit(request, model=SuccessionPlan, pk=pk, form_class=SuccessionPlanForm,
                     template="hrm/talent/successionplan/form.html", success_url="hrm:successionplan_list")


@tenant_admin_required
@require_POST
def successionplan_delete(request, pk):
    return crud_delete(request, model=SuccessionPlan, pk=pk, success_url="hrm:successionplan_list")
