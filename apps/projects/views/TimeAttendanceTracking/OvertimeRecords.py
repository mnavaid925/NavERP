"""Projects 7.11 — ProjectOvertimeRecord views (logging, approvals, client billing splits)."""
from apps.projects.forms import ProjectOvertimeRecordForm
from apps.projects.models import ProjectOvertimeRecord
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (
    get_object_or_404, login_required, messages, redirect, render, require_POST, timezone)
from apps.projects.views._helpers import projects, resource_profiles


@login_required
def pot_list(request):
    qs = (ProjectOvertimeRecord.objects.filter(tenant=request.tenant)
          .select_related("resource__employee__party", "resource__party", "project", "project_task"))
    return crud_list(
        request, qs, "projects/timeattendance/overtimerecord/list.html",
        search_fields=["number", "resource__employee__party__name", "resource__party__name",
                       "project__name", "notes"],
        filters=[("status", "status", False),
                 ("project", "project_id", True),
                 ("resource", "resource_id", True),
                 ("overtime_type", "overtime_type", False),
                 ("billable", "is_billable", False)],
        extra_context={
            "status_choices": ProjectOvertimeRecord.STATUS_CHOICES,
            "overtime_type_choices": ProjectOvertimeRecord.OVERTIME_TYPE_CHOICES,
            "resources": resource_profiles(request.tenant),
            "projects": projects(request.tenant),
        },
    )


@login_required
def pot_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ProjectOvertimeRecordForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Overtime record {obj.number} created.")
            return redirect("projects:pot_detail", pk=obj.pk)
    else:
        initial = {
            "resource": request.GET.get("resource", ""),
            "project": request.GET.get("project", ""),
            "date": timezone.localdate(),
        }
        form = ProjectOvertimeRecordForm(tenant=request.tenant, initial=initial)
    return render(request, "projects/timeattendance/overtimerecord/form.html", {"form": form, "is_edit": False})


@login_required
def pot_detail(request, pk):
    obj = get_object_or_404(
        ProjectOvertimeRecord.objects.select_related(
            "resource__employee__party", "resource__party", "project", "project_task", "time_entry", "approved_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/timeattendance/overtimerecord/detail.html", {"obj": obj})


@login_required
def pot_edit(request, pk):
    obj = get_object_or_404(ProjectOvertimeRecord, pk=pk, tenant=request.tenant)
    if obj.status in ("approved", "rejected"):
        messages.error(request, "An approved or rejected overtime record is locked — it cannot be edited.")
        return redirect("projects:pot_detail", pk=obj.pk)
    return crud_edit(
        request, model=ProjectOvertimeRecord, pk=pk, form_class=ProjectOvertimeRecordForm,
        template="projects/timeattendance/overtimerecord/form.html",
        success_url="projects:pot_list")


@login_required
@require_POST
def pot_delete(request, pk):
    obj = get_object_or_404(ProjectOvertimeRecord, pk=pk, tenant=request.tenant)
    if obj.status in ("approved", "rejected"):
        messages.error(request, "An approved or rejected overtime record is locked — it cannot be deleted.")
        return redirect("projects:pot_detail", pk=obj.pk)
    return crud_delete(request, model=ProjectOvertimeRecord, pk=pk, success_url="projects:pot_list")


@login_required
@require_POST
def pot_submit(request, pk):
    obj = get_object_or_404(ProjectOvertimeRecord, pk=pk, tenant=request.tenant)
    if obj.status == "submitted":
        messages.info(request, "That record is already awaiting approval.")
        return redirect("projects:pot_detail", pk=obj.pk)
    if obj.status in ("approved", "rejected"):
        messages.error(request, "An approved or rejected record cannot be submitted.")
        return redirect("projects:pot_detail", pk=obj.pk)
    obj.status = "submitted"
    obj.submitted_at = timezone.now()
    obj.save(update_fields=["status", "submitted_at", "updated_at"])
    write_audit_log(request.user, obj, "submit", changes={"verb": "submit"})
    messages.success(request, f"Overtime record {obj.number} submitted for approval.")
    return redirect("projects:pot_detail", pk=obj.pk)


@login_required
@require_POST
@tenant_admin_required
def pot_approve(request, pk):
    obj = get_object_or_404(ProjectOvertimeRecord, pk=pk, tenant=request.tenant)
    if obj.status != "submitted":
        messages.error(request, f"Only a submitted record can be approved — this one is {obj.get_status_display().lower()}.")
        return redirect("projects:pot_detail", pk=obj.pk)
    obj.status = "approved"
    obj.approved_by = request.user
    obj.approved_at = timezone.now()
    obj.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    write_audit_log(request.user, obj, "approve", changes={"verb": "approve"})
    messages.success(request, f"Overtime record {obj.number} approved.")
    return redirect("projects:pot_detail", pk=obj.pk)


@login_required
@require_POST
@tenant_admin_required
def pot_reject(request, pk):
    obj = get_object_or_404(ProjectOvertimeRecord, pk=pk, tenant=request.tenant)
    if obj.status != "submitted":
        messages.error(request, f"Only a submitted record can be rejected — this one is {obj.get_status_display().lower()}.")
        return redirect("projects:pot_detail", pk=obj.pk)
    obj.status = "rejected"
    obj.approved_by = request.user
    obj.approved_at = timezone.now()
    obj.decision_note = request.POST.get("reason", "").strip()
    obj.save(update_fields=["status", "approved_by", "approved_at", "decision_note", "updated_at"])
    write_audit_log(request.user, obj, "reject", changes={"verb": "reject", "reason": obj.decision_note})
    messages.success(request, f"Overtime record {obj.number} rejected.")
    return redirect("projects:pot_detail", pk=obj.pk)
