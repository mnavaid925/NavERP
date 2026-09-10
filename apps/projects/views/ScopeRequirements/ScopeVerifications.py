"""Projects 7.7 — ScopeVerification views: the deliverable inspection log and its acceptance verbs.

``crud_list``'s ``filters`` are field lookups only, so ``?pending=1`` (the acceptance queue) is
**pre-scoped here** on the real ``acceptance_status`` column.

Verbs (POST-only, GET → 405): ``accept`` (any member — the deliverable cleared the gate),
``reject`` and ``waive`` (admins). All three bind ``VerificationDecisionForm``; ``reject``
additionally refuses a blank note, because a rejection without a written reason is not actionable.
Each decision stamps ``accepted_by``/``accepted_at`` in the same request, so the gate keeps its
evidence.
"""
from apps.core.crud import as_db_int
from apps.projects.forms import ScopeVerificationForm, VerificationDecisionForm
from apps.projects.models import ScopeVerification
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (
    get_object_or_404,
    login_required,
    redirect,
    render,
    require_POST,
)
from apps.projects.views._helpers import owners, projects, requirements

_LOCKED_MSG = ("A decided inspection is frozen evidence and cannot be edited or deleted.")


@login_required
def svr_list(request):
    qs = (ScopeVerification.objects.filter(tenant=request.tenant)
          .select_related("project", "wbs_node", "requirement", "inspected_by", "accepted_by"))
    if request.GET.get("pending") == "1":
        qs = qs.filter(acceptance_status="pending")
    return crud_list(
        request, qs, "projects/scope/scopeverification/list.html",
        search_fields=["number", "deliverable", "findings", "decision_note"],
        filters=[("project", "project_id", True),
                 ("acceptance_status", "acceptance_status", False),
                 ("result", "result", False),
                 ("method", "method", False),
                 ("requirement", "requirement_id", True)],
        extra_context={
            "projects": projects(request.tenant),
            "method_choices": ScopeVerification.METHOD_CHOICES,
            "result_choices": ScopeVerification.RESULT_CHOICES,
            "status_choices": ScopeVerification.ACCEPTANCE_STATUS_CHOICES,
            "requirements": requirements(request.tenant),
            "owners": owners(request.tenant),
        },
    )


@login_required
def svr_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ScopeVerificationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            if not obj.inspected_by_id:
                obj.inspected_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Inspection {obj.number} recorded.")
            return redirect("projects:svr_detail", pk=obj.pk)
    else:
        form = ScopeVerificationForm(
            tenant=request.tenant,
            initial={"project": as_db_int(request.GET.get("project", ""))})
    return render(request, "projects/scope/scopeverification/form.html",
                  {"form": form, "is_edit": False})


@login_required
def svr_detail(request, pk):
    obj = get_object_or_404(
        ScopeVerification.objects.select_related(
            "project", "wbs_node", "requirement", "inspected_by", "accepted_by", "created_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/scope/scopeverification/detail.html", {
        "obj": obj,
        "decision_form": VerificationDecisionForm(),
    })


@login_required
def svr_edit(request, pk):
    obj = get_object_or_404(ScopeVerification, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:svr_detail", pk=obj.pk)
    return crud_edit(
        request, model=ScopeVerification, pk=pk, form_class=ScopeVerificationForm,
        template="projects/scope/scopeverification/form.html", success_url="projects:svr_list")


@login_required
@require_POST
def svr_delete(request, pk):
    obj = get_object_or_404(ScopeVerification, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:svr_detail", pk=obj.pk)
    return crud_delete(request, model=ScopeVerification, pk=pk, success_url="projects:svr_list")


# -- acceptance verbs ---------------------------------------------------------------------------

@login_required
@require_POST
def svr_accept(request, pk):
    """The customer accepted the deliverable. Any member may record the acceptance."""
    obj = get_object_or_404(ScopeVerification, pk=pk, tenant=request.tenant)
    if obj.is_decided:
        messages.info(request, "That inspection has already been decided.")
        return redirect("projects:svr_detail", pk=obj.pk)
    form = VerificationDecisionForm(request.POST)
    note = form.cleaned_data["note"] if form.is_valid() else ""
    previous = obj.acceptance_status
    obj.acceptance_status = "accepted"
    obj.decision_note = note or obj.decision_note
    obj.accepted_by = request.user
    obj.accepted_at = timezone.now()
    obj.save(update_fields=["acceptance_status", "decision_note", "accepted_by", "accepted_at",
                            "updated_at"])
    write_audit_log(request.user, obj, "accept",
                    changes={"verb": "accept", "from": previous, "to": obj.acceptance_status})
    messages.success(request, f"Accepted {obj.number}.")
    return redirect("projects:svr_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def svr_reject(request, pk):
    """Admin-only: the deliverable is refused — and the reason is mandatory."""
    obj = get_object_or_404(ScopeVerification, pk=pk, tenant=request.tenant)
    if obj.is_decided:
        messages.error(request, "That inspection has already been decided.")
        return redirect("projects:svr_detail", pk=obj.pk)
    form = VerificationDecisionForm(request.POST)
    if not form.is_valid() or not form.cleaned_data.get("note", "").strip():
        messages.error(request, "A rejection needs a written reason.")
        return redirect("projects:svr_detail", pk=obj.pk)
    previous = obj.acceptance_status
    obj.acceptance_status = "rejected"
    obj.decision_note = form.cleaned_data["note"].strip()
    obj.accepted_by = request.user
    obj.accepted_at = timezone.now()
    obj.save(update_fields=["acceptance_status", "decision_note", "accepted_by", "accepted_at",
                            "updated_at"])
    write_audit_log(request.user, obj, "reject",
                    changes={"verb": "reject", "from": previous, "to": obj.acceptance_status})
    messages.success(request, f"Rejected {obj.number}.")
    return redirect("projects:svr_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def svr_waive(request, pk):
    """Admin-only: the gate is formally waived — recorded, not silently skipped."""
    obj = get_object_or_404(ScopeVerification, pk=pk, tenant=request.tenant)
    if obj.is_decided:
        messages.error(request, "That inspection has already been decided.")
        return redirect("projects:svr_detail", pk=obj.pk)
    previous = obj.acceptance_status
    obj.acceptance_status = "waived"
    obj.accepted_by = request.user
    obj.accepted_at = timezone.now()
    obj.save(update_fields=["acceptance_status", "accepted_by", "accepted_at", "updated_at"])
    write_audit_log(request.user, obj, "waive",
                    changes={"verb": "waive", "from": previous, "to": obj.acceptance_status})
    messages.success(request, f"Waived the acceptance gate on {obj.number}.")
    return redirect("projects:svr_detail", pk=obj.pk)
