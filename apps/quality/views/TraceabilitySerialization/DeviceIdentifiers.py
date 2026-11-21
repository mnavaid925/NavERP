from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.TraceabilitySerialization.DeviceIdentifiers import DeviceIdentifierForm
from apps.quality.models.TraceabilitySerialization.DeviceIdentifiers import DeviceIdentifier
from apps.quality.views._common import quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def device_identifier_list(request):
    qs = quality_scope(DeviceIdentifier.objects.all(), request).select_related("regulatory_contact")

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(device_name__icontains=query)
            | Q(primary_di__icontains=query)
            | Q(basic_udi_di__icontains=query)
            | Q(model_number__icontains=query)
            | Q(brand_name__icontains=query)
            | Q(number__icontains=query)
        )

    selected_device_class = request.GET.get("device_class", "").strip()
    if selected_device_class:
        qs = qs.filter(device_class=selected_device_class)

    selected_gudid_status = request.GET.get("gudid_status", "").strip()
    if selected_gudid_status:
        qs = qs.filter(gudid_status=selected_gudid_status)

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "device_identifiers": page_obj.object_list,
        "issuing_agency_choices": DeviceIdentifier.ISSUING_AGENCY_CHOICES,
        "device_class_choices": DeviceIdentifier.DEVICE_CLASS_CHOICES,
        "gudid_status_choices": DeviceIdentifier.REGULATORY_STATUS_CHOICES,
        "eudamed_status_choices": DeviceIdentifier.REGULATORY_STATUS_CHOICES,
        "selected_device_class": selected_device_class,
        "selected_gudid_status": selected_gudid_status,
        "query": query,
    }
    return render(request, "quality/traceabilityserialization/device_identifier/list.html", context)


@login_required
def device_identifier_detail(request, pk):
    device_identifier = quality_object(
        request,
        DeviceIdentifier,
        pk,
        select_related=["regulatory_contact", "approval_document"],
    )
    serialized_items = (
        device_identifier.serialized_items.all()[:20] if hasattr(device_identifier, "serialized_items") else []
    )

    context = {
        "device_identifier": device_identifier,
        "serialized_items": serialized_items,
    }
    return render(request, "quality/traceabilityserialization/device_identifier/detail.html", context)


@login_required
def device_identifier_create(request):
    if request.method == "POST":
        form = DeviceIdentifierForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Device Identifier {obj.primary_di} created successfully.")
            return redirect("quality:device_identifier_detail", pk=obj.pk)
    else:
        form = DeviceIdentifierForm(tenant=request.tenant)

    context = {
        "form": form,
        "device_identifier": None,
        "is_edit": False,
    }
    return render(request, "quality/traceabilityserialization/device_identifier/form.html", context)


@login_required
def device_identifier_edit(request, pk):
    obj = quality_object(request, DeviceIdentifier, pk)
    if request.method == "POST":
        form = DeviceIdentifierForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Device Identifier {obj.primary_di} updated successfully.")
            return redirect("quality:device_identifier_detail", pk=obj.pk)
    else:
        form = DeviceIdentifierForm(instance=obj, tenant=request.tenant)

    context = {
        "form": form,
        "device_identifier": obj,
        "is_edit": True,
    }
    return render(request, "quality/traceabilityserialization/device_identifier/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def device_identifier_delete(request, pk):
    obj = quality_object(request, DeviceIdentifier, pk)
    number = obj.primary_di
    write_audit_log(request.user, obj, "delete", tenant=request.tenant)
    obj.delete()
    messages.success(request, f"Device Identifier {number} deleted successfully.")
    return redirect("quality:device_identifier_list")
