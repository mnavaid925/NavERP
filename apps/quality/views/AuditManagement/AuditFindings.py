import csv
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models.OrgUnit import OrgUnit
from apps.quality.forms.AuditManagement.AuditFindings import AuditFindingForm, AuditFindingResponseForm
from apps.quality.models.AuditManagement.AuditFindings import AuditFinding
from apps.quality.models.AuditManagement.QualityAudits import QualityAudit
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.views._common import _csv_safe, quality_object, quality_scope, write_audit_log

User = get_user_model()


@login_required
def audit_finding_list(request):
    qs = quality_scope(
        AuditFinding.objects.select_related(
            "audit", "audited_org_unit", "assignee", "linked_capa", "linked_ncr", "closure_verified_by"
        ),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(standard_clause__icontains=q)
            | Q(requirement_statement__icontains=q)
            | Q(condition_evidence__icontains=q)
            | Q(assignee__first_name__icontains=q)
            | Q(assignee__last_name__icontains=q)
            | Q(assignee__username__icontains=q)
        )

    severity = request.GET.get("severity", "").strip()
    if severity:
        qs = qs.filter(severity=severity)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    audit_param = request.GET.get("audit", "").strip()
    if audit_param.isdigit():
        qs = qs.filter(audit_id=int(audit_param))

    org_unit_param = request.GET.get("org_unit", "").strip()
    if org_unit_param.isdigit():
        qs = qs.filter(audited_org_unit_id=int(org_unit_param))

    assignee_param = request.GET.get("assignee", "").strip()
    if assignee_param.isdigit():
        qs = qs.filter(assignee_id=int(assignee_param))

    total_count = AuditFinding.objects.filter(tenant=request.tenant).count()
    open_count = AuditFinding.objects.filter(tenant=request.tenant).exclude(status="closed").count()
    critical_count = AuditFinding.objects.filter(tenant=request.tenant, severity__in=["critical", "major"]).count()
    overdue_count = AuditFinding.objects.filter(
        tenant=request.tenant,
        response_due_date__lt=date.today()
    ).exclude(status__in=["closed", "response_accepted"]).count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    audits = QualityAudit.objects.filter(tenant=request.tenant)
    org_units = OrgUnit.objects.filter(tenant=request.tenant)
    assignees = User.objects.filter(tenant=request.tenant)

    context = {
        "audit_findings": page_obj.object_list,
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "open_count": open_count,
        "critical_count": critical_count,
        "overdue_count": overdue_count,
        "severity_choices": AuditFinding.SEVERITY_CHOICES,
        "status_choices": AuditFinding.STATUS_CHOICES,
        "audits": audits,
        "org_units": org_units,
        "assignees": assignees,
        "selected_severity": severity,
        "selected_status": status,
        "selected_audit": audit_param,
        "selected_org_unit": org_unit_param,
        "selected_assignee": assignee_param,
        "search_query": q,
    }
    return render(request, "quality/auditmanagement/audit_finding/list.html", context)


@login_required
def audit_finding_detail(request, pk):
    finding = quality_object(
        request,
        AuditFinding,
        pk,
        select_related=("audit", "audited_org_unit", "assignee", "linked_capa", "linked_ncr", "closure_verified_by"),
    )
    response_form = AuditFindingResponseForm(instance=finding) if finding.status in ("issued", "draft", "response_submitted") else None

    context = {
        "audit_finding": finding,
        "obj": finding,
        "response_form": response_form,
    }
    return render(request, "quality/auditmanagement/audit_finding/detail.html", context)


@login_required
def audit_finding_create(request):
    initial = {
        "response_due_date": date.today() + timedelta(days=30),
        "assignee": request.user.pk,
    }
    audit_param = request.GET.get("audit", "").strip()
    if audit_param.isdigit():
        initial["audit"] = int(audit_param)

    if request.method == "POST":
        form = AuditFindingForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            finding = form.save(commit=False)
            finding.tenant = request.tenant
            finding.save()
            write_audit_log(request.user, finding, "create", tenant=request.tenant)
            messages.success(request, f"Audit Finding {finding.number} logged successfully.")
            return redirect("quality:audit_finding_detail", pk=finding.pk)
    else:
        form = AuditFindingForm(tenant=request.tenant, initial=initial)

    context = {
        "form": form,
        "is_edit": False,
        "audit_finding": None,
        "obj": None,
    }
    return render(request, "quality/auditmanagement/audit_finding/form.html", context)


