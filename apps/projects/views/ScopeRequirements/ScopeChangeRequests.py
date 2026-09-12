"""Projects 7.7 — ScopeChangeRequest views: the CCB register, its CRUD and its five verbs.

``crud_list``'s ``filters`` are field lookups only, so the two derived lenses are **pre-scoped
here**: ``?pending=1`` (still in front of the board) and ``?high_impact=1`` (the material changes —
the documented thresholds are read straight off the model's constants, so the lens and
``is_high_impact`` cannot drift apart).

Verbs (POST-only, GET → 405): ``submit`` (draft → the board's queue), ``review``, ``approve`` and
``reject`` (admins — the CCB's decision, which stamps ``decided_by``/``decided_at``) and
``implement`` (approved → landed). The reject verb binds ``ChangeRejectionForm`` because a rejection
without a written reason is not actionable.
"""
from django.db.models import Q

from apps.core.crud import as_db_int
from apps.projects.forms import ChangeRejectionForm, ScopeChangeForm
from apps.projects.models import ScopeChangeRequest
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (
    get_object_or_404,
    login_required,
    redirect,
    render,
    require_POST,
)
from apps.projects.views._helpers import owners, projects, requirements

_LOCKED_MSG = ("An implemented change request is frozen evidence and cannot be edited or deleted.")
#: The statuses the CCB can still decide on.
_DECIDABLE = ("submitted", "under_review")


@login_required
def scr_list(request):
    qs = (ScopeChangeRequest.objects.filter(tenant=request.tenant)
          .select_related("project", "requirement", "risk", "requested_by", "decided_by"))
    if request.GET.get("pending") == "1":
        qs = qs.filter(status__in=("draft", "submitted", "under_review"))
    if request.GET.get("high_impact") == "1":
        # Read the thresholds off the model so this lens cannot drift from ``is_high_impact``.
        qs = qs.filter(
            Q(cost_impact__gte=ScopeChangeRequest.HIGH_COST)
            | Q(schedule_impact_days__gte=ScopeChangeRequest.HIGH_SCHEDULE_DAYS)
            | Q(quality_impact="high"))
    return crud_list(
        request, qs, "projects/scope/scopechange/list.html",
        search_fields=["number", "title", "description", "justification"],
        filters=[("project", "project_id", True),
                 ("status", "status", False),
                 ("priority", "priority", False),
                 ("source", "source", False),
                 ("requirement", "requirement_id", True)],
        extra_context={
            "projects": projects(request.tenant),
            "status_choices": ScopeChangeRequest.STATUS_CHOICES,
            "priority_choices": ScopeChangeRequest.PRIORITY_CHOICES,
            "source_choices": ScopeChangeRequest.SOURCE_CHOICES,
            "requirements": requirements(request.tenant),
            "owners": owners(request.tenant),
        },
    )


@login_required
def scr_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ScopeChangeForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            if not obj.requested_by_id:
                obj.requested_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Change request {obj.number} raised.")
            return redirect("projects:scr_detail", pk=obj.pk)
    else:
        form = ScopeChangeForm(tenant=request.tenant,
                               initial={"project": as_db_int(request.GET.get("project", ""))})
    return render(request, "projects/scope/scopechange/form.html",
                  {"form": form, "is_edit": False})


