import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.FinalQuality.PackagingLabelVerifications import PackagingLabelVerificationForm
from apps.quality.models.FinalQuality.PackagingLabelVerifications import PackagingLabelVerification

PAGE_SIZE = 15


def _csv_safe(val):
    if val is None:
        return ""
    s = str(val)
    if s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + s
    return s


@login_required
def packaging_label_verification_list(request):
    qs = PackagingLabelVerification.objects.filter(tenant=request.tenant).select_related(
        "artwork_master", "inspection_lot", "shipment", "verifier"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(item_code__icontains=q)
            | Q(item_name__icontains=q)
            | Q(lot_number__icontains=q)
            | Q(label_part_number__icontains=q)
            | Q(scanned_barcode_data__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    disposition = request.GET.get("disposition", "").strip()
    if disposition:
        qs = qs.filter(disposition=disposition)

    grade = request.GET.get("grade", "").strip()
    if grade:
        qs = qs.filter(iso_iec_print_grade=grade)

    stats = PackagingLabelVerification.objects.filter(tenant=request.tenant).aggregate(
        total_count=Count("id"),
        verified_count=Count("id", filter=Q(disposition="pass_released")),
        failed_count=Count("id", filter=Q(disposition__in=["relabel_required", "repack_required", "reject_quarantine"])),
    )

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "verifications": page_obj,
        "paginator": paginator,
        "q": q,
        "status": status,
        "disposition": disposition,
        "grade": grade,
        "status_choices": PackagingLabelVerification.STATUS_CHOICES,
        "disposition_choices": PackagingLabelVerification.DISPOSITION_CHOICES,
        "grade_choices": PackagingLabelVerification.ISO_IEC_GRADE_CHOICES,
        "total_count": stats["total_count"] or 0,
        "verified_count": stats["verified_count"] or 0,
        "failed_count": stats["failed_count"] or 0,
        "BARCODE_CSS": PackagingLabelVerification.BARCODE_CSS,
        "GRADE_CSS": PackagingLabelVerification.ISO_IEC_GRADE_CSS,
        "STATUS_CSS": PackagingLabelVerification.STATUS_CSS,
        "DISPOSITION_CSS": PackagingLabelVerification.DISPOSITION_CSS,
    }
    return render(request, "quality/finalquality/packaging_label_verification/list.html", context)


@login_required
def packaging_label_verification_detail(request, pk):
    verification = get_object_or_404(
        PackagingLabelVerification.objects.filter(tenant=request.tenant).select_related(
            "artwork_master", "inspection_lot", "shipment", "verifier"
        ),
        pk=pk,
    )
    context = {
        "verification": verification,
        "BARCODE_CSS": PackagingLabelVerification.BARCODE_CSS,
        "GRADE_CSS": PackagingLabelVerification.ISO_IEC_GRADE_CSS,
        "STATUS_CSS": PackagingLabelVerification.STATUS_CSS,
        "DISPOSITION_CSS": PackagingLabelVerification.DISPOSITION_CSS,
    }
    return render(request, "quality/finalquality/packaging_label_verification/detail.html", context)


@login_required
def packaging_label_verification_create(request):
    if request.method == "POST":
        form = PackagingLabelVerificationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            verification = form.save(commit=False)
            verification.tenant = request.tenant
            verification.save()
            write_audit_log(request.user, verification, "create", tenant=request.tenant)
            messages.success(request, f"Packaging verification {verification.number} created successfully.")
            return redirect("quality:packaging_label_verification_detail", pk=verification.pk)
    else:
        form = PackagingLabelVerificationForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
        "verification": None,
        "title": "New Packaging & Label Verification",
    }
    return render(request, "quality/finalquality/packaging_label_verification/form.html", context)


@login_required
def packaging_label_verification_edit(request, pk):
    verification = get_object_or_404(PackagingLabelVerification, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = PackagingLabelVerificationForm(request.POST, instance=verification, tenant=request.tenant)
        if form.is_valid():
            verification = form.save()
            write_audit_log(request.user, verification, "update", tenant=request.tenant)
            messages.success(request, f"Packaging verification {verification.number} updated successfully.")
            return redirect("quality:packaging_label_verification_detail", pk=verification.pk)
    else:
        form = PackagingLabelVerificationForm(instance=verification, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "verification": verification,
        "title": f"Edit Packaging Verification: {verification.number}",
    }
    return render(request, "quality/finalquality/packaging_label_verification/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def packaging_label_verification_delete(request, pk):
    verification = get_object_or_404(PackagingLabelVerification, pk=pk, tenant=request.tenant)
    number = verification.number
    write_audit_log(request.user, verification, "delete", tenant=request.tenant)
    verification.delete()
    messages.success(request, f"Packaging verification {number} deleted successfully.")
    return redirect("quality:packaging_label_verification_list")


@login_required
def packaging_label_verification_export(request):
    write_audit_log(request.user, PackagingLabelVerification(), "export", tenant=request.tenant)
    qs = PackagingLabelVerification.objects.filter(tenant=request.tenant).order_by("-created_at")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="packaging_label_verifications.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Verification Number",
        "Title",
        "Status",
        "Disposition",
        "Item Code",
        "Item Name",
        "Batch/Lot",
        "Cartons Inspected",
        "Symbology",
        "Scanned Data",
        "ISO/IEC Grade",
        "Content Accurate",
        "Carton Intact",
        "Verifier",
        "Verified Date",
    ])
    for item in qs:
        writer.writerow([
            _csv_safe(item.number),
            _csv_safe(item.title),
            _csv_safe(item.get_status_display()),
            _csv_safe(item.get_disposition_display()),
            _csv_safe(item.item_code),
            _csv_safe(item.item_name),
            _csv_safe(item.lot_number),
            _csv_safe(item.carton_count_inspected),
            _csv_safe(item.get_barcode_symbology_display()),
            _csv_safe(item.scanned_barcode_data),
            _csv_safe(item.get_iso_iec_print_grade_display()),
            "Yes" if item.label_content_accurate else "No",
            "Yes" if item.carton_integrity_intact else "No",
            _csv_safe(item.verifier.get_full_name() if item.verifier else ""),
            _csv_safe(item.verified_date),
        ])

    return response
