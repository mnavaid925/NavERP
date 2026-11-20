import csv
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.quality.forms.AuditManagement.AuditPrograms import AuditProgramForm
from apps.quality.models.AuditManagement.AuditPrograms import AuditProgram
from apps.quality.views._common import _csv_safe, quality_object, quality_scope, write_audit_log


@login_required
def audit_program_list(request):
    qs = quality_scope(
        AuditProgram.objects.select_related("program_manager", "approved_by").annotate(
            annotated_total=Count("audits"),
            annotated_completed=Count("audits", filter=Q(audits__status="closed")),
            annotated_open=Count("audits", filter=~Q(audits__status__in=["closed", "cancelled"])),
        ),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(scope_description__icontains=q)
            | Q(program_manager__first_name__icontains=q)
            | Q(program_manager__last_name__icontains=q)
            | Q(program_manager__username__icontains=q)
        )

    program_type = request.GET.get("program_type", "").strip()
    if program_type:
        qs = qs.filter(program_type=program_type)

    risk_basis = request.GET.get("risk_basis", "").strip()
    if risk_basis:
        qs = qs.filter(risk_basis=risk_basis)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    year = request.GET.get("year", "").strip()
    if year.isdigit():
        qs = qs.filter(program_year=int(year))

    program_stats = AuditProgram.objects.filter(tenant=request.tenant).aggregate(
        total_count=Count("id"),
        active_count=Count("id", filter=Q(status="active")),
        completed_count=Count("id", filter=Q(status="completed")),
    )
    total_count = program_stats["total_count"]
    active_count = program_stats["active_count"]
    completed_count = program_stats["completed_count"]

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "audit_programs": page_obj.object_list,
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "active_count": active_count,
        "completed_count": completed_count,
        "program_type_choices": AuditProgram.PROGRAM_TYPE_CHOICES,
        "risk_basis_choices": AuditProgram.RISK_BASIS_CHOICES,
        "status_choices": AuditProgram.STATUS_CHOICES,
        "selected_program_type": program_type,
        "selected_risk_basis": risk_basis,
        "selected_status": status,
        "selected_year": year,
        "search_query": q,
    }
    return render(request, "quality/auditmanagement/audit_program/list.html", context)


@login_required
def audit_program_detail(request, pk):
    program = quality_object(
        request,
        AuditProgram,
        pk,
        select_related=("program_manager", "approved_by"),
        prefetch_related=("audits", "audits__lead_auditor", "audits__target_org_unit", "audits__external_entity"),
    )
    audits = list(program.audits.all())
    total_audits = len(audits)
    completed_audits = sum(1 for a in audits if a.status == "closed")
    open_audits = sum(1 for a in audits if a.status not in ("closed", "cancelled"))
    completion_rate = int((completed_audits / total_audits) * 100) if total_audits else 0
    program.annotated_total = total_audits
    program.annotated_completed = completed_audits
    program.annotated_open = open_audits

    context = {
        "audit_program": program,
        "obj": program,
        "audits": audits,
        "completion_rate": completion_rate,
        "total_audits": total_audits,
        "completed_audits": completed_audits,
        "open_audits": open_audits,
    }
    return render(request, "quality/auditmanagement/audit_program/detail.html", context)


@login_required
def audit_program_create(request):
    if request.method == "POST":
        form = AuditProgramForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            program = form.save(commit=False)
            program.tenant = request.tenant
            program.save()
            write_audit_log(request.user, program, "create", tenant=request.tenant)
            messages.success(request, f"Audit Program {program.number} created successfully.")
            return redirect("quality:audit_program_detail", pk=program.pk)
    else:
        form = AuditProgramForm(
            tenant=request.tenant,
            initial={
                "program_year": date.today().year,
                "start_date": date(date.today().year, 1, 1),
                "end_date": date(date.today().year, 12, 31),
                "program_manager": request.user.pk,
            },
        )

    context = {
        "form": form,
        "is_edit": False,
        "audit_program": None,
        "obj": None,
    }
    return render(request, "quality/auditmanagement/audit_program/form.html", context)


@login_required
def audit_program_edit(request, pk):
    program = quality_object(request, AuditProgram, pk)
    if request.method == "POST":
        form = AuditProgramForm(request.POST, instance=program, tenant=request.tenant)
        if form.is_valid():
            program = form.save()
            write_audit_log(request.user, program, "update", tenant=request.tenant)
            messages.success(request, f"Audit Program {program.number} updated successfully.")
            return redirect("quality:audit_program_detail", pk=program.pk)
    else:
        form = AuditProgramForm(instance=program, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "audit_program": program,
        "obj": program,
    }
    return render(request, "quality/auditmanagement/audit_program/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def audit_program_delete(request, pk):
    program = quality_object(request, AuditProgram, pk)
    number = program.number
    write_audit_log(request.user, program, "delete", tenant=request.tenant)
    program.delete()
    messages.success(request, f"Audit Program {number} deleted successfully.")
    return redirect("quality:audit_program_list")


@login_required
@require_POST
@tenant_admin_required
def audit_program_approve(request, pk):
    program = quality_object(request, AuditProgram, pk)
    if program.status in ("draft", "submitted"):
        program.status = "approved"
        program.approved_by = request.user
        program.approval_date = timezone.now().date()
        program.save(update_fields=["status", "approved_by", "approval_date", "updated_at"])
        write_audit_log(request.user, program, "approve", tenant=request.tenant)
        messages.success(request, f"Audit Program {program.number} has been approved.")
    else:
        messages.warning(request, f"Audit Program {program.number} cannot be approved in status '{program.get_status_display()}'.")
    return redirect("quality:audit_program_detail", pk=program.pk)


@login_required
def audit_program_export_csv(request):
    qs = quality_scope(AuditProgram.objects.select_related("program_manager", "approved_by"), request)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(scope_description__icontains=q)
        )

    program_type = request.GET.get("program_type", "").strip()
    if program_type:
        qs = qs.filter(program_type=program_type)

    risk_basis = request.GET.get("risk_basis", "").strip()
    if risk_basis:
        qs = qs.filter(risk_basis=risk_basis)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    year = request.GET.get("year", "").strip()
    if year.isdigit():
        qs = qs.filter(program_year=int(year))

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="audit_programs.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Program Number",
        "Year",
        "Title",
        "Program Type",
        "Risk Basis",
        "Status",
        "Start Date",
        "End Date",
        "Budget Hours",
        "Program Manager",
        "Approved By",
        "Approval Date",
    ])

    for prog in qs:
        writer.writerow([
            _csv_safe(prog.number),
            _csv_safe(prog.program_year),
            _csv_safe(prog.title),
            _csv_safe(prog.get_program_type_display()),
            _csv_safe(prog.get_risk_basis_display()),
            _csv_safe(prog.get_status_display()),
            _csv_safe(prog.start_date),
            _csv_safe(prog.end_date),
            _csv_safe(prog.allocated_budget_hours),
            _csv_safe(prog.program_manager.get_full_name() or prog.program_manager.username if prog.program_manager else ""),
            _csv_safe(prog.approved_by.get_full_name() or prog.approved_by.username if prog.approved_by else ""),
            _csv_safe(prog.approval_date),
        ])

    return response
