import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from apps.core.models import OrgUnit, Party
from apps.core.utils import write_audit_log
from apps.quality.forms.EhsManagement.WasteDisposalManifests import WasteDisposalManifestForm
from apps.quality.models.EhsManagement.WasteDisposalManifests import WasteDisposalManifest
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def waste_disposal_manifest_list(request):
    qs = quality_scope(WasteDisposalManifest.objects.all(), request).select_related(
        "generator_org_unit", "transporter", "tsdf_facility", "associated_hazardous_material"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(manifest_title__icontains=q)
            | Q(regulatory_manifest_id__icontains=q)
            | Q(waste_description__icontains=q)
            | Q(epa_waste_codes__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    type_filter = request.GET.get("manifest_type", "").strip()
    if type_filter:
        qs = qs.filter(manifest_type=type_filter)

    transporter_filter = request.GET.get("transporter", "").strip()
    if transporter_filter and transporter_filter.isdigit():
        qs = qs.filter(transporter_id=int(transporter_filter))

    tsdf_filter = request.GET.get("tsdf_facility", "").strip()
    if tsdf_filter and tsdf_filter.isdigit():
        qs = qs.filter(tsdf_facility_id=int(tsdf_filter))

    org_unit_filter = request.GET.get("org_unit", "").strip()
    if org_unit_filter and org_unit_filter.isdigit():
        qs = qs.filter(generator_org_unit_id=int(org_unit_filter))

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    if "page" in query_params:
        del query_params["page"]

    context = {
        "waste_manifests": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": paginator.count,
        "status_choices": WasteDisposalManifest.STATUS_CHOICES,
        "manifest_type_choices": WasteDisposalManifest.MANIFEST_TYPE_CHOICES,
        "transporters": Party.objects.filter(tenant=request.tenant).order_by("name"),
        "tsdfs": Party.objects.filter(tenant=request.tenant).order_by("name"),
        "org_units": OrgUnit.objects.filter(tenant=request.tenant).order_by("name"),
        "query_string": query_params.urlencode(),
    }
    return render(request, "quality/ehsmanagement/waste_disposal_manifest/list.html", context)


@login_required
def waste_disposal_manifest_create(request):
    if request.method == "POST":
        form = WasteDisposalManifestForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Waste disposal manifest {obj.number} created successfully.")
            return redirect("quality:waste_disposal_manifest_detail", pk=obj.pk)
    else:
        form = WasteDisposalManifestForm(
            tenant=request.tenant, initial={"accumulation_start_date": timezone.now().date()}
        )

    context = {
        "form": form,
        "waste_manifest": None,
        "is_edit": False,
    }
    return render(request, "quality/ehsmanagement/waste_disposal_manifest/form.html", context)


@login_required
def waste_disposal_manifest_detail(request, pk):
    obj = quality_object(
        request,
        WasteDisposalManifest,
        pk,
        select_related=[
            "generator_org_unit",
            "associated_hazardous_material",
            "transporter",
            "tsdf_facility",
            "certifying_officer",
        ],
    )
    context = {
        "waste_manifest": obj,
    }
    return render(request, "quality/ehsmanagement/waste_disposal_manifest/detail.html", context)


@login_required
def waste_disposal_manifest_update(request, pk):
    obj = quality_object(
        request,
        WasteDisposalManifest,
        pk,
        select_related=[
            "generator_org_unit",
            "associated_hazardous_material",
            "transporter",
            "tsdf_facility",
            "certifying_officer",
        ],
    )
    if request.method == "POST":
        form = WasteDisposalManifestForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Waste disposal manifest {obj.number} updated.")
            return redirect("quality:waste_disposal_manifest_detail", pk=obj.pk)
    else:
        form = WasteDisposalManifestForm(instance=obj, tenant=request.tenant)

    context = {
        "form": form,
        "waste_manifest": obj,
        "is_edit": True,
    }
    return render(request, "quality/ehsmanagement/waste_disposal_manifest/form.html", context)


waste_disposal_manifest_edit = waste_disposal_manifest_update


@login_required
@require_POST
def waste_disposal_manifest_delete(request, pk):
    obj = quality_object(request, WasteDisposalManifest, pk)
    if not (request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)):
        messages.error(request, "Only tenant administrators can delete waste disposal manifests.")
        return redirect("quality:waste_disposal_manifest_detail", pk=obj.pk)

    if obj.status in ("in_transit", "received_by_tsdf", "certified_disposed"):
        messages.error(request, f"Active or certified waste disposal manifests cannot be deleted.")
        return redirect("quality:waste_disposal_manifest_detail", pk=obj.pk)

    num = obj.number
    write_audit_log(request.user, obj, "delete", tenant=request.tenant)
    obj.delete()
    messages.success(request, f"Waste disposal manifest {num} deleted.")
    return redirect("quality:waste_disposal_manifest_list")


@login_required
def waste_disposal_manifest_export(request):
    qs = quality_scope(WasteDisposalManifest.objects.all(), request).select_related(
        "generator_org_unit", "transporter", "tsdf_facility"
    )
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(manifest_title__icontains=q)
            | Q(regulatory_manifest_id__icontains=q)
            | Q(waste_description__icontains=q)
            | Q(epa_waste_codes__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    type_filter = request.GET.get("manifest_type", "").strip()
    if type_filter:
        qs = qs.filter(manifest_type=type_filter)

    transporter_filter = request.GET.get("transporter", "").strip()
    if transporter_filter and transporter_filter.isdigit():
        qs = qs.filter(transporter_id=int(transporter_filter))

    tsdf_filter = (request.GET.get("tsdf_facility") or request.GET.get("tsdf", "")).strip()
    if tsdf_filter and tsdf_filter.isdigit():
        qs = qs.filter(tsdf_facility_id=int(tsdf_filter))

    org_unit_filter = request.GET.get("org_unit", "").strip()
    if org_unit_filter and org_unit_filter.isdigit():
        qs = qs.filter(generator_org_unit_id=int(org_unit_filter))

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="waste_manifests_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Manifest Number",
        "Regulatory Tracking ID",
        "Title",
        "Manifest Type",
        "Status",
        "Generator Site",
        "Accumulation Start",
        "Accumulation Days",
        "Quantity",
        "UOM",
        "Container Type",
        "Container Count",
        "EPA Waste Codes",
        "Transporter",
        "TSDF Facility",
        "Shipment Date",
        "TSDF Receipt Date",
        "Destruction Cert #",
    ])
    for item in qs:
        writer.writerow([
            _csv_safe(item.number),
            _csv_safe(item.regulatory_manifest_id),
            _csv_safe(item.manifest_title),
            _csv_safe(item.get_manifest_type_display()),
            _csv_safe(item.get_status_display()),
            _csv_safe(item.generator_org_unit.name if item.generator_org_unit else ""),
            _csv_safe(item.accumulation_start_date),
            _csv_safe(item.accumulation_days),
            _csv_safe(item.quantity_value),
            _csv_safe(item.get_quantity_uom_display()),
            _csv_safe(item.get_container_type_display()),
            _csv_safe(item.container_count),
            _csv_safe(item.epa_waste_codes),
            _csv_safe(item.transporter.name if item.transporter else ""),
            _csv_safe(item.tsdf_facility.name if item.tsdf_facility else ""),
            _csv_safe(item.shipment_date),
            _csv_safe(item.tsdf_receipt_date),
            _csv_safe(item.certificate_of_disposal_number),
        ])
    return response


