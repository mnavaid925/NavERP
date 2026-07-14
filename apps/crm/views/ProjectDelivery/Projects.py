"""CRM 1.8 Project & Delivery Management — Projects views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    CrmMilestone,
    CrmProject,
    Expense,
    Opportunity,
    Timesheet,
)
from apps.crm.forms import (
    CrmProjectForm,
)


# ------------------------------------------------------------ 1.8 Projects
@login_required
def crmproject_list(request):
    # Annotate milestone counts so the progress bar (progress_pct) doesn't query per row.
    qs = (CrmProject.objects.filter(tenant=request.tenant)
          .select_related("account", "owner", "source_opportunity")
          .annotate(ms_total=Count("milestones"),
                    ms_done=Count("milestones", filter=Q(milestones__status="completed")))
          .order_by("-created_at"))  # explicit: annotate()+GROUP BY drops the Meta default ordering
    return crud_list(
        request, qs,
        "crm/projects/crmproject/list.html",
        search_fields=["number", "name", "account__name"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": CrmProject.STATUS_CHOICES},
    )


@login_required
def crmproject_create(request):
    return crud_create(request, form_class=CrmProjectForm, template="crm/projects/crmproject/form.html",
                       success_url="crm:crmproject_list")


@login_required
def crmproject_detail(request, pk):
    obj = get_object_or_404(
        CrmProject.objects.select_related("account", "owner", "source_opportunity"),
        pk=pk, tenant=request.tenant)
    timesheets = Timesheet.objects.filter(tenant=request.tenant, project=obj)
    hours = timesheets.aggregate(total=Sum("hours"),
                                 billable=Sum("hours", filter=Q(is_billable=True)))
    expense_total = Expense.objects.filter(
        tenant=request.tenant, project=obj, status="approved").aggregate(t=Sum("amount"))["t"] or 0
    return render(request, "crm/projects/crmproject/detail.html", {
        "obj": obj,
        "milestones": obj.milestones.filter(tenant=request.tenant).select_related("assignee"),
        "total_hours": hours["total"] or 0,
        "billable_hours": hours["billable"] or 0,
        "expense_total": expense_total,
    })


@login_required
def crmproject_edit(request, pk):
    return crud_edit(request, model=CrmProject, pk=pk, form_class=CrmProjectForm,
                     template="crm/projects/crmproject/form.html", success_url="crm:crmproject_list")


@login_required
@require_POST
def crmproject_delete(request, pk):
    return crud_delete(request, model=CrmProject, pk=pk, success_url="crm:crmproject_list")


@login_required
@require_POST
def opportunity_to_project(request, pk):
    """1.8: convert a won Opportunity into a delivery Project (idempotent)."""
    opp = get_object_or_404(Opportunity, pk=pk, tenant=request.tenant)
    if opp.stage != "closed_won":
        messages.error(request, "Only won opportunities can be converted to a project.")
        return redirect("crm:opportunity_detail", pk=opp.pk)
    existing = CrmProject.objects.filter(tenant=request.tenant, source_opportunity=opp).first()
    if existing:
        messages.info(request, f"Project {existing.number} already exists for this opportunity.")
        return redirect("crm:crmproject_detail", pk=existing.pk)
    project = CrmProject.objects.create(
        tenant=request.tenant, name=f"{opp.name} — Delivery", account=opp.account,
        source_opportunity=opp, status="planning", budget=opp.amount, owner=opp.owner,
        description=f"Auto-created from won opportunity {opp.number}.")
    write_audit_log(request.user, project, "create", {"from_opportunity": opp.number})
    messages.success(request, f"Project {project.number} created from {opp.number}.")
    return redirect("crm:crmproject_detail", pk=project.pk)


@login_required
def crmproject_board(request):
    """1.8 Projects — Kanban board: milestones grouped into status columns (optional ?project=)."""
    projects = list(CrmProject.objects.filter(tenant=request.tenant).order_by("name"))
    qs = CrmMilestone.objects.filter(tenant=request.tenant).select_related("project", "assignee")
    project_id = request.GET.get("project", "").strip()
    selected_project = None
    if project_id.isdigit():
        pid = int(project_id)
        qs = qs.filter(project_id=pid)
        selected_project = next((p for p in projects if p.pk == pid), None)  # scan the list — no 2nd query
    ms_list = list(qs)  # evaluate once; bucket per column in Python (no re-query)
    columns = [{"value": v, "label": label, "cards": [m for m in ms_list if m.status == v]}
               for v, label in CrmMilestone.STATUS_CHOICES]
    return render(request, "crm/projects/board.html", {
        "columns": columns, "projects": projects, "selected_project": selected_project,
        "status_choices": CrmMilestone.STATUS_CHOICES,
    })
