"""HRM 3.41 Employee Engagement & Wellbeing — Surveyactionplan views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.EmployeeEngagement._helpers import _can_manage_action_plan
from apps.hrm.models import (
    EmployeeProfile,
    Survey,
    SurveyActionPlan,
)
from apps.hrm.forms import (
    SurveyActionPlanForm,
)
from apps.hrm.views.EmployeeEngagement._helpers import _can_manage_action_plan
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin


# ---- Survey action plans -----------------------------------------------------------------------
@login_required
def surveyactionplan_list(request):
    is_admin = _is_admin(request.user)
    profile = _current_employee_profile(request)
    qs = (SurveyActionPlan.objects.filter(tenant=request.tenant)
          .select_related("survey", "owner__party", "department", "related_objective")
          .order_by("-target_date", "-id"))
    return crud_list(request, qs, "hrm/engagement/surveyactionplan/list.html",
                     search_fields=["number", "title", "focus_area", "survey__title"],
                     filters=[("status", "status", False), ("owner", "owner_id", True),
                              ("department", "department_id", True), ("survey", "survey_id", True)],
                     extra_context={"status_choices": SurveyActionPlan.STATUS_CHOICES, "is_admin": is_admin,
                                    # so the list only shows the Edit link where the server would allow it
                                    "my_employee_pk": profile.pk if profile else None,
                                    "owners": EmployeeProfile.objects.filter(tenant=request.tenant)
                                    .select_related("party").order_by("party__name"),
                                    "departments": OrgUnit.objects.filter(tenant=request.tenant,
                                                                          kind="department").order_by("name"),
                                    "surveys": Survey.objects.filter(tenant=request.tenant)
                                    .order_by("-created_at")})


@tenant_admin_required
def surveyactionplan_create(request):
    return crud_create(request, form_class=SurveyActionPlanForm,
                       template="hrm/engagement/surveyactionplan/form.html",
                       success_url="hrm:surveyactionplan_list")


@login_required
def surveyactionplan_detail(request, pk):
    obj = get_object_or_404(
        SurveyActionPlan.objects.select_related("survey", "owner__party", "department",
                                                "related_objective"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/engagement/surveyactionplan/detail.html",
                  {"obj": obj, "can_manage": _can_manage_action_plan(request, obj),
                   "is_admin": _is_admin(request.user)})


@login_required
def surveyactionplan_edit(request, pk):
    """Editable by the owner or an admin (crud_edit has no ownership gate, so guard first)."""
    obj = get_object_or_404(SurveyActionPlan, pk=pk, tenant=request.tenant)
    if not _can_manage_action_plan(request, obj):
        raise PermissionDenied("Only the plan's owner or an HR admin can edit it.")
    return crud_edit(request, model=SurveyActionPlan, pk=pk, form_class=SurveyActionPlanForm,
                     template="hrm/engagement/surveyactionplan/form.html",
                     success_url="hrm:surveyactionplan_list")


@tenant_admin_required
@require_POST
def surveyactionplan_delete(request, pk):
    return crud_delete(request, model=SurveyActionPlan, pk=pk,
                       success_url="hrm:surveyactionplan_list")
