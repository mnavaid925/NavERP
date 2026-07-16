"""HRM 3.41 Employee Engagement & Wellbeing — Wellbeingprogram views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    WellbeingProgram,
)
from apps.hrm.forms import (
    WellbeingParticipationForm,
    WellbeingProgramForm,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin


# ---- Wellbeing programs (catalog) --------------------------------------------------------------
@login_required
def wellbeingprogram_list(request):
    is_admin = _is_admin(request.user)
    # Explicit order_by after the Count() annotation — GROUP BY drops Meta.ordering.
    qs = (WellbeingProgram.objects.filter(tenant=request.tenant)
          .select_related("owner", "target_department")
          .annotate(_participant_count=Count("participations", distinct=True))
          .order_by("-start_date", "-id"))
    return crud_list(request, qs, "hrm/engagement/wellbeingprogram/list.html",
                     search_fields=["number", "title", "description"],
                     filters=[("program_type", "program_type", False), ("status", "status", False),
                              ("target_department", "target_department_id", True)],
                     extra_context={"program_type_choices": WellbeingProgram.PROGRAM_TYPE_CHOICES,
                                    "status_choices": WellbeingProgram.STATUS_CHOICES, "is_admin": is_admin,
                                    "departments": OrgUnit.objects.filter(tenant=request.tenant,
                                                                          kind="department").order_by("name")})


@tenant_admin_required
def wellbeingprogram_create(request):
    return crud_create(request, form_class=WellbeingProgramForm,
                       template="hrm/engagement/wellbeingprogram/form.html",
                       success_url="hrm:wellbeingprogram_list")


@login_required
def wellbeingprogram_detail(request, pk):
    obj = get_object_or_404(
        WellbeingProgram.objects.select_related("owner", "target_department"),
        pk=pk, tenant=request.tenant)
    is_admin = _is_admin(request.user)
    profile = _current_employee_profile(request)
    own_participation = None
    if profile is not None:
        own_participation = obj.participations.filter(employee=profile).first()

    ctx = {"obj": obj, "is_admin": is_admin, "own_participation": own_participation,
           "stats": obj.participation_stats()}
    # CONFIDENTIALITY: a confidential program NEVER exposes a per-employee roster — aggregate stats only,
    # for every viewer including admins. Only a non-confidential program passes the roster queryset.
    if obj.is_confidential:
        ctx["participations"] = None
    else:
        ctx["participations"] = (obj.participations.select_related("employee__party")
                                 .order_by("-created_at"))
    # Offer the inline RSVP form to a logged-in employee who has no row yet, on an active program.
    if obj.status == "active" and profile is not None and own_participation is None:
        ctx["rsvp_form"] = WellbeingParticipationForm(can_admin=is_admin, tenant=request.tenant)
    return render(request, "hrm/engagement/wellbeingprogram/detail.html", ctx)


@tenant_admin_required
def wellbeingprogram_edit(request, pk):
    return crud_edit(request, model=WellbeingProgram, pk=pk, form_class=WellbeingProgramForm,
                     template="hrm/engagement/wellbeingprogram/form.html",
                     success_url="hrm:wellbeingprogram_list")


@tenant_admin_required
@require_POST
def wellbeingprogram_delete(request, pk):
    return crud_delete(request, model=WellbeingProgram, pk=pk, success_url="hrm:wellbeingprogram_list")
