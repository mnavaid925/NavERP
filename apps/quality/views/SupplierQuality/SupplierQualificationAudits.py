import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.quality.forms.SupplierQuality.SupplierQualificationAudits import (
    SupplierQualificationAuditForm,
)
from apps.quality.models.SupplierQuality.SupplierQualificationAudits import (
    SupplierQualificationAudit,
)

PAGE_SIZE = 15


def _csv_safe(val):
    if val is None:
        return ""
    s = str(val)
    if s.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + s
    return s


@login_required
def supplier_qualification_audit_list(request):
    qs = SupplierQualificationAudit.objects.filter(tenant=request.tenant).select_related(
        "supplier", "lead_auditor", "quality_agreement"
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(supplier__name__icontains=search_query)
            | Q(scope_commodities__icontains=search_query)
            | Q(notes__icontains=search_query)
        )

    current_status = request.GET.get("status", "").strip()
    if current_status:
        qs = qs.filter(qualification_status=current_status)

    current_tier = request.GET.get("tier", "").strip()
    if current_tier:
        qs = qs.filter(criticality_tier=current_tier)

    current_result = request.GET.get("result", "").strip()
    if current_result:
        qs = qs.filter(audit_result=current_result)

    current_supplier = request.GET.get("supplier", "").strip()
    if current_supplier.isdigit():
        qs = qs.filter(supplier_id=int(current_supplier))

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    audits = paginator.get_page(page_number)

    suppliers = Party.objects.filter(
        tenant=request.tenant, roles__role__in=("supplier", "vendor")
    ).distinct().order_by("name")
    if not suppliers.exists():
        suppliers = Party.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "audits": audits,
        "status_choices": SupplierQualificationAudit.QUALIFICATION_STATUS_CHOICES,
        "tier_choices": SupplierQualificationAudit.CRITICALITY_TIER_CHOICES,
        "result_choices": SupplierQualificationAudit.AUDIT_RESULT_CHOICES,
        "suppliers": suppliers,
        "search_query": search_query,
        "current_status": current_status,
        "current_tier": current_tier,
        "current_result": current_result,
        "current_supplier": current_supplier,
    }
    return render(
        request,
        "quality/supplierquality/supplier_qualification_audit/list.html",
        context,
    )


@login_required
def supplier_qualification_audit_detail(request, pk):
    audit = get_object_or_404(
        SupplierQualificationAudit.objects.filter(tenant=request.tenant).select_related(
            "supplier", "lead_auditor", "quality_agreement"
        ),
        pk=pk,
    )
    scars = getattr(audit, "triggered_scars", None)
    scars_qs = scars.filter(tenant=request.tenant).order_by("-created_at") if scars else []
    scns = getattr(audit, "change_notifications", None)
    scns_qs = scns.filter(tenant=request.tenant).order_by("-created_at") if scns else []

    context = {
        "audit": audit,
        "scars": scars_qs,
        "scns": scns_qs,
    }
    return render(
        request,
        "quality/supplierquality/supplier_qualification_audit/detail.html",
        context,
    )


@login_required
def supplier_qualification_audit_create(request):
    if request.method == "POST":
        form = SupplierQualificationAuditForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            audit = form.save(commit=False)
            audit.tenant = request.tenant
            audit.save()
            form.save_m2m()
            write_audit_log(request.user, audit, "create", tenant=request.tenant)
            messages.success(request, f"Audit {audit.number} created successfully.")
            return redirect("quality:supplier_qualification_audit_detail", pk=audit.pk)
    else:
        form = SupplierQualificationAuditForm(tenant=request.tenant)
    context = {
        "form": form,
        "is_edit": False,
        "audit": None,
    }
    return render(
        request,
        "quality/supplierquality/supplier_qualification_audit/form.html",
        context,
    )


@login_required
def supplier_qualification_audit_edit(request, pk):
    audit = get_object_or_404(SupplierQualificationAudit, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = SupplierQualificationAuditForm(request.POST, instance=audit, tenant=request.tenant)
        if form.is_valid():
            audit = form.save()
            write_audit_log(request.user, audit, "update", tenant=request.tenant)
            messages.success(request, f"Audit {audit.number} updated successfully.")
            return redirect("quality:supplier_qualification_audit_detail", pk=audit.pk)
    else:
        form = SupplierQualificationAuditForm(instance=audit, tenant=request.tenant)
    context = {
        "form": form,
        "is_edit": True,
        "audit": audit,
    }
    return render(
        request,
        "quality/supplierquality/supplier_qualification_audit/form.html",
        context,
    )


@login_required
@require_POST
@tenant_admin_required
def supplier_qualification_audit_delete(request, pk):
    audit = get_object_or_404(SupplierQualificationAudit, pk=pk, tenant=request.tenant)
    write_audit_log(request.user, audit, "delete", tenant=request.tenant)
    audit.delete()
    messages.success(request, f"Audit {audit.number} deleted successfully.")
    return redirect("quality:supplier_qualification_audit_list")


@login_required
def supplier_qualification_audit_export(request):
    qs = SupplierQualificationAudit.objects.filter(tenant=request.tenant).select_related("supplier", "lead_auditor")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="supplier_qualification_audits.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Audit Number",
        "Supplier",
        "Assessment Type",
        "Criticality Tier",
        "Method",
        "Status",
        "Result",
        "Score",
        "Dock to Stock",
        "Requires CoA",
        "Lead Auditor",
        "Audit Date",
        "Next Due Date",
    ])
    for obj in qs:
        writer.writerow([
            _csv_safe(obj.number),
            _csv_safe(obj.supplier.name if obj.supplier else ""),
            _csv_safe(obj.get_assessment_type_display()),
            _csv_safe(obj.get_criticality_tier_display()),
            _csv_safe(obj.get_audit_method_display()),
            _csv_safe(obj.get_qualification_status_display()),
            _csv_safe(obj.get_audit_result_display()),
            _csv_safe(obj.score),
            _csv_safe("Yes" if obj.dock_to_stock_eligible else "No"),
            _csv_safe("Yes" if obj.requires_coa else "No"),
            _csv_safe(obj.lead_auditor.get_full_name() if obj.lead_auditor else ""),
            _csv_safe(obj.audit_date),
            _csv_safe(obj.next_audit_due_date),
        ])
    return response


@login_required
@require_POST
@tenant_admin_required
def supplier_qualification_audit_status(request, pk):
    audit = get_object_or_404(SupplierQualificationAudit, pk=pk, tenant=request.tenant)
    new_status = request.POST.get("status", "").strip()
    valid_statuses = dict(SupplierQualificationAudit.QUALIFICATION_STATUS_CHOICES)
    if new_status in valid_statuses:
        old_status = audit.qualification_status
        audit.qualification_status = new_status
        audit.save(update_fields=["qualification_status", "updated_at"])
        write_audit_log(
            request.user,
            audit,
            "advance",
            tenant=request.tenant,
        )
        messages.success(request, f"Supplier AVL status updated from {old_status} to {valid_statuses[new_status]}.")
    else:
        messages.error(request, "Invalid qualification status provided.")
    return redirect("quality:supplier_qualification_audit_detail", pk=audit.pk)
