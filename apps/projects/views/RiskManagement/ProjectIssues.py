"""Projects 7.5 — ProjectIssue views: the issue log, its CRUD and its three lifecycle verbs.

Bullet **4 Issue Logging & Escalation** is this page. The log carries the most derived lenses of the
four registers, and ``crud_list``'s ``filters`` are **field lookups only** — ``is_open`` and
``is_overdue`` are Python properties, so neither ``?escalated=1`` nor ``?overdue=1`` can be a filter
spec. Each is **pre-scoped here**, before ``crud_list`` paginates, and built out of real columns so
the database does the work.

Verbs (POST-only, GET → 405): ``escalate`` (admin-only — pushing an issue up the chain of command is
a privileged act, and it writes the ``IssueEscalation`` row the escalation register lists),
``resolve`` (capture the root cause and the resolution) and ``close`` (retire a resolved row). A
resolved or closed row is frozen evidence, so ``iss_edit``/``iss_delete`` refuse it.
"""
from django.db import transaction
from django.db.models import Q

from apps.core.crud import as_db_int
from apps.projects.forms import IssueEscalationForm, IssueResolutionForm, ProjectIssueForm
from apps.projects.models import ProjectIssue, ProjectRisk
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import get_object_or_404, login_required, redirect, render, require_POST
from apps.projects.views._helpers import owners, projects

#: The statuses an issue can still be acted on from — everything but the three terminal ones.
_LIVE_STATUSES = ("open", "in_progress", "blocked")

_LOCKED_MSG = ("A resolved or closed issue is frozen evidence and cannot be edited or deleted.")

_MAX_LEVEL = 4


@login_required
def iss_list(request):
    qs = (ProjectIssue.objects.filter(tenant=request.tenant)
          .select_related("project", "wbs_node", "risk", "owner", "raised_by", "escalated_to"))
    if request.GET.get("escalated") == "1":
        # ``escalation_level`` is a real column, but the lens is pre-scoped anyway so the queue
        # reads as one expression: any row that has ever been escalated.
        qs = qs.filter(Q(escalation_level__gt=0))
    if request.GET.get("overdue") == "1":
        # ``is_overdue`` is a property, so the lens is reconstructed from its two real columns —
        # a due date that has passed while the issue is still live.
        qs = qs.filter(Q(due_date__lt=timezone.localdate(), status__in=_LIVE_STATUSES))
    return crud_list(
        request, qs, "projects/risk/issue/list.html",
        search_fields=["number", "title", "description"],
        filters=[("project", "project_id", True),
                 ("severity", "severity", False),
                 ("status", "status", False),
                 ("issue_type", "issue_type", False),
                 ("owner", "owner_id", True),
                 ("risk", "risk_id", True)],
        extra_context={
            "projects": projects(request.tenant),
            "severity_choices": ProjectIssue.SEVERITY_CHOICES,
            "status_choices": ProjectIssue.STATUS_CHOICES,
            "issue_type_choices": ProjectIssue.ISSUE_TYPE_CHOICES,
            "owners": owners(request.tenant),
            "risks": ProjectRisk.objects.filter(tenant=request.tenant).order_by("number"),
        },
    )


@login_required
def iss_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ProjectIssueForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            if not obj.raised_by_id:
                obj.raised_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Issue {obj.number} logged.")
            return redirect("projects:iss_detail", pk=obj.pk)
    else:
        form = ProjectIssueForm(tenant=request.tenant,
                                initial={"project": as_db_int(request.GET.get("project", ""))})
    return render(request, "projects/risk/issue/form.html",
                  {"form": form, "is_edit": False})


