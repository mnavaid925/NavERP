"""HRM 3.24 Training Administration — Trainingcertificate views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.TrainingAdministration._helpers import _issue_certificate
from apps.hrm.models import (
    EmployeeProfile,
    LearningProgress,
    TrainingAttendance,
    TrainingCertificate,
    TrainingCourse,
)
from apps.hrm.forms import (
    TrainingCertificateForm,
)
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.TrainingAdministration._helpers import _issue_certificate


# ------------------------------------------------------------ TrainingCertificate (3.24 Certificates)
@login_required
def trainingcertificate_list(request):
    qs = (TrainingCertificate.objects.filter(tenant=request.tenant)
          .select_related("employee__party", "course"))
    return crud_list(
        request, qs.order_by("-issued_on"),
        "hrm/trainingadmin/trainingcertificate/list.html",
        search_fields=("number", "title", "verification_code", "employee__party__name", "course__title"),
        filters=[("status", "status", False), ("course", "course_id", True), ("employee", "employee_id", True)],
        extra_context={
            "status_choices": TrainingCertificate.STATUS_CHOICES,
            "courses": TrainingCourse.objects.filter(tenant=request.tenant, is_certification=True).order_by("title"),
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
            "is_admin": _is_admin(request.user),   # gate the admin-only Issue/Edit/Delete buttons
        },
    )


# Issuing/editing a certificate mints/alters a real credential — tenant-admin only (revoke already is).
# An employee must not be able to self-mark a completed attendance and self-issue a verifiable cert.
@tenant_admin_required
def trainingcertificate_create(request):
    return crud_create(request, form_class=TrainingCertificateForm,
                       template="hrm/trainingadmin/trainingcertificate/form.html",
                       success_url="hrm:trainingcertificate_list")


@tenant_admin_required
def trainingcertificate_issue_from_attendance(request, attendance_pk):
    att = get_object_or_404(
        TrainingAttendance.objects.select_related("session__course"), pk=attendance_pk, tenant=request.tenant)
    if att.completion_status != "completed" or not att.session.course.is_certification:
        messages.error(request, "A certificate can only be issued from a completed session on a certification course.")
        return redirect("hrm:trainingattendance_detail", pk=att.pk)
    existing = att.certificates_issued.first()
    if existing is not None:
        messages.info(request, "A certificate has already been issued from this attendance record.")
        return redirect("hrm:trainingcertificate_detail", pk=existing.pk)
    return _issue_certificate(request, employee_id=att.employee_id, course=att.session.course,
                              source_attendance=att)


@tenant_admin_required
def trainingcertificate_issue_from_progress(request, progress_pk):
    prog = get_object_or_404(
        LearningProgress.objects.select_related("course"), pk=progress_pk, tenant=request.tenant)
    if prog.status != "completed" or not prog.course.is_certification:
        messages.error(request, "A certificate can only be issued from completed progress on a certification course.")
        return redirect("hrm:learningprogress_detail", pk=prog.pk)
    existing = prog.certificates_issued.first()
    if existing is not None:
        messages.info(request, "A certificate has already been issued from this progress record.")
        return redirect("hrm:trainingcertificate_detail", pk=existing.pk)
    return _issue_certificate(request, employee_id=prog.employee_id, course=prog.course,
                              source_progress=prog)


@login_required
def trainingcertificate_detail(request, pk):
    return crud_detail(request, model=TrainingCertificate, pk=pk,
                       template="hrm/trainingadmin/trainingcertificate/detail.html",
                       select_related=("employee__party", "course", "source_attendance__session", "source_progress"),
                       extra_context={"is_admin": _is_admin(request.user)})


@tenant_admin_required
def trainingcertificate_edit(request, pk):
    obj = get_object_or_404(TrainingCertificate, pk=pk, tenant=request.tenant)
    if obj.status == "revoked":
        messages.error(request, "A revoked certificate can't be edited.")
        return redirect("hrm:trainingcertificate_detail", pk=obj.pk)
    return crud_edit(request, model=TrainingCertificate, pk=pk, form_class=TrainingCertificateForm,
                     template="hrm/trainingadmin/trainingcertificate/form.html",
                     success_url="hrm:trainingcertificate_list")


@tenant_admin_required
@require_POST
def trainingcertificate_delete(request, pk):
    obj = get_object_or_404(TrainingCertificate, pk=pk, tenant=request.tenant)
    if obj.status == "issued":
        messages.error(request, "An issued certificate can't be deleted — revoke it instead.")
        return redirect("hrm:trainingcertificate_detail", pk=obj.pk)
    return crud_delete(request, model=TrainingCertificate, pk=pk, success_url="hrm:trainingcertificate_list")


@tenant_admin_required
@require_POST
def trainingcertificate_revoke(request, pk):
    obj = get_object_or_404(
        TrainingCertificate.objects.select_related("employee__party"), pk=pk, tenant=request.tenant)
    if obj.status != "issued":
        messages.error(request, "Only an issued certificate can be revoked.")
        return redirect("hrm:trainingcertificate_detail", pk=obj.pk)
    obj.status = "revoked"
    obj.revoked_reason = request.POST.get("revoked_reason", "").strip()
    obj.save(update_fields=["status", "revoked_reason", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "revoke"})
    messages.success(request, f"Certificate {obj.number} revoked.")
    return redirect("hrm:trainingcertificate_detail", pk=obj.pk)


@login_required
def trainingcertificate_print(request, pk):
    obj = get_object_or_404(
        TrainingCertificate.objects.select_related("employee__party", "course", "tenant"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/trainingadmin/trainingcertificate/print.html", {"obj": obj})
