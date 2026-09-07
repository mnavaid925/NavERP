"""Projects 7.1 — ProjectRequest views: the intake register and its governance verbs.

Five verbs, all POST-only, and every one of them refuses a disallowed transition with a message
rather than a 500 or a silent no-op:

``submit`` → draft/needs_information ⇒ submitted · ``approve`` (tenant admin) ⇒ approved + Go ·
``reject`` (tenant admin) ⇒ rejected + No-Go · ``return`` ⇒ needs_information ·
``convert`` (tenant admin) ⇒ runs ``convert_to_project()`` and lands a `Project`.

Audit actions stay ≤ 10 characters (`core.AuditLog.action` is `varchar(10)`): the verb itself
goes in ``changes`` (see `apps/projects/views/_common.py`).
"""
from apps.projects.forms import ProjectRequestDecisionForm, ProjectRequestForm
from apps.projects.models import ProjectRequest
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import login_required, redirect, render
from apps.projects.views._helpers import org_units


@login_required
def prq_list(request):
    """The demand-intake register."""
    qs = (ProjectRequest.objects.filter(tenant=request.tenant)
          .select_related("org_unit", "assigned_approver", "converted_project"))
    return crud_list(
        request, qs, "projects/initiation/projectrequest/list.html",
        search_fields=["title", "description", "number"],
        filters=[("status", "status", False),
                 ("request_type", "request_type", False),
                 ("priority", "priority", False),
                 ("risk_rating", "risk_rating", False),
                 ("feasibility", "feasibility", False),
                 ("decision", "decision", False),
                 ("org_unit", "org_unit_id", True)],
        extra_context={
            "status_choices": ProjectRequest.STATUS_CHOICES,
            "request_type_choices": ProjectRequest.REQUEST_TYPE_CHOICES,
            "priority_choices": ProjectRequest.PRIORITY_CHOICES,
            "risk_rating_choices": ProjectRequest.RISK_RATING_CHOICES,
            "feasibility_choices": ProjectRequest.FEASIBILITY_CHOICES,
            "decision_choices": ProjectRequest.DECISION_CHOICES,
            "org_units": org_units(request.tenant),
        },
    )


@login_required
def prq_create(request):
    """Thin wrapper around crud_create so ``created_by`` gets stamped — the generic helper saves
    without knowing about this module's authorship audit."""
    # FIRST LINE, not inside `if form.is_valid()`: a tenant-less user (User.tenant is SET_NULL,
    # so any member of a deleted tenant, not just the superuser) must never reach the form. GET
    # skips the POST branch entirely, and TenantModelForm only scopes its FK dropdowns when
    # tenant is not None — so the un-hoisted guard rendered every workspace's parties, org units,
    # documents and user emails. Same shape as apps/core/crud.py's crud_create.
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ProjectRequestForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Request {obj.number} created.")
            return redirect("projects:prq_detail", pk=obj.pk)
    else:
        form = ProjectRequestForm(tenant=request.tenant)
    return render(request, "projects/initiation/projectrequest/form.html",
                  {"form": form, "is_edit": False})


