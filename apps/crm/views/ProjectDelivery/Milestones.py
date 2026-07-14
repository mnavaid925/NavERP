"""CRM 1.8 Project & Delivery Management — Milestones views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    CrmMilestone,
    CrmProject,
)
from apps.crm.forms import (
    CrmMilestoneForm,
)


# ------------------------------------------------------------ 1.8 Milestones
@login_required
def crmmilestone_list(request):
    return crud_list(
        request,
        CrmMilestone.objects.filter(tenant=request.tenant).select_related("project", "assignee"),
        "crm/projects/crmmilestone/list.html",
        search_fields=["number", "title"],
        filters=[("status", "status", False), ("project", "project_id", True)],
        extra_context={"status_choices": CrmMilestone.STATUS_CHOICES,
                       "kind_choices": CrmMilestone.KIND_CHOICES,
                       "projects": CrmProject.objects.filter(tenant=request.tenant).order_by("name")},
    )


@login_required
def crmmilestone_create(request):
    return crud_create(request, form_class=CrmMilestoneForm, template="crm/projects/crmmilestone/form.html",
                       success_url="crm:crmmilestone_list")


@login_required
def crmmilestone_detail(request, pk):
    obj = get_object_or_404(
        CrmMilestone.objects.select_related("project", "assignee", "parent"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/projects/crmmilestone/detail.html", {
        "obj": obj,
        "subtasks": CrmMilestone.objects.filter(tenant=request.tenant, parent=obj).select_related("assignee"),
    })


@login_required
def crmmilestone_edit(request, pk):
    return crud_edit(request, model=CrmMilestone, pk=pk, form_class=CrmMilestoneForm,
                     template="crm/projects/crmmilestone/form.html", success_url="crm:crmmilestone_list")


@login_required
@require_POST
def crmmilestone_delete(request, pk):
    return crud_delete(request, model=CrmMilestone, pk=pk, success_url="crm:crmmilestone_list")


@login_required
@require_POST
def crmmilestone_move(request, pk):
    """1.8 Kanban — move a milestone to a new status from the board (save() stamps completed_at)."""
    obj = get_object_or_404(CrmMilestone, pk=pk, tenant=request.tenant)
    new_status = request.POST.get("status", "")
    if new_status in {v for v, _ in CrmMilestone.STATUS_CHOICES} and new_status != obj.status:
        obj.status = new_status
        obj.save()
        write_audit_log(request.user, obj, "update", {"action": "move", "status": new_status})
        messages.success(request, f"{obj.number} → {obj.get_status_display()}.")
    url = reverse("crm:crmproject_board")
    proj = request.POST.get("project", "")
    return redirect(f"{url}?project={proj}" if proj.isdigit() else url)
