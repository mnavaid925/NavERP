import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.quality.forms.DesignControls.DesignInputs import DesignInputForm
from apps.quality.models.DesignControls.DesignInputs import DesignInput
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
def design_input_list(request):
    qs = quality_scope(DesignInput.objects.all(), request).select_related("project", "owner", "user_need_parent")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q) | Q(identifier__icontains=q) | Q(title__icontains=q) | Q(description__icontains=q)
        )

    selected_project = request.GET.get("project", "").strip()
    if selected_project and selected_project.isdigit():
        qs = qs.filter(project_id=int(selected_project))

    selected_type = request.GET.get("input_type", "").strip()
    if selected_type:
        qs = qs.filter(input_type=selected_type)

    selected_priority = request.GET.get("priority", "").strip()
    if selected_priority:
        qs = qs.filter(priority=selected_priority)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    projects = quality_scope(DesignProject.objects.all(), request).order_by("number")
    total_count = quality_scope(DesignInput.objects.all(), request).count()
    verified_count = quality_scope(DesignInput.objects.filter(status="verified"), request).count()
    unverified_count = total_count - verified_count

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    inputs = paginator.get_page(page_number)

    return render(
        request,
        "quality/designcontrols/design_input/list.html",
        {
            "inputs": inputs,
            "projects": projects,
            "input_type_choices": DesignInput.INPUT_TYPE_CHOICES,
            "priority_choices": DesignInput.PRIORITY_CHOICES,
            "status_choices": DesignInput.STATUS_CHOICES,
            "total_count": total_count,
            "verified_count": verified_count,
            "unverified_count": unverified_count,
            "q": q,
            "selected_project": selected_project,
            "selected_type": selected_type,
            "selected_priority": selected_priority,
            "selected_status": selected_status,
        },
    )


@login_required
def design_input_export(request):
    qs = quality_scope(DesignInput.objects.all(), request).select_related("project", "owner", "user_need_parent")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="design_inputs.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Number", "Identifier", "Title", "Project", "Type", "Priority", "Status",
        "Owner", "Parent Need", "Acceptance Criteria", "Verified"
    ])
    for item in qs.iterator(chunk_size=500):
        writer.writerow([
            csv_safe(item.number),
            csv_safe(item.identifier),
            csv_safe(item.title),
            csv_safe(item.project.number if item.project else ""),
            csv_safe(item.get_input_type_display()),
            csv_safe(item.get_priority_display()),
            csv_safe(item.get_status_display()),
            csv_safe(item.owner.get_full_name() or item.owner.username if item.owner else ""),
            csv_safe(item.user_need_parent.identifier if item.user_need_parent else ""),
            csv_safe(item.acceptance_criteria),
            csv_safe("Yes" if item.is_verified else "No"),
        ])
    return response


@login_required
def design_input_create(request):
    initial = {}
    project_id = request.GET.get("project", "").strip()
    if project_id and project_id.isdigit():
        project = quality_object(request, DesignProject, int(project_id))
        initial["project"] = project

    if request.method == "POST":
        form = DesignInputForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            inp = form.save(commit=False)
            inp.tenant = request.tenant
            inp.save()
            write_audit_log(request.user, inp, "create", tenant=request.tenant)
            messages.success(request, f"Design input {inp.identifier} created successfully.")
            return redirect("quality:design_input_detail", pk=inp.pk)
    else:
        form = DesignInputForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "quality/designcontrols/design_input/form.html",
        {"form": form, "title": "New Design Input / Specification", "action": "Create"},
    )


@login_required
def design_input_detail(request, pk):
    input_obj = quality_object(
        request,
        DesignInput,
        pk,
        select_related=["project", "owner", "user_need_parent", "controlled_document"],
    )

    verifications = input_obj.verifications.all().select_related("executed_by", "protocol_document", "report_document")
    derived_inputs = input_obj.derived_inputs.all().select_related("owner")

    return render(
        request,
        "quality/designcontrols/design_input/detail.html",
        {
            "input_obj": input_obj,
            "verifications": verifications,
            "derived_inputs": derived_inputs,
        },
    )


@login_required
def design_input_edit(request, pk):
    input_obj = quality_object(request, DesignInput, pk)
    if input_obj.project.dhf_locked:
        messages.error(request, "Parent project DHF is locked. Modifying design inputs requires a Document Change Order.")
        return redirect("quality:design_input_detail", pk=input_obj.pk)

    if request.method == "POST":
        form = DesignInputForm(request.POST, instance=input_obj, tenant=request.tenant)
        if form.is_valid():
            input_obj = form.save()
            write_audit_log(request.user, input_obj, "update", tenant=request.tenant)
            messages.success(request, f"Design input {input_obj.identifier} updated successfully.")
            return redirect("quality:design_input_detail", pk=input_obj.pk)
    else:
        form = DesignInputForm(instance=input_obj, tenant=request.tenant)

    return render(
        request,
        "quality/designcontrols/design_input/form.html",
        {"form": form, "input_obj": input_obj, "title": f"Edit {input_obj.identifier}", "action": "Save Changes"},
    )


@login_required
@require_POST
def design_input_delete(request, pk):
    input_obj = quality_object(request, DesignInput, pk)
    if input_obj.project.dhf_locked:
        messages.error(request, "Cannot delete design input from a locked Design History File.")
        return redirect("quality:design_input_detail", pk=input_obj.pk)

    ident = input_obj.identifier
    write_audit_log(request.user, input_obj, "delete", tenant=request.tenant)
    input_obj.delete()
    messages.success(request, f"Design input {ident} removed.")
    return redirect("quality:design_input_list")
