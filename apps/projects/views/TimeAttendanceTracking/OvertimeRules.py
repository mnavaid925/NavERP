"""Projects 7.11 — OvertimeRule views (policies, thresholds, and multipliers)."""
from apps.projects.forms import OvertimeRuleForm
from apps.projects.models import OvertimeRule
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (
    get_object_or_404, login_required, messages, redirect, render, require_POST)
from apps.projects.views._helpers import projects


@login_required
def otr_list(request):
    qs = OvertimeRule.objects.filter(tenant=request.tenant).select_related("project")
    return crud_list(
        request, qs, "projects/timeattendance/overtimerule/list.html",
        search_fields=["number", "name", "project__name", "notes"],
        filters=[("project", "project_id", True), ("is_active", "is_active", False)],
        extra_context={
            "projects": projects(request.tenant),
        },
    )


@login_required
def otr_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = OvertimeRuleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Overtime rule {obj.name} created.")
            return redirect("projects:otr_detail", pk=obj.pk)
    else:
        form = OvertimeRuleForm(tenant=request.tenant)
    return render(request, "projects/timeattendance/overtimerule/form.html", {"form": form, "is_edit": False})


@login_required
def otr_detail(request, pk):
    obj = get_object_or_404(OvertimeRule.objects.select_related("project"), pk=pk, tenant=request.tenant)
    return render(request, "projects/timeattendance/overtimerule/detail.html", {"obj": obj})


@login_required
def otr_edit(request, pk):
    return crud_edit(
        request, model=OvertimeRule, pk=pk, form_class=OvertimeRuleForm,
        template="projects/timeattendance/overtimerule/form.html",
        success_url="projects:otr_list")


@login_required
@require_POST
def otr_delete(request, pk):
    return crud_delete(
        request, model=OvertimeRule, pk=pk,
        success_url="projects:otr_list")
