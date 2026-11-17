import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.quality.forms.DesignControls.DesignVerifications import DesignVerificationForm
from apps.quality.models.DesignControls.DesignInputs import DesignInput
from apps.quality.models.DesignControls.DesignProjects import DesignProject
from apps.quality.models.DesignControls.DesignVerifications import DesignVerification
from apps.quality.views._common import quality_object, quality_scope


def csv_safe(value):
    if value is None:
        return ""
    text = str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


@login_required
def design_verification_list(request):
    qs = quality_scope(DesignVerification.objects.all(), request).select_related(
        "project", "primary_input", "executed_by"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q) | Q(title__icontains=q) | Q(acceptance_criteria__icontains=q) | Q(results_summary__icontains=q)
        )

    selected_project = request.GET.get("project", "").strip()
    if selected_project and selected_project.isdigit():
        qs = qs.filter(project_id=int(selected_project))

    selected_activity = request.GET.get("activity_type", "").strip()
    if selected_activity:
        qs = qs.filter(activity_type=selected_activity)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_result = request.GET.get("result", "").strip()
    if selected_result:
        qs = qs.filter(pass_fail_result=selected_result)

    projects = quality_scope(DesignProject.objects.all(), request).order_by("number")
    total_count = quality_scope(DesignVerification.objects.all(), request).count()
    passed_count = quality_scope(DesignVerification.objects.filter(pass_fail_result="pass"), request).count()
    failed_count = quality_scope(DesignVerification.objects.filter(pass_fail_result="fail"), request).count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    verifications = paginator.get_page(page_number)

    return render(
        request,
        "quality/designcontrols/design_verification/list.html",
        {
            "verifications": verifications,
            "projects": projects,
            "activity_choices": DesignVerification.ACTIVITY_TYPE_CHOICES,
            "status_choices": DesignVerification.STATUS_CHOICES,
            "result_choices": DesignVerification.RESULT_CHOICES,
            "total_count": total_count,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "q": q,
            "selected_project": selected_project,
            "selected_activity": selected_activity,
            "selected_status": selected_status,
            "selected_result": selected_result,
        },
    )


@login_required
def design_verification_export(request):
    qs = quality_scope(DesignVerification.objects.all(), request).select_related(
        "project", "primary_input", "executed_by"
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="design_verifications.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Number", "Title", "Project", "Design Input", "Activity Type", "Status",
        "Test Method", "Sample Size", "Pass/Fail Result", "Executed By", "Execution Date"
    ])
    for ver in qs.iterator(chunk_size=500):
        writer.writerow([
            csv_safe(ver.number),
            csv_safe(ver.title),
            csv_safe(ver.project.number if ver.project else ""),
            csv_safe(ver.primary_input.identifier if ver.primary_input else ""),
            csv_safe(ver.get_activity_type_display()),
            csv_safe(ver.get_status_display()),
            csv_safe(ver.get_test_method_display()),
            csv_safe(ver.sample_size),
            csv_safe(ver.get_pass_fail_result_display()),
            csv_safe(ver.executed_by.get_full_name() or ver.executed_by.username if ver.executed_by else ""),
            csv_safe(ver.execution_date),
        ])
    return response


@login_required
def design_verification_create(request):
    initial = {}
    input_id = request.GET.get("input", "").strip()
    project_id = request.GET.get("project", "").strip()

    if input_id and input_id.isdigit():
        primary_inp = quality_object(request, DesignInput, int(input_id))
        initial["primary_input"] = primary_inp
        initial["project"] = primary_inp.project
    elif project_id and project_id.isdigit():
        project = quality_object(request, DesignProject, int(project_id))
        initial["project"] = project

    if request.method == "POST":
        form = DesignVerificationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                ver = form.save(commit=False)
                ver.tenant = request.tenant
                ver.save()
                # If test is passed and status is passed, auto-verify primary design input
                if ver.pass_fail_result == "pass" and ver.status == "passed":
                    ver.primary_input.status = "verified"
                    ver.primary_input.save(update_fields=["status", "updated_at"])
                write_audit_log(request.user, ver, "create", tenant=request.tenant)
            messages.success(request, f"Verification protocol {ver.number} created successfully.")
            return redirect("quality:design_verification_detail", pk=ver.pk)
    else:
        form = DesignVerificationForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "quality/designcontrols/design_verification/form.html",
        {"form": form, "title": "New Verification / Validation Protocol", "action": "Create Protocol"},
    )


@login_required
def design_verification_detail(request, pk):
    verification = quality_object(
        request,
        DesignVerification,
        pk,
        select_related=["project", "primary_input", "executed_by", "protocol_document", "report_document"],
    )

    return render(
        request,
        "quality/designcontrols/design_verification/detail.html",
        {"verification": verification},
    )


@login_required
def design_verification_edit(request, pk):
    verification = quality_object(request, DesignVerification, pk)
    if verification.project.dhf_locked:
        messages.error(request, "Parent project DHF is locked. Modifying verification records requires a Document Change Order.")
        return redirect("quality:design_verification_detail", pk=verification.pk)

    if request.method == "POST":
        form = DesignVerificationForm(request.POST, instance=verification, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                verification = form.save()
                if verification.pass_fail_result == "pass" and verification.status == "passed":
                    verification.primary_input.status = "verified"
                    verification.primary_input.save(update_fields=["status", "updated_at"])
                write_audit_log(request.user, verification, "update", tenant=request.tenant)
            messages.success(request, f"Verification protocol {verification.number} updated successfully.")
            return redirect("quality:design_verification_detail", pk=verification.pk)
    else:
        form = DesignVerificationForm(instance=verification, tenant=request.tenant)

    return render(
        request,
        "quality/designcontrols/design_verification/form.html",
        {"form": form, "verification": verification, "title": f"Edit {verification.number}", "action": "Save Changes"},
    )


@login_required
@require_POST
def design_verification_delete(request, pk):
    verification = quality_object(request, DesignVerification, pk)
    if verification.project.dhf_locked:
        messages.error(request, "Cannot delete verification protocol from a locked Design History File.")
        return redirect("quality:design_verification_detail", pk=verification.pk)

    num = verification.number
    write_audit_log(request.user, verification, "delete", tenant=request.tenant)
    verification.delete()
    messages.success(request, f"Verification protocol {num} removed.")
    return redirect("quality:design_verification_list")
