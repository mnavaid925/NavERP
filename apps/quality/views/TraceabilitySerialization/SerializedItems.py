from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.TraceabilitySerialization.SerializedItems import SerializedItemForm
from apps.quality.models.TraceabilitySerialization.SerializedItems import SerializedItem
from apps.quality.views._common import quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def serialized_item_list(request):
    qs = quality_scope(SerializedItem.objects.all(), request).select_related("parent_container", "batch_record")

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(serial_number__icontains=query)
            | Q(gtin_or_di__icontains=query)
            | Q(sscc_code__icontains=query)
            | Q(lot_number__icontains=query)
            | Q(item_code__icontains=query)
            | Q(item_name__icontains=query)
            | Q(number__icontains=query)
        )

    selected_level = request.GET.get("packaging_level", "").strip()
    if selected_level:
        qs = qs.filter(packaging_level=selected_level)

    selected_status = request.GET.get("commissioning_status", "").strip()
    if selected_status:
        qs = qs.filter(commissioning_status=selected_status)

    selected_state = request.GET.get("epcis_state", "").strip()
    if selected_state:
        qs = qs.filter(epcis_state=selected_state)

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "serialized_items": page_obj.object_list,
        "packaging_level_choices": SerializedItem.PACKAGING_LEVEL_CHOICES,
        "commissioning_status_choices": SerializedItem.COMMISSIONING_STATUS_CHOICES,
        "epcis_state_choices": SerializedItem.EPCIS_STATE_CHOICES,
        "selected_level": selected_level,
        "selected_status": selected_status,
        "selected_state": selected_state,
        "query": query,
    }
    return render(request, "quality/traceabilityserialization/serialized_item/list.html", context)


@login_required
def serialized_item_detail(request, pk):
    serialized_item = quality_object(
        request,
        SerializedItem,
        pk,
        select_related=[
            "batch_record",
            "device_identifier",
            "parent_container",
            "custodian",
            "location_unit",
            "shipment",
        ],
    )
    child_units = serialized_item.child_units.all()

    context = {
        "serialized_item": serialized_item,
        "child_units": child_units,
    }
    return render(request, "quality/traceabilityserialization/serialized_item/detail.html", context)


@login_required
def serialized_item_create(request):
    if request.method == "POST":
        form = SerializedItemForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            if obj.commissioning_status == "commissioned" and not obj.commissioned_at:
                obj.commissioned_at = timezone.now()
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Serialized Item {obj.serial_number} created successfully.")
            return redirect("quality:serialized_item_detail", pk=obj.pk)
    else:
        form = SerializedItemForm(tenant=request.tenant)

    context = {
        "form": form,
        "serialized_item": None,
        "is_edit": False,
    }
    return render(request, "quality/traceabilityserialization/serialized_item/form.html", context)


@login_required
def serialized_item_edit(request, pk):
    obj = quality_object(request, SerializedItem, pk)
    if request.method == "POST":
        form = SerializedItemForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.commissioning_status == "commissioned" and not obj.commissioned_at:
                obj.commissioned_at = timezone.now()
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Serialized Item {obj.serial_number} updated successfully.")
            return redirect("quality:serialized_item_detail", pk=obj.pk)
    else:
        form = SerializedItemForm(instance=obj, tenant=request.tenant)

    context = {
        "form": form,
        "serialized_item": obj,
        "is_edit": True,
    }
    return render(request, "quality/traceabilityserialization/serialized_item/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def serialized_item_delete(request, pk):
    obj = quality_object(request, SerializedItem, pk)
    number = obj.serial_number
    write_audit_log(request.user, obj, "delete", tenant=request.tenant)
    obj.delete()
    messages.success(request, f"Serialized Item {number} deleted successfully.")
    return redirect("quality:serialized_item_list")
