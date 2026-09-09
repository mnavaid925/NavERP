"""Projects 7.2 — ProjectMilestone views.

``mst_achieve`` is the gate decision (bullet 4's stage-gate governance): it is POST-only and
tenant-admin gated — a gate is a governance state, and every 7.1 verb that moves governance
state (approve charter, convert request) is gated the same way. The stamp itself is written by
``save()``; the verb only sets the status.
"""
from apps.projects.forms import MilestoneForm
from apps.projects.models import ProjectMilestone
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import get_object_or_404, login_required, redirect, render, require_POST
from apps.projects.views._helpers import projects


@login_required
def mst_list(request):
    qs = (ProjectMilestone.objects.filter(tenant=request.tenant)
          .select_related("project"))
    return crud_list(
        request, qs, "projects/planning/milestone/list.html",
        search_fields=["name", "number", "description"],
        filters=[("project", "project_id", True),
                 ("status", "status", False),
                 ("is_phase_gate", "is_phase_gate", False)],
        extra_context={
            "status_choices": ProjectMilestone.STATUS_CHOICES,
            "projects": projects(request.tenant),
        },
    )


@login_required
def mst_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = MilestoneForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Milestone {obj.number} created.")
            return redirect("projects:mst_detail", pk=obj.pk)
    else:
        form = MilestoneForm(tenant=request.tenant,
                             initial={"project": request.GET.get("project", "")})
    return render(request, "projects/planning/milestone/form.html",
                  {"form": form, "is_edit": False})


@login_required
def mst_detail(request, pk):
    obj = get_object_or_404(
        ProjectMilestone.objects.select_related("project", "anchor_task"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/planning/milestone/detail.html", {"obj": obj})


@login_required
def mst_edit(request, pk):
    return crud_edit(
        request, model=ProjectMilestone, pk=pk, form_class=MilestoneForm,
        template="projects/planning/milestone/form.html", success_url="projects:mst_list")


@login_required
@require_POST
def mst_delete(request, pk):
    return crud_delete(request, model=ProjectMilestone, pk=pk,
                       success_url="projects:mst_list")


@login_required
@tenant_admin_required
@require_POST
def mst_achieve(request, pk):
    obj = get_object_or_404(ProjectMilestone, pk=pk, tenant=request.tenant)
    if obj.status == "achieved":
        messages.info(request, "That milestone is already achieved.")
        return redirect("projects:mst_detail", pk=obj.pk)
    if obj.status == "cancelled":
        messages.error(request, "A cancelled milestone cannot be achieved.")
        return redirect("projects:mst_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "achieved"
    obj.save(update_fields=["status", "actual_date", "updated_at"])
    write_audit_log(request.user, obj, "achieve",
                    changes={"verb": "achieve", "from": previous, "to": obj.status})
    messages.success(request, f"Milestone {obj.number} achieved.")
    return redirect("projects:mst_detail", pk=obj.pk)
