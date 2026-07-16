"""HRM 3.6 Candidate Management — Application views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.CandidateManagement._helpers import _auto_send_for_stage, _send_candidate_email
from apps.hrm.models import (
    APPLICATION_STAGE_CHOICES,
    APPLICATION_TERMINAL_STAGES,
    CANDIDATE_SOURCE_CHOICES,
    CandidateEmailTemplate,
    CandidateProfile,
    JobApplication,
    JobRequisition,
    REJECTION_REASON_CHOICES,
)
from apps.hrm.forms import (
    JobApplicationForm,
)
from apps.hrm.views.CandidateManagement._helpers import _auto_send_for_stage, _send_candidate_email
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._common import _date


# --------------------------------------------------------------- Job Applications (3.6)
@login_required
def application_list(request):
    qs = (JobApplication.objects.filter(tenant=request.tenant)
          .select_related("candidate", "requisition", "referred_by__party"))
    return crud_list(
        request, qs, "hrm/candidates/application/list.html",
        search_fields=["number", "candidate__first_name", "candidate__last_name",
                       "candidate__email", "requisition__title", "requisition__number"],
        filters=[("stage", "stage", False), ("source", "source", False),
                 ("requisition", "requisition_id", True), ("candidate", "candidate_id", True)],
        extra_context={
            "stage_choices": APPLICATION_STAGE_CHOICES,
            "source_choices": CANDIDATE_SOURCE_CHOICES,
            "requisitions": JobRequisition.objects.filter(tenant=request.tenant).only("pk", "number", "title"),
            "candidates": CandidateProfile.objects.filter(tenant=request.tenant)
            .only("pk", "first_name", "last_name", "number"),
        },
    )


@login_required
def application_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = JobApplicationForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Application {obj.number} created.")
            # Land on the new application so the recruiter can immediately work its pipeline.
            return redirect("hrm:application_detail", pk=obj.pk)
    else:
        # Pre-select the candidate/requisition when arriving from a candidate hub or a requisition hub.
        form = JobApplicationForm(tenant=request.tenant, initial={
            "candidate": request.GET.get("candidate") or None,
            "requisition": request.GET.get("requisition") or None,
        })
    return render(request, "hrm/candidates/application/form.html", {"form": form, "is_edit": False})


@login_required
def application_detail(request, pk):
    obj = get_object_or_404(
        JobApplication.objects.filter(tenant=request.tenant)
        .select_related("candidate__party", "requisition", "referred_by__party"), pk=pk)
    return render(request, "hrm/candidates/application/detail.html", {
        "obj": obj,
        "communications": obj.communications.select_related("template", "sent_by").order_by("-sent_at")[:50],
        "email_templates": CandidateEmailTemplate.objects.filter(tenant=request.tenant, is_active=True),
        "stage_choices": APPLICATION_STAGE_CHOICES,
        "rejection_reason_choices": REJECTION_REASON_CHOICES,
    })


@login_required
def application_edit(request, pk):
    return crud_edit(
        request, model=JobApplication, pk=pk, form_class=JobApplicationForm,
        template="hrm/candidates/application/form.html",
        success_url="hrm:application_list")


@login_required
@require_POST
def application_delete(request, pk):
    return crud_delete(request, model=JobApplication, pk=pk, success_url="hrm:application_list")


@login_required
@require_POST
def application_advance_stage(request, pk):
    obj = get_object_or_404(
        JobApplication.objects.filter(tenant=request.tenant).select_related("candidate", "requisition"),
        pk=pk)
    new_stage = request.POST.get("new_stage", "")
    valid = dict(APPLICATION_STAGE_CHOICES)
    if new_stage not in valid:
        messages.error(request, "Invalid stage.")
        return redirect("hrm:application_detail", pk=obj.pk)
    if obj.stage in APPLICATION_TERMINAL_STAGES:
        messages.error(request, "This application is closed. Reopen it before changing the stage.")
        return redirect("hrm:application_detail", pk=obj.pk)
    obj.stage = new_stage
    obj.stage_changed_at = timezone.now()
    fields = ["stage", "stage_changed_at", "updated_at"]
    if new_stage == "hired":
        obj.hired_on = _date.today()
        fields.append("hired_on")
        if obj.candidate.status != "hired":
            obj.candidate.status = "hired"
            obj.candidate.save(update_fields=["status", "updated_at"])
    obj.save(update_fields=fields)
    write_audit_log(request.user, obj, "update", {"action": "advance_stage", "stage": new_stage})
    _auto_send_for_stage(obj, new_stage, request.user)
    messages.success(request, f"Application moved to {valid[new_stage]}.")
    return redirect("hrm:application_detail", pk=obj.pk)


@login_required
@require_POST
def application_reject(request, pk):
    obj = get_object_or_404(
        JobApplication.objects.filter(tenant=request.tenant).select_related("candidate", "requisition"),
        pk=pk)
    if obj.stage in APPLICATION_TERMINAL_STAGES:
        messages.error(request, "This application is already closed.")
        return redirect("hrm:application_detail", pk=obj.pk)
    reason = request.POST.get("rejection_reason", "")
    if reason and reason not in dict(REJECTION_REASON_CHOICES):
        reason = "other"
    obj.stage = "rejected"
    obj.stage_changed_at = timezone.now()
    obj.rejection_reason = reason
    obj.rejection_notes = request.POST.get("rejection_notes", "").strip()
    obj.save(update_fields=["stage", "stage_changed_at", "rejection_reason", "rejection_notes", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "reject", "reason": reason})
    template = (CandidateEmailTemplate.objects
                .filter(tenant=request.tenant, template_type="rejection", is_active=True, is_auto_send=True)
                .order_by("pk").first())
    if template is not None:
        _send_candidate_email(obj, template=template, sent_by=request.user)
    messages.success(request, "Application rejected.")
    return redirect("hrm:application_detail", pk=obj.pk)


@login_required
@require_POST
def application_withdraw(request, pk):
    obj = get_object_or_404(JobApplication.objects.filter(tenant=request.tenant), pk=pk)
    if obj.stage in APPLICATION_TERMINAL_STAGES:
        messages.error(request, "This application is already closed.")
        return redirect("hrm:application_detail", pk=obj.pk)
    obj.stage = "withdrawn"
    obj.stage_changed_at = timezone.now()
    obj.save(update_fields=["stage", "stage_changed_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "withdraw"})
    messages.success(request, "Application withdrawn.")
    return redirect("hrm:application_detail", pk=obj.pk)


@login_required
@require_POST
def application_hold(request, pk):
    obj = get_object_or_404(
        JobApplication.objects.filter(tenant=request.tenant).select_related("candidate", "requisition"),
        pk=pk)
    if obj.stage in APPLICATION_TERMINAL_STAGES:
        messages.error(request, "This application is already closed.")
        return redirect("hrm:application_detail", pk=obj.pk)
    obj.stage = "on_hold"
    obj.stage_changed_at = timezone.now()
    obj.save(update_fields=["stage", "stage_changed_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "hold"})
    template = (CandidateEmailTemplate.objects
                .filter(tenant=request.tenant, template_type="on_hold", is_active=True, is_auto_send=True)
                .order_by("pk").first())
    if template is not None:
        _send_candidate_email(obj, template=template, sent_by=request.user)
    messages.success(request, "Application placed on hold.")
    return redirect("hrm:application_detail", pk=obj.pk)


@login_required
@require_POST
def application_send_email(request, pk):
    obj = get_object_or_404(
        JobApplication.objects.filter(tenant=request.tenant).select_related("candidate", "requisition"),
        pk=pk)
    if obj.candidate.do_not_contact:
        messages.error(request, "This candidate is marked do-not-contact; email not sent.")
        return redirect("hrm:application_detail", pk=obj.pk)
    template = None
    template_id = request.POST.get("template_id")
    if template_id:
        template = CandidateEmailTemplate.objects.filter(
            tenant=request.tenant, pk=template_id).first()
    subject = request.POST.get("subject", "").strip() or None
    body = request.POST.get("body", "").strip() or None
    if not body and template is None:
        messages.error(request, "Pick a template or write a message body.")
        return redirect("hrm:application_detail", pk=obj.pk)
    comm = _send_candidate_email(obj, template=template, subject=subject, body=body, sent_by=request.user)
    if comm is None:
        messages.error(request, "Nothing to send.")
    else:
        write_audit_log(request.user, comm, "create", {"to": obj.candidate.email})
        messages.success(request, f"Email sent to {obj.candidate.name}.")
    return redirect("hrm:application_detail", pk=obj.pk)
