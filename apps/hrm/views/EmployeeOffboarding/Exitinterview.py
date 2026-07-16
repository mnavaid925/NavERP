"""HRM 3.4 Employee Offboarding — Exitinterview views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.EmployeeOffboarding._helpers import _offboarding_create
from apps.hrm.models import (
    ExitInterview,
)
from apps.hrm.forms import (
    ExitInterviewForm,
)
from apps.hrm.views.EmployeeOffboarding._helpers import _offboarding_create


# ---------------------------------------------------------- Exit Interviews (3.4)
@login_required
def exitinterview_list(request):
    return crud_list(
        request,
        ExitInterview.objects.filter(tenant=request.tenant)
        .select_related("case__employee__party", "interviewer"),
        "hrm/offboarding/exitinterview/list.html",
        search_fields=["number", "case__employee__party__name", "case__number"],
        filters=[("status", "status", False), ("mode", "mode", False)],
        extra_context={"status_choices": ExitInterview.EI_STATUS_CHOICES,
                       "mode_choices": ExitInterview.MODE_CHOICES},
    )


@login_required
def exitinterview_create(request):
    return _offboarding_create(
        request, ExitInterviewForm, "hrm/offboarding/exitinterview/form.html",
        lambda obj: ("hrm:separationcase_detail", obj.case_id))


@login_required
def exitinterview_detail(request, pk):
    obj = get_object_or_404(
        ExitInterview.objects.select_related("case__employee__party", "interviewer"),
        pk=pk, tenant=request.tenant)
    ratings = [(label, getattr(obj, field)) for field, label in ExitInterview.RATING_FIELDS]
    return render(request, "hrm/offboarding/exitinterview/detail.html",
                  {"obj": obj, "ratings": ratings})


@login_required
def exitinterview_edit(request, pk):
    obj = get_object_or_404(ExitInterview, pk=pk, tenant=request.tenant)
    if obj.status == "completed":
        messages.error(request, "A completed exit interview cannot be edited.")
        return redirect("hrm:exitinterview_detail", pk=obj.pk)
    return crud_edit(request, model=ExitInterview, pk=pk, form_class=ExitInterviewForm,
                     template="hrm/offboarding/exitinterview/form.html",
                     success_url="hrm:exitinterview_list")


@login_required
@require_POST
def exitinterview_delete(request, pk):
    obj = get_object_or_404(ExitInterview, pk=pk, tenant=request.tenant)
    if obj.status == "completed":
        messages.error(request, "A completed exit interview cannot be deleted.")
        return redirect("hrm:exitinterview_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Exit interview deleted.")
    return redirect("hrm:exitinterview_list")


@tenant_admin_required  # closing out an exit interview is a privileged HR action (terminal + audited)
@require_POST
def exitinterview_complete(request, pk):
    obj = get_object_or_404(ExitInterview, pk=pk, tenant=request.tenant)
    if obj.status == "scheduled":
        obj.status = "completed"
        obj.conducted_at = timezone.now()
        obj.save(update_fields=["status", "conducted_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "complete"})
        messages.success(request, f"Exit interview {obj.number} marked completed.")
    else:
        messages.error(request, "Only a scheduled interview can be completed.")
    return redirect("hrm:exitinterview_detail", pk=obj.pk)


@tenant_admin_required  # skipping an exit interview is a privileged HR action
@require_POST
def exitinterview_skip(request, pk):
    obj = get_object_or_404(ExitInterview, pk=pk, tenant=request.tenant)
    if obj.status == "scheduled":
        obj.status = "skipped"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "skip"})
        messages.success(request, f"Exit interview {obj.number} skipped.")
    else:
        messages.error(request, "Only a scheduled interview can be skipped.")
    return redirect("hrm:exitinterview_detail", pk=obj.pk)