@login_required
def audit_finding_edit(request, pk):
    finding = quality_object(request, AuditFinding, pk)
    if request.method == "POST":
        form = AuditFindingForm(request.POST, instance=finding, tenant=request.tenant)
        if form.is_valid():
            finding = form.save()
            write_audit_log(request.user, finding, "update", tenant=request.tenant)
            messages.success(request, f"Audit Finding {finding.number} updated successfully.")
            return redirect("quality:audit_finding_detail", pk=finding.pk)
    else:
        form = AuditFindingForm(instance=finding, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "audit_finding": finding,
        "obj": finding,
    }
    return render(request, "quality/auditmanagement/audit_finding/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def audit_finding_delete(request, pk):
    finding = quality_object(request, AuditFinding, pk)
    audit_pk = finding.audit_id
    number = finding.number
    write_audit_log(request.user, finding, "delete", tenant=request.tenant)
    finding.delete()
    messages.success(request, f"Audit Finding {number} deleted successfully.")
    if audit_pk:
        return redirect("quality:quality_audit_detail", pk=audit_pk)
    return redirect("quality:audit_finding_list")


@login_required
@require_POST
def audit_finding_submit_response(request, pk):
    finding = quality_object(request, AuditFinding, pk)
    form = AuditFindingResponseForm(request.POST, instance=finding)
    if form.is_valid():
        finding = form.save(commit=False)
        finding.response_received_date = timezone.now().date()
        finding.status = "response_submitted"
        finding.save()
        write_audit_log(request.user, finding, "respond", tenant=request.tenant)
        messages.success(request, f"Remediation response submitted for finding {finding.number}.")
    else:
        messages.error(request, "Please fill in all response sections properly.")
    return redirect("quality:audit_finding_detail", pk=finding.pk)


@login_required
@require_POST
def audit_finding_verify_close(request, pk):
    finding = quality_object(request, AuditFinding, pk)
    closure_notes = request.POST.get("closure_notes", "").strip()
    finding.closure_verified_by = request.user
    finding.closed_date = timezone.now().date()
    finding.status = "closed"
    if closure_notes:
        finding.closure_notes = closure_notes
    finding.save()
    write_audit_log(request.user, finding, "verify", tenant=request.tenant)
    messages.success(request, f"Audit Finding {finding.number} verified and closed.")
    return redirect("quality:audit_finding_detail", pk=finding.pk)


@login_required
@require_POST
def audit_finding_create_capa(request, pk):
    finding = quality_object(request, AuditFinding, pk)
    if finding.linked_capa:
        messages.info(request, f"Finding {finding.number} is already linked to CAPA {finding.linked_capa.number}.")
        return redirect("quality:capa_investigation_detail", pk=finding.linked_capa.pk)

    with transaction.atomic():
        capa = CapaInvestigation.objects.create(
            tenant=request.tenant,
            title=f"CAPA from Audit Finding: {finding.title}"[:255],
            source_type="internal_audit",
            source_reference=finding.number,
            action_type="corrective",
            issue_summary=f"Standard Clause: {finding.standard_clause}\n\nRequirement: {finding.requirement_statement}\n\nEvidence: {finding.condition_evidence}",
            risk_priority="critical" if finding.severity == "critical" else "high",
            quality_owner=finding.audit.lead_auditor or request.user,
            lead_investigator=request.user,
            target_closure_date=finding.response_due_date,
            department=finding.audited_org_unit,
            status="draft",
        )
        finding.linked_capa = capa
        finding.status = "capa_in_progress"
        finding.save(update_fields=["linked_capa", "status", "updated_at"])
        write_audit_log(request.user, finding, "update", tenant=request.tenant)

    messages.success(request, f"Closed-loop CAPA {capa.number} initiated for finding {finding.number}.")
    return redirect("quality:capa_investigation_detail", pk=capa.pk)


@login_required
def audit_finding_export_csv(request):
    qs = quality_scope(
        AuditFinding.objects.select_related("audit", "audited_org_unit", "assignee", "linked_capa"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(number__icontains=q) | Q(standard_clause__icontains=q))

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="audit_findings.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Finding Number",
        "Audit Number",
        "Severity",
        "Standard Clause",
        "Title",
        "Audited Unit",
        "Assignee",
        "Response Due Date",
        "Response Received Date",
        "Status",
        "Linked CAPA",
        "Closed Date",
    ])

    for fnd in qs:
        writer.writerow([
            _csv_safe(fnd.number),
            _csv_safe(fnd.audit.number if fnd.audit else ""),
            _csv_safe(fnd.get_severity_display()),
            _csv_safe(fnd.standard_clause),
            _csv_safe(fnd.title),
            _csv_safe(fnd.audited_org_unit.name if fnd.audited_org_unit else ""),
            _csv_safe(fnd.assignee.get_full_name() or fnd.assignee.username if fnd.assignee else ""),
            _csv_safe(fnd.response_due_date),
            _csv_safe(fnd.response_received_date),
            _csv_safe(fnd.get_status_display()),
            _csv_safe(fnd.linked_capa.number if fnd.linked_capa else ""),
            _csv_safe(fnd.closed_date),
        ])

    return response