@login_required
def scr_detail(request, pk):
    obj = get_object_or_404(
        ScopeChangeRequest.objects.select_related(
            "project", "requirement", "risk", "requested_by", "decided_by", "created_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/scope/scopechange/detail.html", {
        "obj": obj,
        "decision_form": ChangeRejectionForm(),
    })


@login_required
def scr_edit(request, pk):
    obj = get_object_or_404(ScopeChangeRequest, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:scr_detail", pk=obj.pk)
    return crud_edit(
        request, model=ScopeChangeRequest, pk=pk, form_class=ScopeChangeForm,
        template="projects/scope/scopechange/form.html", success_url="projects:scr_list")


@login_required
@require_POST
def scr_delete(request, pk):
    obj = get_object_or_404(ScopeChangeRequest, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:scr_detail", pk=obj.pk)
    return crud_delete(request, model=ScopeChangeRequest, pk=pk, success_url="projects:scr_list")


# -- CCB lifecycle verbs ------------------------------------------------------------------------

@login_required
@require_POST
def scr_submit(request, pk):
    """Push a draft onto the board's queue."""
    obj = get_object_or_404(ScopeChangeRequest, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request, "Only a draft change request can be submitted.")
        return redirect("projects:scr_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "submitted"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "submit",
                    changes={"verb": "submit", "from": previous, "to": obj.status})
    messages.success(request, f"Submitted {obj.number} to the change control board.")
    return redirect("projects:scr_detail", pk=obj.pk)


@login_required
@require_POST
@tenant_admin_required
def scr_review(request, pk):
    """Admin-only: the board has taken the change under review."""
    obj = get_object_or_404(ScopeChangeRequest, pk=pk, tenant=request.tenant)
    if obj.status != "submitted":
        messages.error(request, "Only a submitted change request can be taken under review.")
        return redirect("projects:scr_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "under_review"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "review",
                    changes={"verb": "review", "from": previous, "to": obj.status})
    messages.success(request, f"{obj.number} is under review.")
    return redirect("projects:scr_detail", pk=obj.pk)


@login_required
@require_POST
@tenant_admin_required
def scr_approve(request, pk):
    """Admin-only: the board approves the change, stamping the decision evidence."""
    obj = get_object_or_404(ScopeChangeRequest, pk=pk, tenant=request.tenant)
    if obj.status not in _DECIDABLE:
        messages.error(request, "Only a submitted or under-review change can be approved.")
        return redirect("projects:scr_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "approved"
    obj.decided_by = request.user
    obj.decided_at = timezone.now()
    obj.save(update_fields=["status", "decided_by", "decided_at", "updated_at"])
    write_audit_log(request.user, obj, "approve",
                    changes={"verb": "approve", "from": previous, "to": obj.status})
    messages.success(request, f"Approved {obj.number}.")
    return redirect("projects:scr_detail", pk=obj.pk)


@login_required
@require_POST
@tenant_admin_required
def scr_reject(request, pk):
    """Admin-only: the board turns the change down, recording why."""
    obj = get_object_or_404(ScopeChangeRequest, pk=pk, tenant=request.tenant)
    if obj.status not in _DECIDABLE:
        messages.error(request, "Only a submitted or under-review change can be rejected.")
        return redirect("projects:scr_detail", pk=obj.pk)
    form = ChangeRejectionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "A rejection needs a written reason.")
        return redirect("projects:scr_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "rejected"
    obj.decision_note = form.cleaned_data["decision_note"]
    obj.decided_by = request.user
    obj.decided_at = timezone.now()
    obj.save(update_fields=["status", "decision_note", "decided_by", "decided_at", "updated_at"])
    write_audit_log(request.user, obj, "reject",
                    changes={"verb": "reject", "from": previous, "to": obj.status})
    messages.success(request, f"Rejected {obj.number}.")
    return redirect("projects:scr_detail", pk=obj.pk)


@login_required
@require_POST
def scr_implement(request, pk):
    """Approved → implemented: the change has actually landed in the project."""
    obj = get_object_or_404(ScopeChangeRequest, pk=pk, tenant=request.tenant)
    if obj.status != "approved":
        messages.error(request, "Only an approved change request can be implemented.")
        return redirect("projects:scr_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "implemented"
    obj.implemented_at = timezone.now()
    obj.save(update_fields=["status", "implemented_at", "updated_at"])
    write_audit_log(request.user, obj, "implement",
                    changes={"verb": "implement", "from": previous, "to": obj.status})
    messages.success(request, f"Marked {obj.number} implemented.")
    return redirect("projects:scr_detail", pk=obj.pk)