@login_required
def prq_detail(request, pk):
    obj = get_object_or_404(
        ProjectRequest.objects.select_related(
            "org_unit", "requester_party", "source_opportunity", "currency",
            "assigned_reviewer", "assigned_approver", "decided_by", "converted_project"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/initiation/projectrequest/detail.html",
                  {"obj": obj, "decision_form": ProjectRequestDecisionForm()})


@login_required
def prq_edit(request, pk):
    return crud_edit(
        request, model=ProjectRequest, pk=pk, form_class=ProjectRequestForm,
        template="projects/initiation/projectrequest/form.html",
        success_url="projects:prq_list",
    )


@login_required
@require_POST
def prq_delete(request, pk):
    return crud_delete(request, model=ProjectRequest, pk=pk, success_url="projects:prq_list")


# -- governance verbs ---------------------------------------------------------------------------

@login_required
@require_POST
def prq_submit(request, pk):
    """Send a draft into screening. Re-submission after a send-back is the normal path, not an
    error, so ``needs_information`` is an allowed source."""
    obj = get_object_or_404(ProjectRequest, pk=pk, tenant=request.tenant)
    if obj.status not in ("draft", "needs_information"):
        messages.info(request, f"That request is already {obj.get_status_display().lower()}.")
        return redirect("projects:prq_detail", pk=obj.pk)
    obj.status = "submitted"
    obj.submitted_at = timezone.now()
    obj.save(update_fields=["status", "submitted_at", "updated_at"])
    write_audit_log(request.user, obj, "submit",
                    changes={"verb": "submit", "from": "draft", "to": obj.status})
    messages.success(request, f"Submitted “{obj.title}” for screening.")
    return redirect("projects:prq_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def prq_approve(request, pk):
    """Record the Go decision. Only an approved request can be converted."""
    obj = get_object_or_404(ProjectRequest, pk=pk, tenant=request.tenant)
    if obj.status not in ProjectRequest.DECISION_STATUSES:
        messages.error(
            request,
            f"Only a request under review can be approved — this one is "
            f"{obj.get_status_display().lower()}.")
        return redirect("projects:prq_detail", pk=obj.pk)
    obj.status = "approved"
    obj.decision = "go"
    obj.decided_by = request.user
    obj.decided_at = timezone.now()
    obj.save(update_fields=["status", "decision", "decided_by", "decided_at", "updated_at"])
    write_audit_log(request.user, obj, "approve",
                    changes={"verb": "approve", "from": "submitted", "to": obj.status})
    messages.success(request, f"Approved “{obj.title}” — it can now be converted to a project.")
    return redirect("projects:prq_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def prq_reject(request, pk):
    obj = get_object_or_404(ProjectRequest, pk=pk, tenant=request.tenant)
    form = ProjectRequestDecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "A rejection needs a stated reason.")
        return redirect("projects:prq_detail", pk=obj.pk)
    if obj.status == "rejected":
        messages.info(request, "That request is already rejected.")
        return redirect("projects:prq_detail", pk=obj.pk)
    if obj.status == "converted":
        messages.error(request, "A converted request cannot be rejected — reject the project.")
        return redirect("projects:prq_detail", pk=obj.pk)
    obj.status = "rejected"
    obj.decision = "no_go"
    obj.rejection_reason = form.cleaned_data["reason"]
    obj.decided_by = request.user
    obj.decided_at = timezone.now()
    obj.save(update_fields=["status", "decision", "rejection_reason", "decided_by",
                            "decided_at", "updated_at"])
    write_audit_log(request.user, obj, "reject",
                    changes={"verb": "reject", "from": "submitted", "to": obj.status})
    messages.success(request, f"Rejected “{obj.title}”.")
    return redirect("projects:prq_detail", pk=obj.pk)


@login_required
@require_POST
def prq_return_for_information(request, pk):
    """Send back to the requester. The register's honesty depends on this being a real state and
    not a silent no-op — a request stuck in "assessment" with no answer is invisible work."""
    obj = get_object_or_404(ProjectRequest, pk=pk, tenant=request.tenant)
    form = ProjectRequestDecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Say what information is needed.")
        return redirect("projects:prq_detail", pk=obj.pk)
    if obj.status == "needs_information":
        messages.info(request, "That request is already waiting on information.")
        return redirect("projects:prq_detail", pk=obj.pk)
    if obj.status in ("draft", "converted"):
        messages.error(
            request, f"A {obj.get_status_display().lower()} request cannot be sent back.")
        return redirect("projects:prq_detail", pk=obj.pk)
    obj.status = "needs_information"
    obj.information_requested = form.cleaned_data["reason"]
    obj.save(update_fields=["status", "information_requested", "updated_at"])
    write_audit_log(request.user, obj, "return",
                    changes={"verb": "return_for_information", "from": "screening",
                             "to": obj.status})
    messages.success(request, f"Sent “{obj.title}” back for information.")
    return redirect("projects:prq_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def prq_convert(request, pk):
    """The highest-value verb in the sub-module: the request becomes a project.

    Guarded twice — the view checks the status, and ``convert_to_project()`` refuses a request
    that already has a project — because a double-click here would otherwise mint two projects
    for one demand.
    """
    obj = get_object_or_404(ProjectRequest, pk=pk, tenant=request.tenant)
    if obj.status != "approved":
        messages.error(request, "Only an approved request can be converted to a project.")
        return redirect("projects:prq_detail", pk=obj.pk)
    if obj.converted_project_id:
        messages.info(request, "That request has already been converted.")
        return redirect("projects:prq_detail", pk=obj.pk)
    project = obj.convert_to_project(user=request.user)
    if project is None:
        messages.info(request, "That request has already been converted.")
        return redirect("projects:prq_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "convert",
                    changes={"verb": "convert", "from": obj.number, "to": project.number})
    messages.success(request, f"Created project {project.number} from {obj.number}.")
    return redirect("projects:prj_detail", pk=project.pk)
