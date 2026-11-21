import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.models import OrgUnit, Party
from apps.core.utils import write_audit_log
from apps.quality.forms.EhsManagement.HazardousMaterials import HazardousMaterialForm
from apps.quality.models.EhsManagement.HazardousMaterials import HazardousMaterial
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def hazardous_material_list(request):
    qs = quality_scope(HazardousMaterial.objects.all(), request).select_related("org_unit", "supplier", "managed_by")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(material_name__icontains=q)
            | Q(trade_name__icontains=q)
            | Q(cas_number__icontains=q)
            | Q(un_number__icontains=q)
            | Q(storage_location_code__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    physical_state_filter = request.GET.get("physical_state", "").strip()
    if physical_state_filter:
        qs = qs.filter(physical_state=physical_state_filter)

    signal_word_filter = request.GET.get("ghs_signal_word", "").strip()
    if signal_word_filter:
        qs = qs.filter(ghs_signal_word=signal_word_filter)

    org_unit_filter = request.GET.get("org_unit", "").strip()
    if org_unit_filter and org_unit_filter.isdigit():
        qs = qs.filter(org_unit_id=int(org_unit_filter))

    supplier_filter = request.GET.get("supplier", "").strip()
    if supplier_filter and supplier_filter.isdigit():
        qs = qs.filter(supplier_id=int(supplier_filter))

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    if "page" in query_params:
        del query_params["page"]

    context = {
        "hazardous_materials": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": paginator.count,
        "status_choices": HazardousMaterial.STATUS_CHOICES,
        "physical_state_choices": HazardousMaterial.PHYSICAL_STATE_CHOICES,
        "signal_word_choices": HazardousMaterial.GHS_SIGNAL_WORD_CHOICES,
        "org_units": OrgUnit.objects.filter(tenant=request.tenant).order_by("name"),
        "suppliers": Party.objects.filter(tenant=request.tenant).order_by("name"),
        "query_string": query_params.urlencode(),
    }
    return render(request, "quality/ehsmanagement/hazardous_material/list.html", context)


@login_required
def hazardous_material_create(request):
    if request.method == "POST":
        form = HazardousMaterialForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Hazardous material {obj.number} created successfully.")
            return redirect("quality:hazardous_material_detail", pk=obj.pk)
    else:
        form = HazardousMaterialForm(tenant=request.tenant)

    context = {
        "form": form,
        "hazardous_material": None,
        "is_edit": False,
    }
    return render(request, "quality/ehsmanagement/hazardous_material/form.html", context)


@login_required
def hazardous_material_detail(request, pk):
    obj = quality_object(
        request,
        HazardousMaterial,
        pk,
        select_related=["org_unit", "sds_document", "supplier", "managed_by"],
    )
    linked_waste_manifests = obj.waste_manifests.filter(tenant=request.tenant).order_by("-shipment_date")[:10]

    context = {
        "hazardous_material": obj,
        "linked_waste_manifests": linked_waste_manifests,
    }
    return render(request, "quality/ehsmanagement/hazardous_material/detail.html", context)


@login_required
def hazardous_material_update(request, pk):
    obj = quality_object(
        request,
        HazardousMaterial,
        pk,
        select_related=["org_unit", "sds_document", "supplier", "managed_by"],
    )
    if request.method == "POST":
        form = HazardousMaterialForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Hazardous material {obj.number} updated successfully.")
            return redirect("quality:hazardous_material_detail", pk=obj.pk)
    else:
        form = HazardousMaterialForm(instance=obj, tenant=request.tenant)

    context = {
        "form": form,
        "hazardous_material": obj,
        "is_edit": True,
    }
    return render(request, "quality/ehsmanagement/hazardous_material/form.html", context)


hazardous_material_edit = hazardous_material_update


@login_required
@require_POST
def hazardous_material_delete(request, pk):
    obj = quality_object(request, HazardousMaterial, pk)
    num = obj.number
    write_audit_log(request.user, obj, "delete", tenant=request.tenant)
    obj.delete()
    messages.success(request, f"Hazardous material {num} deleted.")
    return redirect("quality:hazardous_material_list")


@login_required
def hazardous_material_export(request):
    qs = quality_scope(HazardousMaterial.objects.all(), request).select_related("org_unit", "supplier", "managed_by")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="hazardous_materials_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Material Number",
        "Common Name",
        "Trade Name",
        "CAS Number",
        "UN Number",
        "Physical State",
        "GHS Signal Word",
        "Status",
        "Storage Location",
        "Max Quantity",
        "UOM",
        "SDS Expiry Date",
        "Facility",
        "Manager",
    ])
    for item in qs:
        writer.writerow([
            _csv_safe(item.number),
            _csv_safe(item.material_name),
            _csv_safe(item.trade_name),
            _csv_safe(item.cas_number),
            _csv_safe(item.un_number),
            _csv_safe(item.get_physical_state_display()),
            _csv_safe(item.get_ghs_signal_word_display()),
            _csv_safe(item.get_status_display()),
            _csv_safe(item.storage_location_code),
            _csv_safe(item.maximum_storage_quantity),
            _csv_safe(item.quantity_uom),
            _csv_safe(item.sds_expiry_date),
            _csv_safe(item.org_unit.name if item.org_unit else ""),
            _csv_safe(item.managed_by.get_full_name() or item.managed_by.username if item.managed_by else ""),
        ])
    return response


@login_required
def hazardous_material_label(request, pk):
    obj = quality_object(
        request,
        HazardousMaterial,
        pk,
        select_related=["org_unit", "managed_by"],
    )
    context = {
        "hazardous_material": obj,
    }
    return render(request, "quality/ehsmanagement/hazardous_material/label.html", context)
