"""Projects 7.7 — Requirement views: the requirements register, its CRUD and its five verbs.

The register carries the 7.7 traceability lenses. ``crud_list``'s ``filters`` are **field lookups
only** — ``is_traced``, ``is_approved`` and ``is_verified`` are Python properties, so ``?untraced=``
/ ``?pending=`` / ``?verified=`` cannot be filter specs. Each is therefore **pre-scoped here**,
before ``crud_list`` paginates, and built out of real columns so the database does the work (the
7.5 ``rsk_list`` ruling).

Verbs (POST-only, GET → 405): ``submit`` (draft/rejected → the approval queue), ``approve`` and
``reject`` (admins — the CCB-equivalent gate for requirements), ``implement`` (approved → built) and
``verify`` (admins — implemented → verified, stamping the verification evidence). Together they are
the bullet-5 verification workflow at requirement level; the deliverable-level gate is
``ScopeVerification``.
"""
from apps.core.crud import as_db_int
from apps.projects.forms import (
    RequirementForm,
    RequirementRejectionForm,
    RequirementVerificationForm,
)
from apps.projects.models import Requirement
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (
    get_object_or_404,
    login_required,
    redirect,
    render,
    require_POST,
)
from apps.projects.views._helpers import owners, projects, requirements

_LOCKED_MSG = ("A verified requirement is frozen evidence and cannot be edited or deleted — it is "
               "the record of what was accepted.")


@login_required
def req_list(request):
    qs = (Requirement.objects.filter(tenant=request.tenant)
          .select_related("project", "parent", "wbs_node", "source_party", "owner",
                          "requested_by"))
    # Derived lenses, pre-scoped on real columns (properties are not filterable).
    if request.GET.get("untraced") == "1":
        qs = qs.filter(wbs_node__isnull=True)
    if request.GET.get("pending") == "1":
        qs = qs.filter(status__in=("draft", "submitted"))
    if request.GET.get("verified") == "1":
        qs = qs.filter(status="verified")
    return crud_list(
        request, qs, "projects/scope/requirement/list.html",
        search_fields=["number", "title", "description", "acceptance_criteria"],
        filters=[("project", "project_id", True),
                 ("requirement_type", "requirement_type", False),
                 ("elicitation_method", "elicitation_method", False),
                 ("priority", "priority", False),
                 ("status", "status", False),
                 ("owner", "owner_id", True)],
        extra_context={
            "projects": projects(request.tenant),
            "type_choices": Requirement.REQUIREMENT_TYPE_CHOICES,
            "priority_choices": Requirement.PRIORITY_CHOICES,
            "status_choices": Requirement.STATUS_CHOICES,
            "method_choices": Requirement.ELICITATION_METHOD_CHOICES,
            "owners": owners(request.tenant),
            "requirements": requirements(request.tenant),
        },
    )


@login_required
def req_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = RequirementForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            if not obj.requested_by_id:
                obj.requested_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Requirement {obj.number} logged.")
            return redirect("projects:req_detail", pk=obj.pk)
    else:
        form = RequirementForm(tenant=request.tenant,
                               initial={"project": as_db_int(request.GET.get("project", ""))})
    return render(request, "projects/scope/requirement/form.html",
                  {"form": form, "is_edit": False})


