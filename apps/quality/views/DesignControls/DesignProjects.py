import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.quality.forms.DesignControls.DesignProjects import DesignProjectForm
from apps.quality.models.DesignControls.DesignProjects import DesignProject
from apps.quality.views._common import quality_object, quality_scope


def csv_safe(value):
    if value is None:
        return ""
    text = str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


@login_required
def design_project_list(request):
    qs = quality_scope(DesignProject.objects.all(), request).select_related("project_lead", "quality_lead", "department")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q) | Q(title__icontains=q) | Q(device_name__icontains=q)
        )

    selected_class = request.GET.get("device_class", "").strip()
    if selected_class:
        qs = qs.filter(device_class=selected_class)

    selected_phase = request.GET.get("phase", "").strip()
    if selected_phase:
        qs = qs.filter(current_phase=selected_phase)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    stats = quality_scope(DesignProject.objects.all(), request).aggregate(
        total_count=Count("id"),
        active_count=Count("id", filter=Q(status__in=["active", "gate_review"])),
        locked_count=Count("id", filter=Q(dhf_locked=True)),
    )
    total_count = stats["total_count"]
    active_count = stats["active_count"]
    locked_count = stats["locked_count"]

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    projects = paginator.get_page(page_number)

    return render(
        request,
        "quality/designcontrols/design_project/list.html",
        {
            "projects": projects,
            "device_class_choices": DesignProject.DEVICE_CLASS_CHOICES,
            "phase_choices": DesignProject.CURRENT_PHASE_CHOICES,
            "status_choices": DesignProject.STATUS_CHOICES,
            "total_count": total_count,
            "active_count": active_count,
            "locked_count": locked_count,
            "q": q,
            "selected_class": selected_class,
            "selected_phase": selected_phase,
            "selected_status": selected_status,
        },
    )


@login_required
def design_project_export(request):
    qs = quality_scope(DesignProject.objects.all(), request).select_related("project_lead", "quality_lead", "department")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="design_projects.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Number", "Title", "Device Name", "Device Class", "Regulatory Pathway",
        "Phase", "Status", "Project Lead", "Quality Lead", "Department", "DHF Locked"
    ])
    for p in qs.iterator(chunk_size=500):
        writer.writerow([
            csv_safe(p.number),
            csv_safe(p.title),
            csv_safe(p.device_name),
            csv_safe(p.get_device_class_display()),
            csv_safe(p.get_regulatory_pathway_display()),
            csv_safe(p.get_current_phase_display()),
            csv_safe(p.get_status_display()),
            csv_safe(p.project_lead.get_full_name() or p.project_lead.username if p.project_lead else ""),
            csv_safe(p.quality_lead.get_full_name() or p.quality_lead.username if p.quality_lead else ""),
            csv_safe(p.department.name if p.department else ""),
            csv_safe("Yes" if p.dhf_locked else "No"),
        ])
    return response


@login_required
def design_project_create(request):
    if request.method == "POST":
        form = DesignProjectForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            project = form.save(commit=False)
            project.tenant = request.tenant
            project.save()
            write_audit_log(request.user, project, "create", tenant=request.tenant)
            messages.success(request, f"Design project {project.number} initialized successfully.")
            return redirect("quality:design_project_detail", pk=project.pk)
    else:
        form = DesignProjectForm(tenant=request.tenant)

    return render(
        request,
        "quality/designcontrols/design_project/form.html",
        {"form": form, "title": "New Design Project / DHF Plan", "action": "Create"},
    )


