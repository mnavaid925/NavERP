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
from apps.core.models.OrgUnit import OrgUnit
from apps.quality.forms.AuditManagement.QualityAudits import QualityAuditForm
from apps.quality.models.AuditManagement.AuditPrograms import AuditProgram
from apps.quality.models.AuditManagement.QualityAudits import QualityAudit
from apps.quality.views._common import _csv_safe, quality_object, quality_scope, write_audit_log


@login_required
def quality_audit_list(request):
    qs = quality_scope(
        QualityAudit.objects.select_related(
            "program", "target_org_unit", "external_entity", "lead_auditor", "auditee_lead", "audit_checklist_sop"
        ),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(scope_objectives__icontains=q)
            | Q(product_scope__icontains=q)
            | Q(lot_number_sampled__icontains=q)
            | Q(lead_auditor__first_name__icontains=q)
            | Q(lead_auditor__last_name__icontains=q)
            | Q(lead_auditor__username__icontains=q)
        )

    audit_type = request.GET.get("audit_type", "").strip()
    if audit_type:
        qs = qs.filter(audit_type=audit_type)

    framework = request.GET.get("standard_framework", "").strip()
    if framework:
        qs = qs.filter(standard_framework=framework)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    outcome = request.GET.get("outcome", "").strip()
    if outcome:
        qs = qs.filter(outcome=outcome)

    program_param = request.GET.get("program", "").strip()
    if program_param.isdigit():
        qs = qs.filter(program_id=int(program_param))

    org_unit_param = request.GET.get("org_unit", "").strip()
    if org_unit_param.isdigit():
        qs = qs.filter(target_org_unit_id=int(org_unit_param))

    audit_stats = QualityAudit.objects.filter(tenant=request.tenant).aggregate(
        total_count=Count("id"),
        scheduled_count=Count("id", filter=Q(status="scheduled")),
        in_progress_count=Count("id", filter=Q(status="in_progress")),
        closed_count=Count("id", filter=Q(status="closed")),
    )
    total_count = audit_stats["total_count"]
    scheduled_count = audit_stats["scheduled_count"]
    in_progress_count = audit_stats["in_progress_count"]
    closed_count = audit_stats["closed_count"]

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    programs = AuditProgram.objects.filter(tenant=request.tenant)
    org_units = OrgUnit.objects.filter(tenant=request.tenant)

    context = {
        "quality_audits": page_obj.object_list,
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "scheduled_count": scheduled_count,
        "in_progress_count": in_progress_count,
        "closed_count": closed_count,
        "audit_type_choices": QualityAudit.AUDIT_TYPE_CHOICES,
        "audit_method_choices": QualityAudit.AUDIT_METHOD_CHOICES,
        "standard_framework_choices": QualityAudit.STANDARD_FRAMEWORK_CHOICES,
        "status_choices": QualityAudit.STATUS_CHOICES,
        "outcome_choices": QualityAudit.OUTCOME_CHOICES,
        "programs": programs,
        "org_units": org_units,
        "selected_audit_type": audit_type,
        "selected_framework": framework,
        "selected_status": status,
        "selected_outcome": outcome,
        "selected_program": program_param,
        "selected_org_unit": org_unit_param,
        "search_query": q,
    }
    return render(request, "quality/auditmanagement/quality_audit/list.html", context)


@login_required
def quality_audit_detail(request, pk):
    audit = quality_object(
        request,
        QualityAudit,
        pk,
        select_related=("program", "target_org_unit", "external_entity", "lead_auditor", "auditee_lead", "audit_checklist_sop"),
        prefetch_related=("findings", "findings__assignee", "findings__audited_org_unit", "findings__linked_capa", "regulatory_hosts"),
    )
    findings = audit.findings.all()
    regulatory_hosts = audit.regulatory_hosts.all()

    context = {
        "quality_audit": audit,
        "obj": audit,
        "findings": findings,
        "regulatory_hosts": regulatory_hosts,
        "days_open": audit.days_open,
        "is_overdue": audit.is_overdue,
    }
    return render(request, "quality/auditmanagement/quality_audit/detail.html", context)


@login_required
def quality_audit_create(request):
    initial = {
        "planned_start_date": date.today(),
        "planned_end_date": date.today(),
        "lead_auditor": request.user.pk,
    }
    program_param = request.GET.get("program", "").strip()
    if program_param.isdigit():
        initial["program"] = int(program_param)

    if request.method == "POST":
        form = QualityAuditForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            audit = form.save(commit=False)
            audit.tenant = request.tenant
            audit.save()
            write_audit_log(request.user, audit, "create", tenant=request.tenant)
            messages.success(request, f"Quality Audit {audit.number} created successfully.")
            return redirect("quality:quality_audit_detail", pk=audit.pk)
    else:
        form = QualityAuditForm(tenant=request.tenant, initial=initial)

    context = {
        "form": form,
        "is_edit": False,
        "quality_audit": None,
        "obj": None,
    }
    return render(request, "quality/auditmanagement/quality_audit/form.html", context)