@login_required
def req_detail(request, pk):
    obj = get_object_or_404(
        Requirement.objects.select_related(
            "project", "parent", "wbs_node", "source_party", "owner", "requested_by",
            "approved_by", "verified_by", "created_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/scope/requirement/detail.html", {
        "obj": obj,
        "child_requirements": obj.children.select_related("owner").order_by("number"),
        "change_requests": (obj.change_requests.select_related("requested_by")
                            .order_by("-created_at", "-id")),
        "verifications": (obj.scope_verifications.select_related("inspected_by")
                          .order_by("-inspection_date", "-id")),
        "linked_scope_items": obj.scope_items.select_related("owner").order_by("item_type",
                                                                              "number"),
        "rejection_form": RequirementRejectionForm(),
        "verification_form": RequirementVerificationForm(),
    })


@login_required
def req_edit(request, pk):
    obj = get_object_or_404(Requirement, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:req_detail", pk=obj.pk)
    return crud_edit(
        request, model=Requirement, pk=pk, form_class=RequirementForm,
        template="projects/scope/requirement/form.html", success_url="projects:req_list")


@login_required
@require_POST
def req_delete(request, pk):
    obj = get_object_or_404(Requirement, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:req_detail", pk=obj.pk)
    return crud_delete(request, model=Requirement, pk=pk, success_url="projects:req_list")


# -- lifecycle verbs ----------------------------------------------------------------------------

@login_required
@require_POST
def req_submit(request, pk):
    """Push a draft (or a rejected requirement) onto the approval queue."""
    obj = get_object_or_404(Requirement, pk=pk, tenant=request.tenant)
    if obj.status not in ("draft", "rejected"):
        messages.error(request, "Only a draft or rejected requirement can be submitted.")
        return redirect("projects:req_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "submitted"
    obj.rejection_reason = ""
    obj.save(update_fields=["status", "rejection_reason", "updated_at"])
    write_audit_log(request.user, obj, "submit",
                    changes={"verb": "submit", "from": previous, "to": obj.status})
    messages.success(request, f"Submitted {obj.number} for approval.")
    return redirect("projects:req_detail", pk=obj.pk)


@login_required
@require_POST
@tenant_admin_required
def req_approve(request, pk):
    """Admin-only: the requirement gate. Approval stamps the approver and the instant."""
    obj = get_object_or_404(Requirement, pk=pk, tenant=request.tenant)
    if obj.status != "submitted":
        messages.error(request, "Only a submitted requirement can be approved.")
        return redirect("projects:req_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "approved"
    obj.approved_by = request.user
    obj.approved_at = timezone.now()
    obj.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    write_audit_log(request.user, obj, "approve",
                    changes={"verb": "approve", "from": previous, "to": obj.status})
    messages.success(request, f"Approved {obj.number}.")
    return redirect("projects:req_detail", pk=obj.pk)


@login_required
@require_POST
@tenant_admin_required
def req_reject(request, pk):
    """Admin-only: turn the requirement down, recording why. Voids any approval evidence."""
    obj = get_object_or_404(Requirement, pk=pk, tenant=request.tenant)
    if obj.status != "submitted":
        messages.error(request, "Only a submitted requirement can be rejected.")
        return redirect("projects:req_detail", pk=obj.pk)
    form = RequirementRejectionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "A rejection needs a written reason.")
        return redirect("projects:req_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "rejected"
    obj.rejection_reason = form.cleaned_data["reason"]
    obj.approved_by = None
    obj.approved_at = None
    obj.save(update_fields=["status", "rejection_reason", "approved_by", "approved_at",
                            "updated_at"])
    write_audit_log(request.user, obj, "reject",
                    changes={"verb": "reject", "from": previous, "to": obj.status})
    messages.success(request, f"Rejected {obj.number}.")
    return redirect("projects:req_detail", pk=obj.pk)


@login_required
@require_POST
def req_implement(request, pk):
    """Approved → implemented. The delivery claim the verification then checks."""
    obj = get_object_or_404(Requirement, pk=pk, tenant=request.tenant)
    if obj.status != "approved":
        messages.error(request, "Only an approved requirement can be marked implemented.")
        return redirect("projects:req_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "implemented"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "implement",
                    changes={"verb": "implement", "from": previous, "to": obj.status})
    messages.success(request, f"Marked {obj.number} implemented.")
    return redirect("projects:req_detail", pk=obj.pk)


@login_required
@require_POST
@tenant_admin_required
def req_verify(request, pk):
    """Admin-only: the acceptance gate. Verification freezes the row."""
    obj = get_object_or_404(Requirement, pk=pk, tenant=request.tenant)
    if obj.status != "implemented":
        messages.error(request, "Only an implemented requirement can be verified.")
        return redirect("projects:req_detail", pk=obj.pk)
    form = RequirementVerificationForm(request.POST)
    note = form.cleaned_data["note"] if form.is_valid() else ""
    previous = obj.status
    obj.status = "verified"
    obj.verification_note = note or obj.verification_note
    obj.verified_by = request.user
    obj.verified_at = timezone.now()
    obj.save(update_fields=["status", "verification_note", "verified_by", "verified_at",
                            "updated_at"])
    write_audit_log(request.user, obj, "verify",
                    changes={"verb": "verify", "from": previous, "to": obj.status})
    messages.success(request, f"Verified {obj.number}.")
    return redirect("projects:req_detail", pk=obj.pk)