@login_required
def design_project_detail(request, pk):
    project = quality_object(
        request,
        DesignProject,
        pk,
        select_related=["project_lead", "quality_lead", "department"],
    )

    inputs = project.inputs.all().select_related("owner", "user_need_parent", "controlled_document")[:20]
    reviews = project.reviews.all().select_related("lead_reviewer", "independent_reviewer", "electronic_signature")[:10]
    verifications = project.verifications.all().select_related("primary_input", "executed_by", "protocol_document", "report_document")[:20]

    input_stats = project.inputs.aggregate(
        total=Count("id"),
        verified=Count("id", filter=Q(status="verified")),
        approved=Count("id", filter=Q(status="approved")),
    )
    review_stats = project.reviews.aggregate(
        total=Count("id"),
        approved=Count("id", filter=Q(status="approved")),
    )
    verification_stats = project.verifications.aggregate(
        total=Count("id"),
        passed=Count("id", filter=Q(pass_fail_result="pass")),
        failed=Count("id", filter=Q(pass_fail_result="fail")),
    )

    return render(
        request,
        "quality/designcontrols/design_project/detail.html",
        {
            "project": project,
            "inputs": inputs,
            "reviews": reviews,
            "verifications": verifications,
            "input_stats": input_stats,
            "review_stats": review_stats,
            "verification_stats": verification_stats,
        },
    )


@login_required
def design_project_edit(request, pk):
    project = quality_object(request, DesignProject, pk)
    if project.dhf_locked:
        messages.error(request, "This project's DHF is locked. Post-transfer changes require a formal DCO.")
        return redirect("quality:design_project_detail", pk=project.pk)

    if request.method == "POST":
        form = DesignProjectForm(request.POST, instance=project, tenant=request.tenant)
        if form.is_valid():
            project = form.save()
            write_audit_log(request.user, project, "update", tenant=request.tenant)
            messages.success(request, f"Design project {project.number} updated successfully.")
            return redirect("quality:design_project_detail", pk=project.pk)
    else:
        form = DesignProjectForm(instance=project, tenant=request.tenant)

    return render(
        request,
        "quality/designcontrols/design_project/form.html",
        {"form": form, "project": project, "title": f"Edit {project.number}", "action": "Save Changes"},
    )


@login_required
@require_POST
def design_project_delete(request, pk):
    project = quality_object(request, DesignProject, pk)
    if project.dhf_locked:
        messages.error(request, "Cannot delete a project with a locked Design History File.")
        return redirect("quality:design_project_detail", pk=project.pk)

    num = project.number
    write_audit_log(request.user, project, "delete", tenant=request.tenant)
    project.delete()
    messages.success(request, f"Design project {num} deleted.")
    return redirect("quality:design_project_list")


@login_required
@require_POST
def design_project_advance_phase(request, pk):
    project = quality_object(request, DesignProject, pk)
    if project.dhf_locked:
        messages.error(request, "Cannot advance phase on a project with a locked Design History File (DHF).")
        return redirect("quality:design_project_detail", pk=project.pk)

    phase_order = ["planning", "input", "output_verification", "validation", "commercial_closure", "closed"]
    curr_idx = phase_order.index(project.current_phase) if project.current_phase in phase_order else 0

    if curr_idx < len(phase_order) - 1:
        next_phase = phase_order[curr_idx + 1]
        project.current_phase = next_phase
        if next_phase == "commercial_closure":
            project.status = "completed"
        elif project.status == "draft":
            project.status = "active"
        project.save(update_fields=["current_phase", "status", "updated_at"])
        write_audit_log(request.user, project, "advance", tenant=request.tenant)
        messages.success(request, f"Advanced to {project.get_current_phase_display()}.")
    else:
        messages.info(request, "Project is already in final closed phase.")

    return redirect("quality:design_project_detail", pk=project.pk)


@login_required
@require_POST
def design_project_lock_dhf(request, pk):
    project = quality_object(request, DesignProject, pk)
    project.dhf_locked = True
    project.status = "completed"
    if not project.actual_completion_date:
        project.actual_completion_date = timezone.now().date()
    project.save(update_fields=["dhf_locked", "status", "actual_completion_date", "updated_at"])
    write_audit_log(request.user, project, "lock_dhf", tenant=request.tenant)
    messages.success(request, f"Design History File (DHF) for {project.number} has been frozen and locked.")
    return redirect("quality:design_project_detail", pk=project.pk)
