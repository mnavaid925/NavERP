"""HRM 3.5 Job Requisition — Jobrequisition views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.JobRequisition._helpers import _JR_CLONE_FK_FIELDS, _JR_CLONE_PLAIN_FIELDS
from apps.hrm.models import (
    EMPLOYMENT_TYPE_CHOICES,
    EmployeeProfile,
    JR_STATUS_CHOICES,
    JobDescriptionTemplate,
    JobRequisition,
    POSTING_TYPE_CHOICES,
    PRIORITY_CHOICES,
    REQ_TYPE_CHOICES,
)
from apps.hrm.forms import (
    JobRequisitionForm,
    RequisitionApprovalForm,
)
from apps.hrm.views.EmployeeManagement._helpers import _is_hr_admin
from apps.hrm.views.JobRequisition._helpers import _JR_CLONE_FK_FIELDS, _JR_CLONE_PLAIN_FIELDS


# Job Requisitions — the hub record + its approval-chain state machine.
@login_required
def jobrequisition_list(request):
    return crud_list(
        request,
        JobRequisition.objects.filter(tenant=request.tenant)
        .select_related("designation", "department", "hiring_manager__party", "recruiter__party"),
        "hrm/recruitment/jobrequisition/list.html",
        search_fields=["number", "title", "location", "designation__name"],
        # ``posting_type`` backs the 3.38 "Internal Mobility" sidebar deep-link
        # (?posting_type=internal) — without it in this tuple the deep-link silently showed every
        # requisition instead of just the internally-posted ones.
        filters=[("status", "status", False), ("priority", "priority", False),
                 ("department", "department_id", True), ("hiring_manager", "hiring_manager_id", True),
                 ("req_type", "req_type", False), ("employment_type", "employment_type", False),
                 ("posting_type", "posting_type", False)],
        extra_context={"status_choices": JR_STATUS_CHOICES,
                       "priority_choices": PRIORITY_CHOICES,
                       "req_type_choices": REQ_TYPE_CHOICES,
                       "employment_type_choices": EMPLOYMENT_TYPE_CHOICES,
                       "posting_type_choices": POSTING_TYPE_CHOICES,
                       "departments": OrgUnit.objects.filter(tenant=request.tenant, kind="department")
                       .order_by("name"),
                       "hiring_managers": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@tenant_admin_required  # a requisition authorizes headcount + budget — authoritative HR record
def jobrequisition_create(request):
    # Custom create (not crud_create) so the "Save & Apply Template" button can copy the selected
    # template's JD body onto the new requisition in the same request.
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = JobRequisitionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            if request.POST.get("apply_template") and obj.template_id:
                apply_template_to_requisition(obj, obj.template)
                messages.success(request, f"Requisition {obj.number} created; "
                                 f"template '{obj.template.name}' applied.")
            else:
                messages.success(request, f"Requisition {obj.number} created.")
            return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    else:
        form = JobRequisitionForm(tenant=request.tenant)
    return render(request, "hrm/recruitment/jobrequisition/form.html",
                  {"form": form, "is_edit": False})


@login_required
def jobrequisition_detail(request, pk):
    obj = get_object_or_404(
        JobRequisition.objects.select_related(
            "designation__job_grade", "job_grade", "department", "cost_center",
            "hiring_manager__party", "recruiter__party", "template"),
        pk=pk, tenant=request.tenant)
    approvals = list(obj.approvals.select_related("approver", "decided_by").order_by("step_order"))
    approved_count = sum(1 for a in approvals if a.status == "approved")
    total_count = len(approvals)
    approval_progress = int(round(approved_count / total_count * 100)) if total_count else 0
    # Current pending step (lowest order) computed from the already-fetched list (no extra query).
    current_step = next((a for a in approvals if a.status == "pending"), None)
    # 3.6 — surface the applicants on the requisition hub (was a dead-end before Candidate Management).
    applications = list(obj.applications.select_related("candidate").order_by("-applied_at")[:10])
    application_count = obj.applications.count()
    return render(request, "hrm/recruitment/jobrequisition/detail.html", {
        "obj": obj,
        "approvals": approvals,
        "approved_count": approved_count,
        "total_count": total_count,
        "approval_progress": approval_progress,
        "current_step": current_step,
        "applications": applications,
        "application_count": application_count,
        "approval_form": RequisitionApprovalForm(tenant=request.tenant),
        "is_hr_admin": _is_hr_admin(request.user),  # gates the admin-only action UI in the template
        "jd_templates": JobDescriptionTemplate.objects.filter(tenant=request.tenant, is_active=True)
        .only("id", "name").order_by("name"),  # dropdown uses pk+name only (skip the jd_* TEXT cols)
        "can_submit": obj.status in ("draft", "rejected"),
        "can_approve": obj.status == "pending_approval",
        "can_post": obj.status == "approved",
        "can_hold": obj.status in ("approved", "posted"),
        "can_fill": obj.status in ("posted", "on_hold"),
        "can_cancel": obj.status not in ("filled", "cancelled"),
        "can_edit": obj.status in ("draft", "rejected"),
    })


@tenant_admin_required  # a requisition authorizes headcount + budget — authoritative HR record
def jobrequisition_edit(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    # Only a draft or rejected req is editable — once it's in the approval flow its terms are locked.
    if obj.status not in ("draft", "rejected"):
        messages.error(request, "Only a draft or rejected requisition can be edited.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    return crud_edit(request, model=JobRequisition, pk=pk, form_class=JobRequisitionForm,
                     template="hrm/recruitment/jobrequisition/form.html",
                     success_url="hrm:jobrequisition_list")


@tenant_admin_required  # a requisition authorizes headcount + budget — authoritative HR record
@require_POST
def jobrequisition_delete(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    # Only a draft req is deletable — once submitted it is cancelled (keeps the audit trail).
    if obj.status != "draft":
        messages.error(request, "Only a draft requisition can be deleted. Cancel it instead.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Requisition deleted.")
    return redirect("hrm:jobrequisition_list")


# --- Workflow state-machine actions (all privileged; the form never sets these fields) ---
@tenant_admin_required
@require_POST
def jobrequisition_submit(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    # A rejected requisition can be edited and re-submitted (mirrors the editable-when-rejected guard).
    if obj.status not in ("draft", "rejected"):
        messages.error(request, "Only a draft or rejected requisition can be submitted.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    with transaction.atomic():
        # On re-submit of a rejected req, reset the prior chain so it re-approves from the top.
        if obj.status == "rejected":
            obj.approvals.update(status="pending", decided_at=None, decided_by=None, comments="")
        generate_approval_chain(obj)  # idempotent: builds the default chain only when none exist
        obj.status = "pending_approval"
        obj.submitted_at = timezone.now()
        obj.save(update_fields=["status", "submitted_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit", "to": obj.status})
    messages.success(request, f"Requisition {obj.number} submitted for approval.")
    return redirect("hrm:jobrequisition_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def jobrequisition_approve_step(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    if obj.status != "pending_approval":
        messages.error(request, "Only a requisition pending approval can be approved.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    step = obj.approvals.filter(status="pending").order_by("step_order").first()
    if step is None:
        messages.error(request, "No pending approval step to approve.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    with transaction.atomic():
        step.status = "approved"
        step.decided_at = timezone.now()
        step.decided_by = request.user
        step.save(update_fields=["status", "decided_at", "decided_by", "updated_at"])
        # When the last pending step clears, the whole requisition is approved.
        if not obj.approvals.filter(status="pending").exists():
            obj.status = "approved"
            obj.approved_at = timezone.now()
            obj.save(update_fields=["status", "approved_at", "updated_at"])
        write_audit_log(request.user, obj, "update",
                        {"action": "approve_step", "step": step.step_order, "to": obj.status})
    if obj.status == "approved":
        messages.success(request, f"Final approval recorded — {obj.number} is approved.")
    else:
        messages.success(request, f"Approval step #{step.step_order} approved.")
    return redirect("hrm:jobrequisition_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def jobrequisition_reject(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    if obj.status != "pending_approval":
        messages.error(request, "Only a requisition pending approval can be rejected.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    step = obj.approvals.filter(status="pending").order_by("step_order").first()
    with transaction.atomic():
        if step is not None:
            step.status = "rejected"
            step.decided_at = timezone.now()
            step.decided_by = request.user
            step.comments = request.POST.get("comments", "").strip()[:2000]
            step.save(update_fields=["status", "decided_at", "decided_by", "comments", "updated_at"])
        obj.status = "rejected"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
    messages.success(request, f"Requisition {obj.number} rejected.")
    return redirect("hrm:jobrequisition_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def jobrequisition_return(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    if obj.status != "pending_approval":
        messages.error(request, "Only a requisition pending approval can be returned for revision.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    step = obj.approvals.filter(status="pending").order_by("step_order").first()
    with transaction.atomic():
        if step is not None:
            step.status = "returned"
            step.decided_at = timezone.now()
            step.decided_by = request.user
            step.comments = request.POST.get("comments", "").strip()[:2000]
            step.save(update_fields=["status", "decided_at", "decided_by", "comments", "updated_at"])
        # Reset the chain so a fresh submit re-approves from the top, and reopen the req for editing.
        obj.approvals.exclude(pk=step.pk if step else None).update(
            status="pending", decided_at=None, decided_by=None, comments="")
        obj.status = "draft"
        obj.submitted_at = None
        obj.save(update_fields=["status", "submitted_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "return"})
    messages.success(request, f"Requisition {obj.number} returned for revision.")
    return redirect("hrm:jobrequisition_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def jobrequisition_post(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    if obj.status != "approved":
        messages.error(request, "Only an approved requisition can be posted.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    obj.status = "posted"
    obj.posted_at = timezone.now()
    fields = ["status", "posted_at", "updated_at"]
    # Mint the public careers-portal token once (3.6) so the posted opening gets a shareable apply URL.
    if not obj.public_token:
        obj.public_token = secrets.token_urlsafe(32)
        fields.append("public_token")
    obj.save(update_fields=fields)
    write_audit_log(request.user, obj, "update", {"action": "post"})
    messages.success(request, f"Requisition {obj.number} posted.")
    return redirect("hrm:jobrequisition_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def jobrequisition_hold(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    if obj.status not in ("approved", "posted"):
        messages.error(request, "Only an approved or posted requisition can be placed on hold.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    obj.status = "on_hold"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "hold"})
    messages.success(request, f"Requisition {obj.number} placed on hold.")
    return redirect("hrm:jobrequisition_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def jobrequisition_mark_filled(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    if obj.status not in ("posted", "on_hold"):
        messages.error(request, "Only a posted or on-hold requisition can be marked filled.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    obj.status = "filled"
    obj.filled_at = timezone.now()
    obj.save(update_fields=["status", "filled_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "fill"})
    messages.success(request, f"Requisition {obj.number} marked filled.")
    return redirect("hrm:jobrequisition_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def jobrequisition_cancel(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    if obj.status in ("filled", "cancelled"):
        messages.error(request, "This requisition can no longer be cancelled.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    obj.status = "cancelled"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "cancel"})
    messages.success(request, f"Requisition {obj.number} cancelled.")
    return redirect("hrm:jobrequisition_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def jobrequisition_apply_template(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    if obj.status not in ("draft", "rejected"):
        messages.error(request, "A template can only be applied to a draft or rejected requisition.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    template_id = request.POST.get("template_id", "").strip()
    if not template_id.isdigit():
        messages.error(request, "Select a template to apply.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    tmpl = get_object_or_404(JobDescriptionTemplate, pk=int(template_id), tenant=request.tenant)
    apply_template_to_requisition(obj, tmpl)
    write_audit_log(request.user, obj, "update", {"action": "apply_template", "template": tmpl.name})
    messages.success(request, f"Template '{tmpl.name}' applied to {obj.number}.")
    return redirect("hrm:jobrequisition_detail", pk=obj.pk)


@tenant_admin_required  # cloning creates a new requisition — authoritative HR record
@require_POST
def jobrequisition_clone(request, pk):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before cloning records.")
        return redirect("dashboard:home")
    source = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    new_req = JobRequisition(tenant=request.tenant)  # status defaults to draft; *_at stamps stay null
    for field in _JR_CLONE_FK_FIELDS:
        setattr(new_req, f"{field}_id", getattr(source, f"{field}_id"))
    for field in _JR_CLONE_PLAIN_FIELDS:
        setattr(new_req, field, getattr(source, field))
    new_req.save()
    write_audit_log(request.user, new_req, "create", {"cloned_from": source.number})
    messages.success(request, f"Requisition cloned from {source.number} as {new_req.number}.")
    return redirect("hrm:jobrequisition_detail", pk=new_req.pk)
