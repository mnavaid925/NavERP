"""HRM 3.35 Travel Management — Travelpolicy views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    JobGrade,
    TravelPolicy,
    TravelRequest,
)
from apps.hrm.forms import (
    TravelPolicyForm,
)
from apps.hrm.views.PerformanceReview._helpers import _is_admin


@login_required
def travelpolicy_list(request):
    return crud_list(request,
                     TravelPolicy.objects.filter(tenant=request.tenant).select_related("job_grade"),
                     "hrm/travel/travelpolicy/list.html", search_fields=["name"],
                     filters=[("is_active", "is_active", False), ("job_grade", "job_grade_id", True)],
                     extra_context={"is_admin": _is_admin(request.user),
                                    "job_grades": JobGrade.objects.filter(tenant=request.tenant, is_active=True)
                                    .order_by("level_order", "name")})


@tenant_admin_required
def travelpolicy_create(request):
    return crud_create(request, form_class=TravelPolicyForm,
                       template="hrm/travel/travelpolicy/form.html", success_url="hrm:travelpolicy_list")


@login_required
def travelpolicy_detail(request, pk):
    return crud_detail(request, model=TravelPolicy, pk=pk, template="hrm/travel/travelpolicy/detail.html",
                       extra_context={"is_admin": _is_admin(request.user),
                                      "request_count": TravelRequest.objects.filter(
                                          tenant=request.tenant, policy_id=pk).count()})


@tenant_admin_required
def travelpolicy_edit(request, pk):
    return crud_edit(request, model=TravelPolicy, pk=pk, form_class=TravelPolicyForm,
                     template="hrm/travel/travelpolicy/form.html", success_url="hrm:travelpolicy_list")


@tenant_admin_required
@require_POST
def travelpolicy_delete(request, pk):
    if TravelRequest.objects.filter(tenant=request.tenant, policy_id=pk).exists():
        messages.error(request, "This policy is used by existing travel requests and can't be deleted.")
        return redirect("hrm:travelpolicy_detail", pk=pk)
    return crud_delete(request, model=TravelPolicy, pk=pk, success_url="hrm:travelpolicy_list")