@login_required
@require_POST
def waste_disposal_manifest_certify(request, pk):
    obj = quality_object(request, WasteDisposalManifest, pk)
    cert_num = request.POST.get("certificate_of_disposal_number", "").strip()[:100]
    cert_date_str = request.POST.get("certificate_received_date", "").strip()
    method_code = request.POST.get("management_method_code", "").strip()[:50]
    discrepancy = request.POST.get("discrepancy_details", "").strip()

    if not cert_num and not discrepancy:
        messages.error(request, "A Certificate of Disposal number or discrepancy explanation is required.")
        return redirect("quality:waste_disposal_manifest_detail", pk=obj.pk)

    if cert_num:
        obj.certificate_of_disposal_number = cert_num
    if method_code:
        obj.management_method_code = method_code
    if discrepancy:
        obj.discrepancy_details = discrepancy
        obj.status = "discrepancy_flagged"
    else:
        obj.status = "certified_disposed"

    if cert_date_str:
        parsed_d = parse_date(cert_date_str)
        if parsed_d:
            obj.certificate_received_date = parsed_d
    elif not obj.certificate_received_date:
        obj.certificate_received_date = timezone.now().date()

    if not obj.tsdf_receipt_date:
        obj.tsdf_receipt_date = timezone.now().date()

    obj.save()
    write_audit_log(request.user, obj, "certify", tenant=request.tenant)
    messages.success(request, f"Manifest {obj.number} certified disposed. Certificate #{obj.certificate_of_disposal_number} recorded.")
    return redirect("quality:waste_disposal_manifest_detail", pk=obj.pk)
