"""HRM 3.21 Performance Improvement — Coachingnote views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.PerformanceImprovement._helpers import _can_edit_coaching, _can_view_coaching, _visible_coaching_q
from apps.hrm.models import (
    CoachingNote,
    EmployeeProfile,
)
from apps.hrm.forms import (
    CoachingNoteForm,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceImprovement._helpers import _can_edit_coaching, _can_view_coaching, _visible_coaching_q
from apps.hrm.views.PerformanceReview._helpers import _is_admin


# ------------------------------------------------------------ CoachingNote (3.21 — coach/admin ONLY)
@login_required
def coachingnote_list(request):
    qs = (CoachingNote.objects.filter(tenant=request.tenant)
          .select_related("employee__party", "coach__party", "related_pip"))
    vq = _visible_coaching_q(request)
    if vq is not None:
        qs = qs.filter(vq)
    return crud_list(
        request, qs.order_by("-note_date", "-created_at"),
        "hrm/performance/coachingnote/list.html",
        search_fields=("number", "content", "employee__party__name"),
        filters=[("category", "category", False), ("employee", "employee_id", True)],
        extra_context={
            "category_choices": CoachingNote.CATEGORY_CHOICES,
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
        },
    )


@login_required
def coachingnote_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    coach = _current_employee_profile(request)
    if coach is None:
        messages.error(request, "Your account isn't linked to an employee profile, so you can't author a coaching note.")
        return redirect("hrm:coachingnote_list")
    if request.method == "POST":
        form = CoachingNoteForm(request.POST, tenant=request.tenant, viewer_profile=coach, viewer_is_admin=_is_admin(request.user))
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.coach = coach   # server-set — never form-typed (a user can't log a note as someone else)
            try:
                obj.clean()     # coach set server-side (after form validation) — run employee!=coach guard
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                obj.save()
                write_audit_log(request.user, obj, "create")
                messages.success(request, f"Coaching note {obj.number} logged.")
                return redirect("hrm:coachingnote_detail", pk=obj.pk)
    else:
        form = CoachingNoteForm(tenant=request.tenant, viewer_profile=coach, viewer_is_admin=_is_admin(request.user))
    return render(request, "hrm/performance/coachingnote/form.html", {"form": form, "is_edit": False})


@login_required
def coachingnote_detail(request, pk):
    obj = get_object_or_404(
        CoachingNote.objects.select_related("employee__party", "coach__party", "related_pip"),
        pk=pk, tenant=request.tenant)
    if not _can_view_coaching(request, obj):
        raise PermissionDenied("You do not have access to this coaching note.")
    return render(request, "hrm/performance/coachingnote/detail.html", {"obj": obj})


@login_required
def coachingnote_edit(request, pk):
    obj = get_object_or_404(CoachingNote, pk=pk, tenant=request.tenant)
    if not _can_edit_coaching(request, obj):
        messages.error(request, "Only the coach (author) or a tenant admin can edit this coaching note.")
        return redirect("hrm:coachingnote_detail", pk=obj.pk)
    return crud_edit(request, model=CoachingNote, pk=pk, form_class=CoachingNoteForm,
                     template="hrm/performance/coachingnote/form.html", success_url="hrm:coachingnote_list")


@login_required
@require_POST
def coachingnote_delete(request, pk):
    obj = get_object_or_404(CoachingNote, pk=pk, tenant=request.tenant)
    if not _can_edit_coaching(request, obj):
        messages.error(request, "Only the coach (author) or a tenant admin can delete this coaching note.")
        return redirect("hrm:coachingnote_detail", pk=obj.pk)
    return crud_delete(request, model=CoachingNote, pk=pk, success_url="hrm:coachingnote_list")
