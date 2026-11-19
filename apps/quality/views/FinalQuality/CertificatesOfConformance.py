import csv
import hashlib

from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.FinalQuality.CertificatesOfConformance import CertificateOfConformanceForm
from apps.quality.models.FinalQuality.CertificatesOfConformance import CertificateOfConformance

PAGE_SIZE = 15


def _csv_safe(val):
    if val is None:
        return ""
    s = str(val)
    if s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + s
    return s


@login_required
def certificate_of_conformance_list(request):
    qs = CertificateOfConformance.objects.filter(tenant=request.tenant).select_related(
        "customer", "sales_order", "shipment", "inspection_lot", "authorized_signatory"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(item_code__icontains=q)
            | Q(item_name__icontains=q)
            | Q(lot_number__icontains=q)
            | Q(customer_po_number__icontains=q)
            | Q(sales_order_number__icontains=q)
            | Q(shipment_number__icontains=q)
            | Q(customer__name__icontains=q)
        )

    cert_type = request.GET.get("type", "").strip()
    if cert_type:
        qs = qs.filter(certificate_type=cert_type)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    customer_id = request.GET.get("customer", "").strip()
    if customer_id.isdigit():
        qs = qs.filter(customer_id=int(customer_id))

    stats = CertificateOfConformance.objects.filter(tenant=request.tenant).aggregate(
        total_count=Count("id"),
        signed_count=Count("id", filter=Q(status="approved_signed")),
        review_count=Count("id", filter=Q(status="under_review")),
    )

    customers = []
    try:
        Party = apps.get_model("core", "Party")
        customers = list(Party.objects.filter(tenant=request.tenant).only("id", "name").order_by("name"))
    except LookupError:
        pass

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "certificates": page_obj,
        "paginator": paginator,
        "q": q,
        "type": cert_type,
        "status": status,
        "customer_id": customer_id,
        "type_choices": CertificateOfConformance.CERTIFICATE_TYPE_CHOICES,
        "status_choices": CertificateOfConformance.STATUS_CHOICES,
        "customers": customers,
        "total_count": stats["total_count"] or 0,
        "signed_count": stats["signed_count"] or 0,
        "review_count": stats["review_count"] or 0,
        "TYPE_CSS": CertificateOfConformance.TYPE_CSS,
        "STATUS_CSS": CertificateOfConformance.STATUS_CSS,
    }
    return render(request, "quality/finalquality/certificate_of_conformance/list.html", context)


@login_required
def certificate_of_conformance_detail(request, pk):
    certificate = get_object_or_404(
        CertificateOfConformance.objects.filter(tenant=request.tenant).select_related(
            "customer", "sales_order", "shipment", "inspection_lot", "authorized_signatory"
        ),
        pk=pk,
    )
    context = {
        "certificate": certificate,
        "TYPE_CSS": CertificateOfConformance.TYPE_CSS,
        "STATUS_CSS": CertificateOfConformance.STATUS_CSS,
    }
    return render(request, "quality/finalquality/certificate_of_conformance/detail.html", context)


@login_required
def certificate_of_conformance_create(request):
    if request.method == "POST":
        form = CertificateOfConformanceForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            certificate = form.save(commit=False)
            certificate.tenant = request.tenant
            certificate.save()
            write_audit_log(request.user, certificate, "create", tenant=request.tenant)
            messages.success(request, f"Certificate of Conformance {certificate.number} created successfully.")
            return redirect("quality:certificate_of_conformance_detail", pk=certificate.pk)
    else:
        form = CertificateOfConformanceForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
        "certificate": None,
        "title": "New Certificate of Conformance",
    }
    return render(request, "quality/finalquality/certificate_of_conformance/form.html", context)


@login_required
def certificate_of_conformance_edit(request, pk):
    certificate = get_object_or_404(CertificateOfConformance, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = CertificateOfConformanceForm(request.POST, instance=certificate, tenant=request.tenant)
        if form.is_valid():
            certificate = form.save()
            write_audit_log(request.user, certificate, "update", tenant=request.tenant)
            messages.success(request, f"Certificate of Conformance {certificate.number} updated successfully.")
            return redirect("quality:certificate_of_conformance_detail", pk=certificate.pk)
    else:
        form = CertificateOfConformanceForm(instance=certificate, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "certificate": certificate,
        "title": f"Edit Certificate: {certificate.number}",
    }
    return render(request, "quality/finalquality/certificate_of_conformance/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def certificate_of_conformance_delete(request, pk):
    certificate = get_object_or_404(CertificateOfConformance, pk=pk, tenant=request.tenant)
    number = certificate.number
    write_audit_log(request.user, certificate, "delete", tenant=request.tenant)
    certificate.delete()
    messages.success(request, f"Certificate {number} deleted successfully.")
    return redirect("quality:certificate_of_conformance_list")


@login_required
@require_POST
def certificate_of_conformance_sign(request, pk):
    certificate = get_object_or_404(CertificateOfConformance, pk=pk, tenant=request.tenant)
    now = timezone.now()
    raw_stamp = f"{certificate.number}:{certificate.tenant_id}:{request.user.id}:{now.isoformat()}"
    digest = hashlib.sha256(raw_stamp.encode("utf-8")).hexdigest()

    certificate.authorized_signatory = request.user
    certificate.signed_date = now.date()
    certificate.digital_signature_hash = digest
    certificate.status = "approved_signed"
    certificate.save()

    write_audit_log(request.user, certificate, "sign", tenant=request.tenant)
    messages.success(request, f"Certificate {certificate.number} has been digitally signed and approved.")
    return redirect("quality:certificate_of_conformance_detail", pk=certificate.pk)


@login_required
def certificate_of_conformance_export(request):
    write_audit_log(request.user, None, "export", changes={"model": "CertificateOfConformance"}, tenant=request.tenant)
    qs = CertificateOfConformance.objects.filter(tenant=request.tenant).order_by("-created_at")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="certificates_of_conformance.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Certificate Number",
        "Title",
        "Type",
        "Status",
        "Customer",
        "Customer PO",
        "Item Code",
        "Item Name",
        "Batch/Lot",
        "Certified Qty",
        "QR Code",
        "Signed Date",
        "Signatory",
    ])
    for item in qs:
        writer.writerow([
            _csv_safe(item.number),
            _csv_safe(item.title),
            _csv_safe(item.get_certificate_type_display()),
            _csv_safe(item.get_status_display()),
            _csv_safe(item.customer.name if item.customer else ""),
            _csv_safe(item.customer_po_number),
            _csv_safe(item.item_code),
            _csv_safe(item.item_name),
            _csv_safe(item.lot_number),
            _csv_safe(item.certified_quantity),
            _csv_safe(item.qr_verification_code),
            _csv_safe(item.signed_date),
            _csv_safe(item.authorized_signatory.get_full_name() if item.authorized_signatory else ""),
        ])

    return response
