"""HRM 3.37 Compensation & Benefits — Benefitplan views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    BenefitPlan,
    EmployeeBenefitEnrollment,
)
from apps.hrm.forms import (
    BenefitPlanForm,
)
from apps.hrm.views.PerformanceReview._helpers import _is_admin


# ---- Benefit plans (admin catalog) ------------------------------------------------------------
@login_required
def benefitplan_list(request):
    qs = BenefitPlan.objects.filter(tenant=request.tenant)  # currency only rendered on the detail page
    return crud_list(request, qs, "hrm/compensation/benefitplan/list.html",
                     search_fields=["name", "provider"],
                     filters=[("plan_type", "plan_type", False), ("is_active", "is_active", False)],
                     extra_context={"is_admin": _is_admin(request.user),
                                    "plan_type_choices": BenefitPlan.PLAN_TYPE_CHOICES})


@tenant_admin_required
def benefitplan_create(request):
    return crud_create(request, form_class=BenefitPlanForm,
                       template="hrm/compensation/benefitplan/form.html", success_url="hrm:benefitplan_list")


@login_required
def benefitplan_detail(request, pk):
    return crud_detail(request, model=BenefitPlan, pk=pk, template="hrm/compensation/benefitplan/detail.html",
                       select_related=("currency",),
                       extra_context={"is_admin": _is_admin(request.user),
                                      "enrollment_count": EmployeeBenefitEnrollment.objects.filter(
                                          tenant=request.tenant, plan_id=pk).count()})


@tenant_admin_required
def benefitplan_edit(request, pk):
    return crud_edit(request, model=BenefitPlan, pk=pk, form_class=BenefitPlanForm,
                     template="hrm/compensation/benefitplan/form.html", success_url="hrm:benefitplan_list")


@tenant_admin_required
@require_POST
def benefitplan_delete(request, pk):
    if EmployeeBenefitEnrollment.objects.filter(tenant=request.tenant, plan_id=pk).exists():
        messages.error(request, "This plan has employee enrollments and can't be deleted.")
        return redirect("hrm:benefitplan_detail", pk=pk)
    return crud_delete(request, model=BenefitPlan, pk=pk, success_url="hrm:benefitplan_list")
