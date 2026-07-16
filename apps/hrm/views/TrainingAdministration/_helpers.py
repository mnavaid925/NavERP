"""HRM 3.24 Training Administration — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.forms import (
    TrainingCertificateForm,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin


# ------------------------------------------------------------ TrainingNomination (3.24 Nomination)
def _can_decide_nomination(request, obj):
    """A tenant admin OR the nominee's own manager may approve/reject (per the reporting line)."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return bool(profile is not None and obj.employee.employment_id
                and obj.employee.employment.manager_id == profile.party_id)


# ------------------------------------------------------------ TrainingFeedback (3.24 Training Feedback)
def _can_manage_feedback(request, feedback):
    """The attendee (the giver) OR a tenant admin — mirrors 3.20 _can_edit_feedback (giver/admin).
    Without this, any tenant user could edit/delete or unmask anyone's feedback."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return bool(profile is not None and profile.pk == feedback.attendance.employee_id)


def _issue_certificate(request, *, employee_id, course, source_attendance=None, source_progress=None):
    """Shared body for the two 'issue from ...' convenience routes — pre-fills the form and saves."""
    initial = {"employee": employee_id, "course": course.pk, "issued_on": timezone.localdate(),
               "title": course.certification_name or course.title}
    if source_attendance is not None:
        initial["source_attendance"] = source_attendance.pk
    if source_progress is not None:
        initial["source_progress"] = source_progress.pk
    if request.method == "POST":
        form = TrainingCertificateForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Certificate {obj.number} issued.")
            return redirect("hrm:trainingcertificate_detail", pk=obj.pk)
    else:
        form = TrainingCertificateForm(initial=initial, tenant=request.tenant)
    return render(request, "hrm/trainingadmin/trainingcertificate/form.html",
                  {"form": form, "is_edit": False})
