import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.quality.forms.SupplierQuality.SupplierChangeNotifications import (
    SupplierChangeNotificationForm,
)
from apps.quality.models.SupplierQuality.SupplierChangeNotifications import (
    SupplierChangeNotification,
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
def supplier_change_notification_list(request):
    qs = SupplierChangeNotification.objects.filter(tenant=request.tenant).select_related(
        "supplier", "approved_by", "evaluated_by", "design_project", "requalification_audit"
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(title__icontains=search_query)
            | Q(supplier_scn_number__icontains=search_query)
            | Q(supplier__name__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(affected_item_code__icontains=search_query)
        )

    current_status = request.GET.get("status", "").strip()
    if current_status:
        qs = qs.filter(status=current_status)

    current_category = request.GET.get("category", "").strip()
    if current_category:
        qs = qs.filter(change_category=current_category)

    current_risk = request.GET.get("risk", "").strip()
    if current_risk:
        qs = qs.filter(risk_level=current_risk)

    current_disposition = request.GET.get("disposition", "").strip()
    if current_disposition:
        qs = qs.filter(disposition=current_disposition)

    current_supplier = request.GET.get("supplier", "").strip()
    if current_supplier.isdigit():
        qs = qs.filter(supplier_id=int(current_supplier))

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    scns = paginator.get_page(page_number)

    suppliers = list(
        Party.objects.filter(
            tenant=request.tenant, roles__role__in=("supplier", "vendor")
        ).only("id", "name").distinct().order_by("name")
    )
    if not suppliers:
        suppliers = list(Party.objects.filter(tenant=request.tenant).only("id", "name").order_by("name"))

    context = {
        "scns": scns,
        "category_choices": SupplierChangeNotification.CHANGE_CATEGORY_CHOICES,
        "risk_choices": SupplierChangeNotification.RISK_LEVEL_CHOICES,
        "status_choices": SupplierChangeNotification.STATUS_CHOICES,
        "disposition_choices": SupplierChangeNotification.DISPOSITION_CHOICES,
        "suppliers": suppliers,
        "search_query": search_query,
        "current_status": current_status,
        "current_category": current_category,
        "current_risk": current_risk,
        "current_disposition": current_disposition,
        "current_supplier": current_supplier,
    }
    return render(
        request,
        "quality/supplierquality/supplier_change_notification/list.html",
        context,
    )


@login_required
def supplier_change_notification_detail(request, pk):
    scn = get_object_or_404(
        SupplierChangeNotification.objects.filter(tenant=request.tenant).select_related(
            "supplier", "approved_by", "evaluated_by", "design_project", "requalification_audit"
        ),
        pk=pk,
    )
    context = {
        "scn": scn,
    }
    return render(
        request,
        "quality/supplierquality/supplier_change_notification/detail.html",
        context,
    )


@login_required
def supplier_change_notification_create(request):
    if request.method == "POST":
        form = SupplierChangeNotificationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            scn = form.save(commit=False)
            scn.tenant = request.tenant
            scn.save()
            form.save_m2m()
            write_audit_log(request.user, scn, "create", tenant=request.tenant)
            messages.success(request, f"SCN {scn.number} logged successfully.")
            return redirect("quality:supplier_change_notification_detail", pk=scn.pk)
    else:
        form = SupplierChangeNotificationForm(tenant=request.tenant)
    context = {
        "form": form,
        "is_edit": False,
        "scn": None,
    }
    return render(
        request,
        "quality/supplierquality/supplier_change_notification/form.html",
        context,
    )


@login_required
def supplier_change_notification_edit(request, pk):
    scn = get_object_or_404(SupplierChangeNotification, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = SupplierChangeNotificationForm(request.POST, instance=scn, tenant=request.tenant)
        if form.is_valid():
            scn = form.save()
            write_audit_log(request.user, scn, "update", tenant=request.tenant)
            messages.success(request, f"SCN {scn.number} updated successfully.")
            return redirect("quality:supplier_change_notification_detail", pk=scn.pk)
    else:
        form = SupplierChangeNotificationForm(instance=scn, tenant=request.tenant)
    context = {
        "form": form,
        "is_edit": True,
        "scn": scn,
    }
    return render(
        request,
        "quality/supplierquality/supplier_change_notification/form.html",
        context,
    )


@login_required
@require_POST
@tenant_admin_required
def supplier_change_notification_delete(request, pk):
    scn = get_object_or_404(SupplierChangeNotification, pk=pk, tenant=request.tenant)
    write_audit_log(request.user, scn, "delete", tenant=request.tenant)
    scn.delete()
    messages.success(request, f"SCN {scn.number} deleted successfully.")
    return redirect("quality:supplier_change_notification_list")


@login_required
def supplier_change_notification_export(request):
    qs = SupplierChangeNotification.objects.filter(tenant=request.tenant).select_related("supplier", "approved_by")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="supplier_change_notifications.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "SCN #",
        "Supplier",
        "Title",
        "Vendor Ref #",
        "Category",
        "Risk Level",
        "Status",
        "Disposition",
        "Effective Date",
        "Item Code",
        "Affects FFF",
        "Requalification Required",
        "Regulatory Filing",
    ])
    for obj in qs:
        writer.writerow([
            _csv_safe(obj.number),
            _csv_safe(obj.supplier.name if obj.supplier else ""),
            _csv_safe(obj.title),
            _csv_safe(obj.supplier_scn_number),
            _csv_safe(obj.get_change_category_display()),
            _csv_safe(obj.get_risk_level_display()),
            _csv_safe(obj.get_status_display()),
            _csv_safe(obj.get_disposition_display()),
            _csv_safe(obj.proposed_effective_date),
            _csv_safe(obj.affected_item_code),
            _csv_safe("Yes" if obj.affects_form_fit_function else "No"),
            _csv_safe("Yes" if obj.requires_requalification else "No"),
            _csv_safe("Yes" if obj.requires_regulatory_filing else "No"),
        ])
    return response


@login_required
@require_POST
@tenant_admin_required
def supplier_change_notification_disposition(request, pk):
    scn = get_object_or_404(SupplierChangeNotification, pk=pk, tenant=request.tenant)
    new_disp = request.POST.get("disposition", "").strip()
    valid_disps = dict(SupplierChangeNotification.DISPOSITION_CHOICES)
    if new_disp in valid_disps:
        scn.disposition = new_disp
        scn.disposition_date = timezone.now().date()
        scn.approved_by = request.user
        update_fields = ["disposition", "disposition_date", "approved_by", "updated_at"]

        action_verb = "advance"
        if new_disp == "approved":
            scn.status = "approved"
            update_fields.append("status")
            action_verb = "approve"
        elif new_disp == "rejected":
            scn.status = "rejected"
            update_fields.append("status")
            action_verb = "reject"
        elif new_disp == "conditional_approval":
            scn.status = "conditional_approval"
            update_fields.append("status")

        notes = request.POST.get("disposition_notes", "").strip()
        if notes:
            scn.disposition_notes = notes
            update_fields.append("disposition_notes")

        scn.save(update_fields=update_fields)
        write_audit_log(
            request.user,
            scn,
            action_verb,
            tenant=request.tenant,
        )
        messages.success(request, f"SCN disposition updated to {valid_disps[new_disp]}.")
    else:
        messages.error(request, "Invalid disposition value provided.")
    return redirect("quality:supplier_change_notification_detail", pk=scn.pk)
