import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.quality.models.DesignControls.DesignInputs import DesignInput
from apps.quality.models.DesignControls.DesignProjects import DesignProject
from apps.quality.models.DesignControls.DesignReviews import DesignReview
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
def traceability_matrix(request):
    projects = quality_scope(DesignProject.objects.all(), request).order_by("-created_at")

    selected_project_id = request.GET.get("project", "").strip()
    selected_project = None

    if selected_project_id:
        if selected_project_id.isdigit():
            selected_project = quality_scope(DesignProject.objects.filter(pk=int(selected_project_id)), request).first()
        if not selected_project:
            messages.warning(request, "Selected design project was not found or is inaccessible.")
            if projects.exists():
                selected_project = projects.first()
    elif projects.exists():
        selected_project = projects.first()

    matrix_rows = []
    total_inputs = 0
    verified_inputs = 0
    gap_count = 0

    if selected_project:
        inputs = selected_project.inputs.all().select_related("user_need_parent", "controlled_document").prefetch_related("verifications")
        total_inputs = inputs.count()

        for inp in inputs:
            verifications = list(inp.verifications.all())
            is_verified = inp.is_verified or any(v.pass_fail_result == "pass" for v in verifications)
            if is_verified:
                verified_inputs += 1
            else:
                gap_count += 1

            matrix_rows.append({
                "input": inp,
                "user_need": inp.user_need_parent if inp.user_need_parent else (inp if inp.input_type == "user_need" else None),
                "verifications": verifications,
                "is_verified": is_verified,
                "has_failures": any(v.pass_fail_result == "fail" for v in verifications),
            })

    coverage_percentage = round((verified_inputs / total_inputs * 100), 1) if total_inputs > 0 else 0

    return render(
        request,
        "quality/designcontrols/traceability_matrix.html",
        {
            "projects": projects,
            "selected_project": selected_project,
            "matrix_rows": matrix_rows,
            "total_inputs": total_inputs,
            "verified_inputs": verified_inputs,
            "coverage_percentage": coverage_percentage,
            "gap_count": gap_count,
        },
    )


@login_required
def traceability_matrix_export(request):
    selected_project_id = request.GET.get("project", "").strip()
    if not (selected_project_id and selected_project_id.isdigit()):
        messages.error(request, "Select a valid design project to export its matrix.")
        return redirect("quality:traceability_matrix")

    project = quality_object(request, DesignProject, int(selected_project_id))
    inputs = project.inputs.all().select_related("user_need_parent", "controlled_document").prefetch_related("verifications")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="RTM_{project.number}.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Project #", "User Need", "Design Input Identifier", "Design Input Title", "Type",
        "Acceptance Criteria", "Verification Protocol #", "Test Method", "Pass/Fail Result", "Status"
    ])

    for inp in inputs:
        verifications = list(inp.verifications.all())
        user_need_str = inp.user_need_parent.identifier if inp.user_need_parent else ("Self (User Need)" if inp.input_type == "user_need" else "None")
        if verifications:
            for v in verifications:
                writer.writerow([
                    csv_safe(project.number),
                    csv_safe(user_need_str),
                    csv_safe(inp.identifier),
                    csv_safe(inp.title),
                    csv_safe(inp.get_input_type_display()),
                    csv_safe(inp.acceptance_criteria),
                    csv_safe(v.number),
                    csv_safe(v.get_test_method_display()),
                    csv_safe(v.get_pass_fail_result_display()),
                    csv_safe("Verified" if v.pass_fail_result == "pass" else "Unverified"),
                ])
        else:
            writer.writerow([
                csv_safe(project.number),
                csv_safe(user_need_str),
                csv_safe(inp.identifier),
                csv_safe(inp.title),
                csv_safe(inp.get_input_type_display()),
                csv_safe(inp.acceptance_criteria),
                "NO VERIFICATION LINKED",
                "—",
                "Pending",
                "Coverage Gap",
            ])

    return response


@login_required
def design_project_dhf(request, pk):
    project = quality_object(
        request,
        DesignProject,
        pk,
        select_related=["project_lead", "quality_lead", "department"],
    )

    inputs = project.inputs.all().select_related("owner", "user_need_parent", "controlled_document").prefetch_related("verifications")
    reviews = project.reviews.all().select_related("lead_reviewer", "independent_reviewer", "electronic_signature").order_by("review_date")
    verifications = project.verifications.all().select_related("primary_input", "executed_by", "protocol_document", "report_document").order_by("created_at")

    spec_ids = set()
    specifications = []
    for inp in inputs:
        if inp.controlled_document and inp.controlled_document.pk not in spec_ids:
            spec_ids.add(inp.controlled_document.pk)
            specifications.append(inp.controlled_document)

    for v in verifications:
        if v.protocol_document and v.protocol_document.pk not in spec_ids:
            spec_ids.add(v.protocol_document.pk)
            specifications.append(v.protocol_document)
        if v.report_document and v.report_document.pk not in spec_ids:
            spec_ids.add(v.report_document.pk)
            specifications.append(v.report_document)

    total_inputs = inputs.count()
    verified_inputs = sum(1 for inp in inputs if inp.is_verified)
    transfer_gate_cleared = reviews.filter(review_stage="transfer_gate", status="approved").exists()

    is_dhf_complete = (
        total_inputs > 0 and
        verified_inputs == total_inputs and
        transfer_gate_cleared and
        not verifications.filter(pass_fail_result="fail").exists()
    )

    return render(
        request,
        "quality/designcontrols/dhf_dossier.html",
        {
            "project": project,
            "inputs": inputs,
            "reviews": reviews,
            "verifications": verifications,
            "specifications": specifications,
            "total_inputs": total_inputs,
            "verified_inputs": verified_inputs,
            "transfer_gate_cleared": transfer_gate_cleared,
            "is_dhf_complete": is_dhf_complete,
        },
    )


@login_required
def design_project_dhf_export(request, pk):
    project = quality_object(request, DesignProject, pk)
    inputs = project.inputs.all()
    reviews = project.reviews.all()
    verifications = project.verifications.all()

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="DHF_Index_{project.number}.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow(["Section", "Record Number", "Title / Item", "Classification / Stage", "Status", "Date / Outcome"])

    writer.writerow(["DHF Plan", csv_safe(project.number), csv_safe(project.title), csv_safe(project.get_device_class_display()), csv_safe(project.get_status_display()), csv_safe(project.created_at.date())])

    for inp in inputs:
        writer.writerow(["Design Input", csv_safe(inp.identifier), csv_safe(inp.title), csv_safe(inp.get_input_type_display()), csv_safe(inp.get_status_display()), csv_safe("Verified" if inp.is_verified else "Unverified")])

    for rev in reviews:
        writer.writerow(["Design Review", csv_safe(rev.number), csv_safe(rev.title), csv_safe(rev.get_review_stage_display()), csv_safe(rev.get_status_display()), csv_safe(rev.review_date)])

    for ver in verifications:
        writer.writerow(["Verification", csv_safe(ver.number), csv_safe(ver.title), csv_safe(ver.get_activity_type_display()), csv_safe(ver.get_status_display()), csv_safe(ver.get_pass_fail_result_display())])

    return response
