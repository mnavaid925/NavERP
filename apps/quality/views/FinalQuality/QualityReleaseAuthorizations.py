import csv

from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.FinalQuality.QualityReleaseAuthorizations import QualityReleaseAuthorizationForm
from apps.quality.models.FinalQuality.QualityReleaseAuthorizations import QualityReleaseAuthorization

PAGE_SIZE = 15


def _csv_safe(val):
    if val is None:
        return ""
    s = str(val)
    if s.startswith(("=", "+", "-", "@", "\t", "\r")) or s.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + s
    return s


@login_required
def quality_release_authorization_list(request):
    qs = QualityReleaseAuthorization.objects.filter(tenant=request.tenant).select_related(
        "customer", "shipment"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(shipment_number__icontains=q)
            | Q(sales_order_number__icontains=q)
            | Q(lot_number__icontains=q)
            | Q(customer__name__icontains=q)
            | Q(carrier_name__icontains=q)
            | Q(tracking_reference__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    disposition = request.GET.get("disposition", "").strip()
    if disposition:
        qs = qs.filter(release_disposition=disposition)

    on_hold = request.GET.get("on_hold", "").strip()
    if on_hold == "1":
        qs = qs.filter(is_on_hold=True)
    elif on_hold == "0":
        qs = qs.filter(is_on_hold=False)

    customer_id = request.GET.get("customer", "").strip()
    if customer_id.isdigit():
        qs = qs.filter(customer_id=int(customer_id))

    stats = QualityReleaseAuthorization.objects.filter(tenant=request.tenant).aggregate(
        total_count=Count("id"),
        authorized_count=Count("id", filter=Q(status="authorized")),
        hold_count=Count("id", filter=Q(is_on_hold=True)),
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
        "releases": page_obj,
        "paginator": paginator,
        "q": q,
        "status": status,
        "disposition": disposition,
        "on_hold": on_hold,
        "customer_id": customer_id,
        "status_choices": QualityReleaseAuthorization.STATUS_CHOICES,
        "disposition_choices": QualityReleaseAuthorization.RELEASE_DISPOSITION_CHOICES,
        "customers": customers,
        "total_count": stats["total_count"] or 0,
        "authorized_count": stats["authorized_count"] or 0,
        "hold_count": stats["hold_count"] or 0,
        "STATUS_CSS": QualityReleaseAuthorization.STATUS_CSS,
        "DISPOSITION_CSS": QualityReleaseAuthorization.RELEASE_DISPOSITION_CSS,
    }
    return render(request, "quality/finalquality/quality_release_authorization/list.html", context)


@login_required
def quality_release_authorization_detail(request, pk):
    release = get_object_or_404(
        QualityReleaseAuthorization.objects.filter(tenant=request.tenant).select_related(
            "customer", "shipment", "sales_order", "inspection_lot",
            "certificate_of_conformance", "packaging_verification", "releasing_officer"
        ),
        pk=pk,
    )
    context = {
        "release": release,
        "STATUS_CSS": QualityReleaseAuthorization.STATUS_CSS,
        "DISPOSITION_CSS": QualityReleaseAuthorization.RELEASE_DISPOSITION_CSS,
    }
    return render(request, "quality/finalquality/quality_release_authorization/detail.html", context)


@login_required
def quality_release_authorization_create(request):
    if request.method == "POST":
        form = QualityReleaseAuthorizationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            release = form.save(commit=False)
            release.tenant = request.tenant
            release.save()
            write_audit_log(request.user, release, "create", tenant=request.tenant)
            messages.success(request, f"Quality release {release.number} created successfully.")
            return redirect("quality:quality_release_authorization_detail", pk=release.pk)
    else:
        form = QualityReleaseAuthorizationForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
        "release": None,
        "title": "New Quality Release Authorization",
    }
    return render(request, "quality/finalquality/quality_release_authorization/form.html", context)


@login_required
def quality_release_authorization_edit(request, pk):
    release = get_object_or_404(QualityReleaseAuthorization, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = QualityReleaseAuthorizationForm(request.POST, instance=release, tenant=request.tenant)
        if form.is_valid():
            release = form.save()
            write_audit_log(request.user, release, "update", tenant=request.tenant)
            messages.success(request, f"Quality release {release.number} updated successfully.")
            return redirect("quality:quality_release_authorization_detail", pk=release.pk)
    else:
        form = QualityReleaseAuthorizationForm(instance=release, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "release": release,
        "title": f"Edit Quality Release: {release.number}",
    }
    return render(request, "quality/finalquality/quality_release_authorization/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def quality_release_authorization_delete(request, pk):
    release = get_object_or_404(QualityReleaseAuthorization, pk=pk, tenant=request.tenant)
    if release.status == "authorized":
        messages.error(request, f"Authorized quality release {release.number} cannot be deleted. Revoke or place on hold instead to preserve traceability.")
        return redirect("quality:quality_release_authorization_detail", pk=release.pk)
    number = release.number
    write_audit_log(request.user, release, "delete", tenant=request.tenant)
    release.delete()
    messages.success(request, f"Quality release {number} deleted successfully.")
    return redirect("quality:quality_release_authorization_list")


@login_required
@require_POST
@tenant_admin_required
def quality_release_authorization_toggle_hold(request, pk):
    release = get_object_or_404(QualityReleaseAuthorization, pk=pk, tenant=request.tenant)
    reason = request.POST.get("hold_reason", "").strip()
    if release.is_on_hold:
        release.is_on_hold = False
        release.status = "draft"
        action = "release"
        msg = f"Quality release {release.number} removed from hold."
    else:
        if not reason:
            messages.error(request, "A non-empty hold reason is mandatory when placing a release on hold.")
            return redirect("quality:quality_release_authorization_detail", pk=release.pk)
        release.is_on_hold = True
        release.status = "active_hold"
        release.hold_reason = reason
        action = "hold"
        msg = f"Quality release {release.number} placed on shipping hold."
    release.save()
    write_audit_log(request.user, release, action, tenant=request.tenant)
    messages.success(request, msg)
    return redirect("quality:quality_release_authorization_detail", pk=release.pk)


@login_required
def quality_release_authorization_export(request):
    write_audit_log(request.user, None, "export", changes={"model": "QualityReleaseAuthorization"}, tenant=request.tenant)
    qs = QualityReleaseAuthorization.objects.filter(tenant=request.tenant).select_related("customer", "releasing_officer").order_by("-created_at")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="quality_releases.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Release Number",
        "Title",
        "Status",
        "Disposition",
        "Customer",
        "Shipment Number",
        "Lot Number",
        "Destination Country",
        "Authorized Qty",
        "On Hold",
        "Hold Reason",
        "Inspection Passed",
        "Packaging Approved",
        "CoC Signed",
        "Export Cleared",
        "Security Seal #",
        "Carrier",
        "Tracking Ref",
        "Releasing Officer",
        "Release Date",
    ])
    for item in qs:
        writer.writerow([
            _csv_safe(item.number),
            _csv_safe(item.title),
            _csv_safe(item.get_status_display()),
            _csv_safe(item.get_release_disposition_display()),
            _csv_safe(item.customer.name if item.customer else ""),
            _csv_safe(item.shipment_number),
            _csv_safe(item.lot_number),
            _csv_safe(item.destination_country),
            _csv_safe(item.quantity_authorized),
            "Yes" if item.is_on_hold else "No",
            _csv_safe(item.hold_reason),
            "Yes" if item.final_inspection_passed else "No",
            "Yes" if item.packaging_label_approved else "No",
            "Yes" if item.coc_issued_and_signed else "No",
            "Yes" if item.export_compliance_verified else "No",
            _csv_safe(item.shipping_container_security_seal),
            _csv_safe(item.carrier_name),
            _csv_safe(item.tracking_reference),
            _csv_safe(item.releasing_officer.get_full_name() if item.releasing_officer else ""),
            _csv_safe(item.release_date),
        ])

    return response