@login_required
def quality_audit_edit(request, pk):
    audit = quality_object(request, QualityAudit, pk)
    if request.method == "POST":
        form = QualityAuditForm(request.POST, instance=audit, tenant=request.tenant)
        if form.is_valid():
            audit = form.save()
            write_audit_log(request.user, audit, "update", tenant=request.tenant)
            messages.success(request, f"Quality Audit {audit.number} updated successfully.")
            return redirect("quality:quality_audit_detail", pk=audit.pk)
    else:
        form = QualityAuditForm(instance=audit, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "quality_audit": audit,
        "obj": audit,
    }
    return render(request, "quality/auditmanagement/quality_audit/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def quality_audit_delete(request, pk):
    audit = quality_object(request, QualityAudit, pk)
    number = audit.number
    write_audit_log(request.user, audit, "delete", tenant=request.tenant)
    audit.delete()
    messages.success(request, f"Quality Audit {number} deleted successfully.")
    return redirect("quality:quality_audit_list")


@login_required
@require_POST
def quality_audit_publish_report(request, pk):
    audit = quality_object(request, QualityAudit, pk)
    if audit.status == "cancelled":
        messages.warning(request, f"Quality Audit {audit.number} is cancelled and cannot publish a report.")
        return redirect("quality:quality_audit_detail", pk=audit.pk)

    audit.report_published_date = timezone.now().date()
    if audit.status in ("scheduled", "in_preparation", "in_progress"):
        audit.status = "reporting"
    audit.save(update_fields=["report_published_date", "status", "updated_at"])
    write_audit_log(request.user, audit, "publish", tenant=request.tenant)
    messages.success(request, f"Audit report published for {audit.number}.")
    return redirect("quality:quality_audit_detail", pk=audit.pk)


@login_required
@require_POST
def quality_audit_close(request, pk):
    audit = quality_object(request, QualityAudit, pk)
    if audit.status == "cancelled":
        messages.warning(request, f"Quality Audit {audit.number} is cancelled and cannot be closed.")
        return redirect("quality:quality_audit_detail", pk=audit.pk)

    is_admin = request.user.is_superuser or getattr(request.user, "is_tenant_admin", False) or getattr(request.user, "role", "") == "admin"
    is_lead = (audit.lead_auditor_id == request.user.id)
    if not (is_lead or is_admin):
        messages.error(request, "Only the lead auditor or a tenant administrator can close this audit.")
        return redirect("quality:quality_audit_detail", pk=audit.pk)

    open_critical_count = audit.findings.filter(severity="critical").exclude(status="closed").count()
    if open_critical_count > 0:
        messages.error(request, f"Cannot close audit: There are {open_critical_count} open Critical non-conformance findings that must be verified closed first.")
        return redirect("quality:quality_audit_detail", pk=audit.pk)

    audit.status = "closed"
    if not audit.actual_end_date:
        audit.actual_end_date = timezone.now().date()
    audit.save(update_fields=["status", "actual_end_date", "updated_at"])
    write_audit_log(request.user, audit, "close", tenant=request.tenant)
    messages.success(request, f"Quality Audit {audit.number} has been closed.")
    return redirect("quality:quality_audit_detail", pk=audit.pk)


@login_required
def quality_audit_export_csv(request):
    qs = quality_scope(
        QualityAudit.objects.select_related("program", "target_org_unit", "external_entity", "lead_auditor"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(number__icontains=q))

    audit_type = request.GET.get("audit_type", "").strip()
    if audit_type:
        qs = qs.filter(audit_type=audit_type)

    framework = request.GET.get("standard_framework", "").strip()
    if framework:
        qs = qs.filter(standard_framework=framework)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    outcome = request.GET.get("outcome", "").strip()
    if outcome:
        qs = qs.filter(outcome=outcome)

    program_param = request.GET.get("program", "").strip()
    if program_param.isdigit():
        qs = qs.filter(program_id=int(program_param))

    org_unit_param = request.GET.get("org_unit", "").strip()
    if org_unit_param.isdigit():
        qs = qs.filter(target_org_unit_id=int(org_unit_param))

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="quality_audits.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Audit Number",
        "Title",
        "Program",
        "Audit Type",
        "Method",
        "Framework",
        "Audited Unit/Entity",
        "Lead Auditor",
        "Planned Start",
        "Planned End",
        "Status",
        "Outcome",
        "Total Findings",
        "Critical Findings",
        "Major Findings",
        "Minor Findings",
    ])

    for aud in qs:
        unit_or_party = ""
        if aud.target_org_unit:
            unit_or_party = aud.target_org_unit.name
        elif aud.external_entity:
            unit_or_party = aud.external_entity.legal_name

        writer.writerow([
            _csv_safe(aud.number),
            _csv_safe(aud.title),
            _csv_safe(aud.program.number if aud.program else ""),
            _csv_safe(aud.get_audit_type_display()),
            _csv_safe(aud.get_audit_method_display()),
            _csv_safe(aud.get_standard_framework_display()),
            _csv_safe(unit_or_party),
            _csv_safe(aud.lead_auditor.get_full_name() or aud.lead_auditor.username if aud.lead_auditor else ""),
            _csv_safe(aud.planned_start_date),
            _csv_safe(aud.planned_end_date),
            _csv_safe(aud.get_status_display()),
            _csv_safe(aud.get_outcome_display()),
            _csv_safe(aud.total_findings_count),
            _csv_safe(aud.critical_findings_count),
            _csv_safe(aud.major_findings_count),
            _csv_safe(aud.minor_findings_count),
        ])

    return response
