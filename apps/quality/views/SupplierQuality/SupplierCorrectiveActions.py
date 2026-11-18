import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import crud_create, crud_delete, crud_edit
from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.quality.forms.SupplierQuality.SupplierCorrectiveActions import (
    SupplierCorrectiveActionForm,
)
from apps.quality.models.SupplierQuality.SupplierCorrectiveActions import (
    SupplierCorrectiveAction,
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
def supplier_corrective_action_list(request):
    qs = SupplierCorrectiveAction.objects.filter(tenant=request.tenant).select_related(
        "supplier", "issued_by", "verified_by", "purchase_order", "non_conformance"
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(title__icontains=search_query)
            | Q(supplier__name__icontains=search_query)
            | Q(defect_summary__icontains=search_query)
            | Q(affected_item_code__icontains=search_query)
        )

    current_status = request.GET.get("status", "").strip()
    if current_status:
        qs = qs.filter(status=current_status)

    current_severity = request.GET.get("severity", "").strip()
    if current_severity:
        qs = qs.filter(severity=current_severity)

    current_category = request.GET.get("category", "").strip()
    if current_category:
        qs = qs.filter(root_cause_category=current_category)

    current_supplier = request.GET.get("supplier", "").strip()
    if current_supplier.isdigit():
        qs = qs.filter(supplier_id=int(current_supplier))

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    scars = paginator.get_page(page_number)

    suppliers = Party.objects.filter(
        tenant=request.tenant, roles__role__in=("supplier", "vendor")
    ).distinct().order_by("name")
    if not suppliers.exists():
        suppliers = Party.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "scars": scars,
        "severity_choices": SupplierCorrectiveAction.SEVERITY_CHOICES,
        "status_choices": SupplierCorrectiveAction.STATUS_CHOICES,
        "category_choices": SupplierCorrectiveAction.ROOT_CAUSE_CATEGORY_CHOICES,
        "suppliers": suppliers,
        "search_query": search_query,
        "current_status": current_status,
        "current_severity": current_severity,
        "current_category": current_category,
        "current_supplier": current_supplier,
    }
    return render(
        request,
        "quality/supplierquality/supplier_corrective_action/list.html",
        context,
    )


@login_required
def supplier_corrective_action_detail(request, pk):
    scar = get_object_or_404(
        SupplierCorrectiveAction.objects.filter(tenant=request.tenant).select_related(
            "supplier",
            "issued_by",
            "verified_by",
            "purchase_order",
            "non_conformance",
            "qualification_audit",
            "internal_capa",
        ),
        pk=pk,
    )
    context = {
        "scar": scar,
    }
    return render(
        request,
        "quality/supplierquality/supplier_corrective_action/detail.html",
        context,
    )


@login_required
def supplier_corrective_action_create(request):
    if request.method == "POST":
        form = SupplierCorrectiveActionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            scar = form.save(commit=False)
            scar.tenant = request.tenant
            scar.save()
            form.save_m2m()
            write_audit_log(request.user, scar, "create", tenant=request.tenant)
            messages.success(request, f"SCAR {scar.number} created successfully.")
            return redirect("quality:supplier_corrective_action_detail", pk=scar.pk)
    else:
        form = SupplierCorrectiveActionForm(tenant=request.tenant)
    context = {
        "form": form,
        "is_edit": False,
        "scar": None,
    }
    return render(
        request,
        "quality/supplierquality/supplier_corrective_action/form.html",
        context,
    )


@login_required
def supplier_corrective_action_edit(request, pk):
    scar = get_object_or_404(SupplierCorrectiveAction, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = SupplierCorrectiveActionForm(request.POST, instance=scar, tenant=request.tenant)
        if form.is_valid():
            scar = form.save()
            write_audit_log(request.user, scar, "update", tenant=request.tenant)
            messages.success(request, f"SCAR {scar.number} updated successfully.")
            return redirect("quality:supplier_corrective_action_detail", pk=scar.pk)
    else:
        form = SupplierCorrectiveActionForm(instance=scar, tenant=request.tenant)
    context = {
        "form": form,
        "is_edit": True,
        "scar": scar,
    }
    return render(
        request,
        "quality/supplierquality/supplier_corrective_action/form.html",
        context,
    )


@login_required
@require_POST
@tenant_admin_required
def supplier_corrective_action_delete(request, pk):
    scar = get_object_or_404(SupplierCorrectiveAction, pk=pk, tenant=request.tenant)
    write_audit_log(request.user, scar, "delete", tenant=request.tenant)
    scar.delete()
    messages.success(request, f"SCAR {scar.number} deleted successfully.")
    return redirect("quality:supplier_corrective_action_list")


@login_required
def supplier_corrective_action_export(request):
    qs = SupplierCorrectiveAction.objects.filter(tenant=request.tenant).select_related("supplier", "issued_by")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="supplier_corrective_actions.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "SCAR #",
        "Supplier",
        "Title",
        "Severity",
        "Status",
        "Root Cause Category",
        "Item Code",
        "Item Name",
        "Lots",
        "Issued Date",
        "Response Due Date",
        "Effective?",
        "Closed Date",
    ])
    for obj in qs:
        writer.writerow([
            _csv_safe(obj.number),
            _csv_safe(obj.supplier.name if obj.supplier else ""),
            _csv_safe(obj.title),
            _csv_safe(obj.get_severity_display()),
            _csv_safe(obj.get_status_display()),
            _csv_safe(obj.get_root_cause_category_display()),
            _csv_safe(obj.affected_item_code),
            _csv_safe(obj.affected_item_name),
            _csv_safe(obj.affected_lots),
            _csv_safe(obj.issued_date),
            _csv_safe(obj.response_due_date),
            _csv_safe("Yes" if obj.is_effective else ("No" if obj.is_effective is False else "")),
            _csv_safe(obj.closed_at),
        ])
    return response


@login_required
@require_POST
@tenant_admin_required
def supplier_corrective_action_status(request, pk):
    scar = get_object_or_404(SupplierCorrectiveAction, pk=pk, tenant=request.tenant)
    new_status = request.POST.get("status", "").strip()
    valid_statuses = dict(SupplierCorrectiveAction.STATUS_CHOICES)
    if new_status in valid_statuses:
        old_status = scar.status
        scar.status = new_status
        update_fields = ["status", "updated_at"]
        action_verb = "advance"
        if new_status == "closed":
            scar.closed_at = timezone.now().date()
            update_fields.append("closed_at")
            action_verb = "close"
        scar.save(update_fields=update_fields)
        write_audit_log(
            request.user,
            scar,
            action_verb,
            tenant=request.tenant,
        )
        messages.success(request, f"SCAR status advanced from {old_status} to {valid_statuses[new_status]}.")
    else:
        messages.error(request, "Invalid SCAR status provided.")
    return redirect("quality:supplier_corrective_action_detail", pk=scar.pk)
