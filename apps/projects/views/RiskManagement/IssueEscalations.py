"""Projects 7.5 — IssueEscalation views: the escalation register and its CRUD.

Bullet **4 Issue Logging & Escalation** lists this register. An escalation has no lifecycle of its
own, so this module is plain CRUD — the rows are appended by ``iss_escalate`` on the issue detail
page and by ``esc_create`` here; neither ``esc_edit`` nor ``esc_delete`` has a lock to honour, so
``esc_delete`` is the only view that needs ``@require_POST``.

``crud_list``'s ``filters`` are field lookups only, so the level filter reads the real ``level``
column (``is_int``) and the issue/user filters hop to their ``_id`` columns. The register's level
vocabulary is the model's own ``LEVEL_CHOICES`` constant — one definition shared by the filter, the
form and ``iss_escalate``.

**Writing this register is an admin act**, exactly like ``iss_escalate``: the row records who was
told about an issue and why, so forging, rewriting or deleting it defeats the gate on the verb.
``esc_create``/``esc_edit``/``esc_delete`` therefore carry ``@tenant_admin_required``; the list and
detail pages stay readable by every member.
"""
from apps.core.crud import as_db_int
from apps.projects.forms import IssueEscalationForm
from apps.projects.models import IssueEscalation, ProjectIssue
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import get_object_or_404, login_required, redirect, render, require_POST
from apps.projects.views._helpers import owners


@login_required
def esc_list(request):
    qs = (IssueEscalation.objects.filter(tenant=request.tenant)
          .select_related("issue", "issue__project", "target_user", "escalated_by"))
    return crud_list(
        request, qs, "projects/risk/escalation/list.html",
        search_fields=["number", "target_role", "reason", "outcome"],
        filters=[("issue", "issue_id", True),
                 ("level", "level", True),
                 ("target_user", "target_user_id", True)],
        extra_context={
            "issues": ProjectIssue.objects.filter(tenant=request.tenant).order_by("number"),
            "level_choices": IssueEscalation.LEVEL_CHOICES,
            "owners": owners(request.tenant),
        },
    )


@login_required
@tenant_admin_required
def esc_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = IssueEscalationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            if not obj.escalated_by_id:
                obj.escalated_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Escalation {obj.number} recorded.")
            return redirect("projects:esc_detail", pk=obj.pk)
    else:
        form = IssueEscalationForm(tenant=request.tenant,
                                   initial={"issue": as_db_int(request.GET.get("issue", ""))})
    return render(request, "projects/risk/escalation/form.html",
                  {"form": form, "is_edit": False})


@login_required
def esc_detail(request, pk):
    obj = get_object_or_404(
        IssueEscalation.objects.select_related(
            "issue", "issue__project", "target_user", "escalated_by", "created_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/risk/escalation/detail.html", {"obj": obj})


@login_required
@tenant_admin_required
def esc_edit(request, pk):
    return crud_edit(
        request, model=IssueEscalation, pk=pk, form_class=IssueEscalationForm,
        template="projects/risk/escalation/form.html", success_url="projects:esc_list")


@login_required
@tenant_admin_required
@require_POST
def esc_delete(request, pk):
    return crud_delete(request, model=IssueEscalation, pk=pk, success_url="projects:esc_list")