@login_required
def iss_detail(request, pk):
    obj = get_object_or_404(
        ProjectIssue.objects.select_related(
            "project", "wbs_node", "risk", "owner", "raised_by", "escalated_to",
            "resolved_by", "created_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/risk/issue/detail.html", {
        "obj": obj,
        "escalations": obj.escalations.select_related("target_user", "escalated_by")
                        .order_by("level", "id"),
        "escalation_form": IssueEscalationForm(
            tenant=request.tenant,
            initial={"level": min(obj.escalation_level + 1, _MAX_LEVEL)}),
        "resolution_form": IssueResolutionForm(),
    })


@login_required
def iss_edit(request, pk):
    obj = get_object_or_404(ProjectIssue, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:iss_detail", pk=obj.pk)
    return crud_edit(
        request, model=ProjectIssue, pk=pk, form_class=ProjectIssueForm,
        template="projects/risk/issue/form.html", success_url="projects:iss_list")


@login_required
@require_POST
def iss_delete(request, pk):
    obj = get_object_or_404(ProjectIssue, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:iss_detail", pk=obj.pk)
    return crud_delete(request, model=ProjectIssue, pk=pk, success_url="projects:iss_list")


# -- lifecycle verbs ----------------------------------------------------------------------------

@login_required
@require_POST
@tenant_admin_required
def iss_escalate(request, pk):
    """Push the issue up one level of the chain of command. Admin-only — escalation is a privileged
    act — and the only writer of the ``IssueEscalation`` row the escalation register lists."""
    obj = get_object_or_404(ProjectIssue, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, "A resolved or closed issue cannot be escalated.")
        return redirect("projects:iss_detail", pk=obj.pk)
    if obj.escalation_level >= _MAX_LEVEL:
        messages.error(request, "This issue is already at the top escalation level.")
        return redirect("projects:iss_detail", pk=obj.pk)
    # The inline escalate form on the detail page is issue-scoped by the URL, so it does not render
    # an ``issue`` select — inject the pk into the bound data rather than loosening the form's
    # ``issue`` field to optional (a null-issue escalation row would be a real integrity hole).
    data = request.POST.copy()
    data["issue"] = obj.pk
    form = IssueEscalationForm(data, tenant=request.tenant)
    if not form.is_valid():
        first_error = next((err for errs in form.errors.values() for err in errs),
                           "Please check the escalation details.")
        messages.error(request, first_error)
        return redirect("projects:iss_detail", pk=obj.pk)
    previous = obj.status
    level = form.cleaned_data.get("level") or min(obj.escalation_level + 1, _MAX_LEVEL)
    # The escalation row and the issue's current level describe the same event, so the pair is
    # written atomically — never leave the row behind without the level it records.
    with transaction.atomic():
        row = form.save(commit=False)
        row.issue = obj
        row.escalated_by = request.user
        row.created_by = request.user
        row.tenant = request.tenant
        row.save()
        obj.escalation_level = level
        obj.escalated_to = row.target_user
        obj.escalated_at = timezone.now()
        obj.save(update_fields=["escalation_level", "escalated_to", "escalated_at", "updated_at"])
        write_audit_log(request.user, obj, "escalate",
                        changes={"verb": "escalate", "from": previous, "to": obj.status,
                                 "level": level})
    messages.success(request, f"Escalated {obj.number} to level {level}.")
    return redirect("projects:iss_detail", pk=obj.pk)


@login_required
@require_POST
def iss_resolve(request, pk):
    """Capture the root cause and the resolution, stamping ``resolved_by``/``resolved_at`` — the
    only writer of those stamps, which is why the status and the notes are off the form."""
    obj = get_object_or_404(ProjectIssue, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        if obj.status == "resolved":
            messages.info(request, "That issue is already resolved.")
        else:
            messages.error(request, "A closed issue is frozen evidence and cannot be resolved.")
        return redirect("projects:iss_detail", pk=obj.pk)
    form = IssueResolutionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Could not resolve the issue — the resolution note is required.")
        return redirect("projects:iss_detail", pk=obj.pk)
    previous = obj.status
    obj.root_cause = form.cleaned_data.get("root_cause", "").strip()
    obj.resolution_note = form.cleaned_data.get("resolution_note", "").strip()
    obj.resolved_by = request.user
    obj.resolved_at = timezone.now()
    obj.status = "resolved"
    obj.save(update_fields=["root_cause", "resolution_note", "resolved_by", "resolved_at",
                            "status", "updated_at"])
    write_audit_log(request.user, obj, "resolve",
                    changes={"verb": "resolve", "from": previous, "to": obj.status})
    messages.success(request, f"Resolved {obj.number}.")
    return redirect("projects:iss_detail", pk=obj.pk)


@login_required
@require_POST
def iss_close(request, pk):
    """Retire a resolved issue. Only a resolved row can be closed — closing an open issue would
    skip the resolution capture the log exists to keep."""
    obj = get_object_or_404(ProjectIssue, pk=pk, tenant=request.tenant)
    if obj.status != "resolved":
        messages.error(request, "Only a resolved issue can be closed.")
        return redirect("projects:iss_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "closed"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "close",
                    changes={"verb": "close", "from": previous, "to": obj.status})
    messages.success(request, f"Closed {obj.number}.")
    return redirect("projects:iss_detail", pk=obj.pk)
