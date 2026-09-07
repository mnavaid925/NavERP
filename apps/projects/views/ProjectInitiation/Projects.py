"""Projects 7.1 — Project views: the charter register.

Two verbs own ``charter_status`` (``submit-charter`` / ``approve-charter``); ``status`` itself is
advanced by 7.1's kickoff verbs (see ProjectKickoffs) rather than from here, so a project is not
"active" until the kickoff that started it says so.
"""
from django.db import transaction

from apps.projects.forms import ProjectForm
from apps.projects.models import Project
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import login_required, redirect, render
from apps.projects.views._helpers import clients, org_units


@login_required
def prj_list(request):
    qs = (Project.objects.filter(tenant=request.tenant)
          .select_related("org_unit", "client", "project_manager", "executive_sponsor"))
    return crud_list(
        request, qs, "projects/initiation/project/list.html",
        search_fields=["name", "code", "number"],
        filters=[("status", "status", False),
                 ("charter_status", "charter_status", False),
                 ("methodology", "methodology", False),
                 ("org_unit", "org_unit_id", True),
                 ("client", "client_id", True)],
        extra_context={
            "status_choices": Project.STATUS_CHOICES,
            "charter_status_choices": Project.CHARTER_STATUS_CHOICES,
            "methodology_choices": Project.METHODOLOGY_CHOICES,
            "org_units": org_units(request.tenant),
            "clients": clients(request.tenant),
        },
    )


@login_required
def prj_create(request):
    # FIRST LINE, not inside `if form.is_valid()`: a tenant-less user (User.tenant is SET_NULL,
    # so any member of a deleted tenant, not just the superuser) must never reach the form. GET
    # skips the POST branch entirely, and TenantModelForm only scopes its FK dropdowns when
    # tenant is not None — so the un-hoisted guard rendered every workspace's parties, org units,
    # documents and user emails. Same shape as apps/core/crud.py's crud_create.
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ProjectForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Project {obj.number} created.")
            return redirect("projects:prj_detail", pk=obj.pk)
    else:
        form = ProjectForm(tenant=request.tenant)
    return render(request, "projects/initiation/project/form.html",
                  {"form": form, "is_edit": False})


@login_required
def prj_detail(request, pk):
    obj = get_object_or_404(
        Project.objects.select_related(
            "org_unit", "client", "project_manager", "executive_sponsor", "request",
            "charter_document", "charter_approved_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/initiation/project/detail.html", {
        "obj": obj,
        # Capped: the register is a page, not the whole grid — the stakeholder list has its own
        # page with the influence/interest ordering.
        "stakeholders": obj.stakeholders.select_related("party", "user")[:50],
        "kickoffs": obj.kickoffs.all(),
        "source_request": obj.request,
    })


@login_required
def prj_edit(request, pk):
    # An APPROVED charter is evidence: charter_approved_by/at attest that a tenant admin approved
    # THIS text. You cannot forge that signature, but rewriting objectives / scope / dates / the
    # charter_document underneath it has the same outcome, so the edit is refused outright — the
    # peer pattern from apps/accounting/views/AccountsPayable/Bills.py's is_locked check.
    obj = get_object_or_404(Project, pk=pk, tenant=request.tenant)
    if obj.charter_status == "approved":
        messages.error(request, "An approved charter cannot be edited — the approval stamp "
                                "attests to this text.")
        return redirect("projects:prj_detail", pk=obj.pk)
    return crud_edit(
        request, model=Project, pk=pk, form_class=ProjectForm,
        template="projects/initiation/project/form.html",
        success_url="projects:prj_list",
    )


@login_required
@require_POST
def prj_delete(request, pk):
    """Delete the project and REOPEN its source request.

    ``ProjectRequest.converted_project`` is ``SET_NULL``, so a bare delete left the request
    reading "Converted" with no project — a dead state every verb then refuses (submit "already
    converted", approve "this one is converted", reject "reject the project" when the project is
    gone, return "cannot be sent back", convert "only an approved request"), making the demand
    permanently unrecoverable. Reopening it puts the demand back in the approved,
    ready-to-convert queue instead, and the two writes land together or not at all.
    """
    obj = get_object_or_404(Project, pk=pk, tenant=request.tenant)
    source = obj.request if obj.request_id and obj.request.status == "converted" else None
    with transaction.atomic():
        response = crud_delete(request, model=Project, pk=pk, success_url="projects:prj_list")
        if source is not None:
            source.status = "approved"
            source.converted_project = None
            source.save(update_fields=["status", "converted_project", "updated_at"])
            write_audit_log(request.user, source, "update",
                            changes={"verb": "reopen_on_project_delete", "from": "converted",
                                     "to": source.status})
            messages.info(
                request,
                f"Request {source.number} was reopened as approved — it can be converted again.")
    return response


# -- charter verbs -------------------------------------------------------------------------------

#: Both charter verbs gate on the PROJECT's status as well as `charter_status`: gating on the
#: charter alone let a cancelled/completed project be walked to a green "Approved" charter
#: with a fresh charter_approved_by/at stamp, while the success message claimed it "is
#: chartered" and `status` stayed cancelled.
TERMINAL_STATUSES = ("completed", "cancelled")


@login_required
@require_POST
def prj_submit_charter(request, pk):
    obj = get_object_or_404(Project, pk=pk, tenant=request.tenant)
    if obj.status in TERMINAL_STATUSES:
        messages.error(request, f"A {obj.get_status_display().lower()} project's charter cannot "
                                f"be changed.")
        return redirect("projects:prj_detail", pk=obj.pk)
    if obj.charter_status not in ("draft", "rejected"):
        messages.info(request, "That charter is already submitted or approved.")
        return redirect("projects:prj_detail", pk=obj.pk)
    obj.charter_status = "submitted"
    obj.save(update_fields=["charter_status", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "submit_charter", "from": "draft", "to": obj.charter_status})
    messages.success(request, f"Charter for “{obj.name}” submitted for approval.")
    return redirect("projects:prj_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def prj_approve_charter(request, pk):
    """Approve the charter and move the project to ``chartered``.

    Refuses to re-stamp an already-approved charter: the who/when is evidence of the decision, and
    a second click must not overwrite the first approver's name.
    """
    obj = get_object_or_404(Project, pk=pk, tenant=request.tenant)
    if obj.status in TERMINAL_STATUSES:
        messages.error(request, f"A {obj.get_status_display().lower()} project's charter cannot "
                                f"be approved.")
        return redirect("projects:prj_detail", pk=obj.pk)
    if obj.charter_status == "approved":
        messages.info(request, "That charter is already approved.")
        return redirect("projects:prj_detail", pk=obj.pk)
    if obj.charter_status != "submitted":
        messages.error(request, "Submit the charter before approving it.")
        return redirect("projects:prj_detail", pk=obj.pk)
    obj.charter_status = "approved"
    obj.charter_approved_by = request.user
    obj.charter_approved_at = timezone.now()
    if obj.status == "draft":
        obj.status = "chartered"
    obj.save(update_fields=["charter_status", "charter_approved_by", "charter_approved_at",
                            "status", "updated_at"])
    write_audit_log(request.user, obj, "approve",
                    changes={"verb": "approve_charter", "from": "submitted", "to": "approved"})
    messages.success(request, f"Charter approved — “{obj.name}” is chartered.")
    return redirect("projects:prj_detail", pk=obj.pk)
