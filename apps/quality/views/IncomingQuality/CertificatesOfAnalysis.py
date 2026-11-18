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
from apps.quality.forms.IncomingQuality.CertificatesOfAnalysis import (
    CertificateOfAnalysisForm,
)
from apps.quality.models.IncomingQuality.CertificatesOfAnalysis import (
    CertificateOfAnalysis,
)

PAGE_SIZE = 15


def _csv_safe(val):
    if val is None:
        return ""
    s = str(val)
    if s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + s
    return s


@login_required
def certificate_of_analysis_list(request):
    qs = CertificateOfAnalysis.objects.filter(tenant=request.tenant).select_related(
        "supplier", "inspection_lot", "inspection_plan", "verified_by"
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(certificate_number__icontains=search_query)
            | Q(lot_number__icontains=search_query)
            | Q(item_code__icontains=search_query)
            | Q(item_name__icontains=search_query)
            | Q(supplier__name__icontains=search_query)
            | Q(manufacturer_name__icontains=search_query)
        )

    current_status = request.GET.get("status", "").strip()
    if current_status:
        qs = qs.filter(status=current_status)

    current_within_spec = request.GET.get("within_spec", "").strip()
    if current_within_spec == "yes":
        qs = qs.filter(is_within_spec=True)
    elif current_within_spec == "no":
        qs = qs.filter(is_within_spec=False)

    current_supplier = request.GET.get("supplier", "").strip()
    if current_supplier.isdigit():
        qs = qs.filter(supplier_id=int(current_supplier))

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    suppliers = list(
        Party.objects.filter(
            tenant=request.tenant, roles__role__in=("supplier", "vendor")
        ).only("id", "name").distinct().order_by("name")
    )

    context = {
        "coas": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": paginator.count,
        "status_choices": CertificateOfAnalysis.STATUS_CHOICES,
        "suppliers": suppliers,
        "current_status": current_status,
        "current_within_spec": current_within_spec,
        "current_supplier": current_supplier,
        "search_query": search_query,
    }
    return render(request, "quality/incoming_quality/certificate_of_analysis/list.html", context)


@login_required
def certificate_of_analysis_detail(request, pk):
    coa = get_object_or_404(
        CertificateOfAnalysis.objects.filter(tenant=request.tenant).select_related(
            "supplier", "inspection_lot", "inspection_plan", "verified_by", "supporting_document"
        ),
        pk=pk,
    )
    context = {
        "coa": coa,
        "obj": coa,
        "status_css": CertificateOfAnalysis.STATUS_CSS,
    }
    return render(request, "quality/incoming_quality/certificate_of_analysis/detail.html", context)


@login_required
def certificate_of_analysis_create(request):
    if request.method == "POST":
        form = CertificateOfAnalysisForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            coa = form.save()
            write_audit_log(request.user, coa, "create", tenant=request.tenant)
            messages.success(request, f"Certificate of Analysis {coa.number} recorded successfully.")
            return redirect("quality:certificate_of_analysis_detail", pk=coa.pk)
    else:
        form = CertificateOfAnalysisForm(tenant=request.tenant)

    return render(
        request,
        "quality/incoming_quality/certificate_of_analysis/form.html",
        {"form": form, "title": "Intake Certificate of Analysis"},
    )


@login_required
def certificate_of_analysis_edit(request, pk):
    coa = get_object_or_404(CertificateOfAnalysis.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = CertificateOfAnalysisForm(request.POST, instance=coa, tenant=request.tenant)
        if form.is_valid():
            coa = form.save()
            write_audit_log(request.user, coa, "update", tenant=request.tenant)
            messages.success(request, f"Certificate of Analysis {coa.number} updated successfully.")
            return redirect("quality:certificate_of_analysis_detail", pk=coa.pk)
    else:
        form = CertificateOfAnalysisForm(instance=coa, tenant=request.tenant)

    return render(
        request,
        "quality/incoming_quality/certificate_of_analysis/form.html",
        {"form": form, "coa": coa, "obj": coa, "title": f"Edit {coa.number}"},
    )


@require_POST
@login_required
@tenant_admin_required
def certificate_of_analysis_delete(request, pk):
    coa = get_object_or_404(CertificateOfAnalysis.objects.filter(tenant=request.tenant), pk=pk)
    num = coa.number
    write_audit_log(request.user, coa, "delete", tenant=request.tenant)
    coa.delete()
    messages.success(request, f"Certificate of Analysis {num} was deleted.")
    return redirect("quality:certificate_of_analysis_list")


@require_POST
@login_required
def certificate_of_analysis_verify(request, pk):
    coa = get_object_or_404(CertificateOfAnalysis.objects.filter(tenant=request.tenant), pk=pk)
    coa.verify_specifications()
    coa.verified_by = request.user
    coa.verified_at = timezone.now()
    coa.save()

    write_audit_log(request.user, coa, "verify", tenant=request.tenant)
    if coa.is_within_spec:
        messages.success(request, f"CoA {coa.number} verified compliant (0 exceptions).")
    else:
        messages.warning(
            request,
            f"CoA {coa.number} verification completed: {coa.variance_count} parameter exception(s) detected.",
        )
    return redirect("quality:certificate_of_analysis_detail", pk=coa.pk)


@login_required
def certificate_of_analysis_export(request):
    qs = CertificateOfAnalysis.objects.filter(tenant=request.tenant).select_related("supplier")

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(certificate_number__icontains=search_query)
            | Q(lot_number__icontains=search_query)
            | Q(item_code__icontains=search_query)
            | Q(item_name__icontains=search_query)
        )

    current_status = request.GET.get("status", "").strip()
    if current_status:
        qs = qs.filter(status=current_status)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="certificates_of_analysis.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Record Number",
        "Supplier CoA #",
        "Item Code",
        "Item Name",
        "Lot Number",
        "Supplier",
        "Manufacturer",
        "Within Spec",
        "Variances",
        "Status",
        "Verified At",
        "Created At",
    ])

    for c in qs.iterator(chunk_size=1000):
        writer.writerow([
            _csv_safe(c.number),
            _csv_safe(c.certificate_number),
            _csv_safe(c.item_code),
            _csv_safe(c.item_name),
            _csv_safe(c.lot_number),
            _csv_safe(c.supplier.name if c.supplier else ""),
            _csv_safe(c.manufacturer_name),
            _csv_safe("Yes" if c.is_within_spec else "No"),
            _csv_safe(c.variance_count),
            _csv_safe(c.get_status_display()),
            _csv_safe(c.verified_at.strftime("%Y-%m-%d %H:%M") if c.verified_at else ""),
            _csv_safe(c.created_at.strftime("%Y-%m-%d")),
        ])

    return response
