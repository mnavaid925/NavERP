"""Function-based CRUD and lifecycle views for IT Hardware Assets (11.18)."""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.ItAssetManagement.ItHardwareAssets import ItHardwareAssetForm
from apps.assets.models.ItAssetManagement.CmdbRelationships import CmdbRelationship
from apps.assets.models.ItAssetManagement.ItHardwareAssets import ItHardwareAsset
from apps.assets.views._common import assets_object, assets_scope
from apps.assets.views.ItAssetManagement._helpers import (
    CMDB_REL_SELECT_RELATED,
    PAGE_SIZE,
    apply_choice_filter,
    apply_fk_filter,
    csv_export_response,
    is_tenant_admin_user,
)
from apps.core.decorators import tenant_admin_required
from apps.core.models.OrgUnit import OrgUnit
from apps.core.utils import write_audit_log

_HW_LIST_SELECT_RELATED = (
    "org_unit",
    "location",
    "custodian_party",
    "employee_profile__party",
    "currency",
)

_HW_DETAIL_SELECT_RELATED = _HW_LIST_SELECT_RELATED + (
    "operational_asset",
    "fixed_asset",
    "asset_model",
    "asset_category",
    "warranty",
    "requisition",
    "replacement_plan",
    "disposal_request",
    "scrap_salvage",
    "vendor_party",
    "owner",
    "sanitization_verified_by",
)


def _filter_hardware_queryset(request, base_qs):
    """Apply search and dropdown GET filters to an ItHardwareAsset queryset."""
    qs = base_qs.select_related(*_HW_LIST_SELECT_RELATED)
    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(hostname__icontains=search_query)
            | Q(fqdn__icontains=search_query)
            | Q(serial_number__icontains=search_query)
            | Q(asset_tag_code__icontains=search_query)
            | Q(manufacturer__icontains=search_query)
            | Q(model_name__icontains=search_query)
            | Q(mac_address__icontains=search_query)
            | Q(operating_system__icontains=search_query)
        )
    qs = apply_choice_filter(
        qs,
        request,
        "status",
        allowed_values={val for val, _ in ItHardwareAsset.STATUS_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "device_class",
        allowed_values={val for val, _ in ItHardwareAsset.DEVICE_CLASS_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "environment",
        allowed_values={val for val, _ in ItHardwareAsset.ENVIRONMENT_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "disk_encryption_status",
        allowed_values={val for val, _ in ItHardwareAsset.DISK_ENCRYPTION_CHOICES},
    )
    qs = apply_fk_filter(qs, request, "org_unit")

    eol_state = request.GET.get("eol_state", "").strip()
    today = timezone.now().date()
    if eol_state == "eol_expired":
        qs = qs.filter(vendor_eol_date__lt=today)
    elif eol_state == "eos_soon":
        qs = qs.filter(vendor_eos_date__gte=today, vendor_eos_date__lte=today + timedelta(days=90))
    elif eol_state == "refresh_due":
        qs = qs.filter(refresh_due_date__lte=today + timedelta(days=90)).exclude(
            status__in=ItHardwareAsset.LOCKED_STATUSES
        )
    elif eol_state == "pending_wipe":
        qs = qs.filter(sanitization_required=True, sanitization_status="pending_wipe")
    return qs


@login_required
def it_hardware_asset_list(request):
    """List IT hardware assets with KPI summary, search, filters, and pagination."""
    base_qs = assets_scope(ItHardwareAsset.objects.all(), request)
    today = timezone.now().date()
    horizon_90d = today + timedelta(days=90)
    kpis = base_qs.aggregate(
        total_count=Count("id"),
        deployed_count=Count("id", filter=Q(status="deployed")),
        eol_due_count=Count(
            "id",
            filter=(
                (Q(vendor_eol_date__lt=today) | Q(refresh_due_date__lte=horizon_90d))
                & ~Q(status__in=ItHardwareAsset.LOCKED_STATUSES)
            ),
        ),
        pending_wipe_count=Count(
            "id",
            filter=Q(sanitization_required=True, sanitization_status="pending_wipe"),
        ),
    )
    filtered_qs = _filter_hardware_queryset(request, base_qs)
    paginator = Paginator(filtered_qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "hardware_assets": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "total_count": kpis["total_count"] or 0,
        "deployed_count": kpis["deployed_count"] or 0,
        "eol_due_count": kpis["eol_due_count"] or 0,
        "pending_wipe_count": kpis["pending_wipe_count"] or 0,
        "status_choices": ItHardwareAsset.STATUS_CHOICES,
        "device_class_choices": ItHardwareAsset.DEVICE_CLASS_CHOICES,
        "environment_choices": ItHardwareAsset.ENVIRONMENT_CHOICES,
        "encryption_choices": ItHardwareAsset.DISK_ENCRYPTION_CHOICES,
        "org_units": OrgUnit.objects.filter(tenant=request.tenant).order_by("name"),
        "search_query": request.GET.get("q", "").strip(),
    }
    return render(request, "assets/itassetmanagement/it_hardware_asset/list.html", context)


@login_required
def it_hardware_asset_export_csv(request):
    """Export filtered IT hardware assets as a formula-safe CSV."""
    base_qs = assets_scope(ItHardwareAsset.objects.all(), request)
    qs = _filter_hardware_queryset(request, base_qs)
    headers = [
        "Number",
        "Hostname",
        "Device Class",
        "Serial Number",
        "OS",
        "IP Address",
        "Environment",
        "Criticality",
        "Status",
        "Disk Encryption",
        "Vendor EOL",
        "Refresh Due",
        "Refresh Cost",
        "Sanitization Status",
        "Org Unit",
    ]
    rows = (
        [
            hw.number,
            hw.hostname,
            hw.get_device_class_display(),
            hw.serial_number,
            f"{hw.operating_system} {hw.os_version}".strip(),
            hw.ip_address or "",
            hw.get_environment_display(),
            hw.get_criticality_display(),
            hw.get_status_display(),
            hw.get_disk_encryption_status_display(),
            hw.vendor_eol_date.isoformat() if hw.vendor_eol_date else "",
            hw.refresh_due_date.isoformat() if hw.refresh_due_date else "",
            hw.estimated_refresh_cost,
            hw.get_sanitization_status_display(),
            hw.org_unit.name if hw.org_unit else "",
        ]
        for hw in qs
    )
    return csv_export_response(filename="it_hardware_assets.csv", headers=headers, rows=rows)


def _sync_sanitization_attestation(hardware, user):
    """Keep sanitization_verified_by and sanitized_at consistent on admin form saves."""
    if not is_tenant_admin_user(user):
        return
    if hardware.sanitization_status in ("wiped_verified", "certificate_on_file"):
        if hardware.sanitization_verified_by_id is None:
            hardware.sanitization_verified_by = user
        if hardware.sanitized_at is None:
            hardware.sanitized_at = timezone.now()
        if hardware.sanitization_date is None:
            hardware.sanitization_date = timezone.now().date()
    else:
        hardware.sanitization_verified_by = None
        hardware.sanitized_at = None


@login_required
def it_hardware_asset_create(request):
    """Create a new tenant-scoped IT hardware asset."""
    if request.method == "POST":
        form = ItHardwareAssetForm(request.POST, tenant=request.tenant, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                hardware = form.save(commit=False)
                hardware.tenant = request.tenant
                if hardware.owner_id is None:
                    hardware.owner = request.user
                _sync_sanitization_attestation(hardware, request.user)
                hardware.save()
                write_audit_log(request.user, hardware, "create", tenant=request.tenant)
            messages.success(request, f"IT Hardware Asset {hardware.number} created.")
            return redirect("assets:it_hardware_asset_detail", pk=hardware.pk)
    else:
        form = ItHardwareAssetForm(tenant=request.tenant, user=request.user)

    return render(
        request,
        "assets/itassetmanagement/it_hardware_asset/form.html",
        {
            "form": form,
            "hardware": None,
            "is_edit": False,
            "title": "New IT Hardware Asset",
        },
    )


@login_required
def it_hardware_asset_detail(request, pk):
    """Display an IT hardware asset detail view with CMDB edges and lifecycle actions."""
    hardware = assets_object(
        request,
        ItHardwareAsset,
        pk,
        select_related=_HW_DETAIL_SELECT_RELATED,
    )
    outbound_edges = (
        CmdbRelationship.objects.filter(tenant=request.tenant, source_hardware=hardware)
        .select_related(*CMDB_REL_SELECT_RELATED)
        .order_by("-updated_at")
    )
    inbound_edges = (
        CmdbRelationship.objects.filter(tenant=request.tenant, target_hardware=hardware)
        .select_related(*CMDB_REL_SELECT_RELATED)
        .order_by("-updated_at")
    )
    return render(
        request,
        "assets/itassetmanagement/it_hardware_asset/detail.html",
        {
            "hardware": hardware,
            "outbound_edges": outbound_edges,
            "inbound_edges": inbound_edges,
        },
    )


@login_required
def it_hardware_asset_edit(request, pk):
    """Edit an unlocked IT hardware asset."""
    hardware = assets_object(request, ItHardwareAsset, pk)
    if hardware.is_locked:
        messages.warning(
            request,
            f"IT Hardware Asset {hardware.number} is {hardware.get_status_display()} and cannot be edited.",
        )
        return redirect("assets:it_hardware_asset_detail", pk=hardware.pk)

    if request.method == "POST":
        form = ItHardwareAssetForm(request.POST, instance=hardware, tenant=request.tenant, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                hardware = form.save(commit=False)
                _sync_sanitization_attestation(hardware, request.user)
                hardware.save()
                write_audit_log(request.user, hardware, "update", tenant=request.tenant)
            messages.success(request, f"IT Hardware Asset {hardware.number} updated.")
            return redirect("assets:it_hardware_asset_detail", pk=hardware.pk)
    else:
        form = ItHardwareAssetForm(instance=hardware, tenant=request.tenant, user=request.user)

    return render(
        request,
        "assets/itassetmanagement/it_hardware_asset/form.html",
        {
            "form": form,
            "hardware": hardware,
            "is_edit": True,
            "title": f"Edit {hardware.number} — {hardware.hostname}",
        },
    )


@tenant_admin_required
@require_POST
def it_hardware_asset_delete(request, pk):
    """Delete an unlocked IT hardware asset (tenant admin only)."""
    hardware = assets_object(request, ItHardwareAsset, pk)
    if hardware.is_locked:
        messages.warning(
            request,
            f"IT Hardware Asset {hardware.number} is {hardware.get_status_display()} and cannot be deleted.",
        )
        return redirect("assets:it_hardware_asset_detail", pk=hardware.pk)
    number = hardware.number
    with transaction.atomic():
        write_audit_log(request.user, hardware, "delete", tenant=request.tenant)
        hardware.delete()
    messages.success(request, f"IT Hardware Asset {number} deleted.")
    return redirect("assets:it_hardware_asset_list")


def _hardware_status_transition(request, pk, target_status, audit_verb, label):
    """Transition an unlocked ItHardwareAsset to ``target_status`` with audit logging."""
    hardware = assets_object(request, ItHardwareAsset, pk)
    if hardware.is_locked:
        messages.warning(
            request,
            f"IT Hardware Asset {hardware.number} is already {hardware.get_status_display()}.",
        )
        return redirect("assets:it_hardware_asset_detail", pk=hardware.pk)
    with transaction.atomic():
        hardware.status = target_status
        update_fields = ["status", "updated_at"]
        if target_status == "deployed":
            hardware.last_seen_checkin = timezone.now()
            update_fields.append("last_seen_checkin")
            if hardware.assigned_date is None:
                hardware.assigned_date = timezone.now().date()
                update_fields.append("assigned_date")
        hardware.save(update_fields=update_fields)
        write_audit_log(request.user, hardware, audit_verb, tenant=request.tenant)
    messages.success(request, f"IT Hardware Asset {hardware.number} moved to {label}.")
    return redirect("assets:it_hardware_asset_detail", pk=hardware.pk)


@login_required
@require_POST
def it_hardware_asset_deploy(request, pk):
    """Mark IT hardware asset as Deployed / In Use."""
    return _hardware_status_transition(request, pk, "deployed", "deploy", "Deployed / In Use")


@login_required
@require_POST
def it_hardware_asset_move_to_stock(request, pk):
    """Move IT hardware asset to Staged in Stock."""
    return _hardware_status_transition(request, pk, "staged_in_stock", "stock", "Staged in Stock")


@login_required
@require_POST
def it_hardware_asset_send_to_repair(request, pk):
    """Move IT hardware asset to In Repair / RMA."""
    return _hardware_status_transition(request, pk, "in_repair", "repair", "In Repair / RMA")


@login_required
@require_POST
def it_hardware_asset_move_to_loaner(request, pk):
    """Move IT hardware asset to Loaner Pool."""
    return _hardware_status_transition(request, pk, "loaner_pool", "loaner", "Loaner Pool")


@login_required
@require_POST
def it_hardware_asset_flag_for_refresh(request, pk):
    """Flag IT hardware asset as Pending Refresh."""
    return _hardware_status_transition(request, pk, "pending_refresh", "refresh", "Pending Refresh")


@tenant_admin_required
@require_POST
def it_hardware_asset_mark_sanitized(request, pk):
    """Verify NIST SP 800-88 data sanitization on an IT hardware asset."""
    hardware = assets_object(request, ItHardwareAsset, pk)
    if hardware.is_locked:
        messages.warning(
            request,
            f"IT Hardware Asset {hardware.number} is {hardware.get_status_display()} and cannot be modified.",
        )
        return redirect("assets:it_hardware_asset_detail", pk=hardware.pk)
    with transaction.atomic():
        if hardware.sanitization_method == "none":
            hardware.sanitization_method = "nist_purge"
        hardware.sanitization_status = (
            "certificate_on_file" if hardware.sanitization_certificate_ref else "wiped_verified"
        )
        if hardware.sanitization_date is None:
            hardware.sanitization_date = timezone.now().date()
        hardware.sanitization_verified_by = request.user
        hardware.sanitized_at = timezone.now()
        hardware.save(
            update_fields=[
                "sanitization_method",
                "sanitization_status",
                "sanitization_date",
                "sanitization_verified_by",
                "sanitized_at",
                "updated_at",
            ]
        )
        write_audit_log(request.user, hardware, "sanitize", tenant=request.tenant)
    messages.success(
        request,
        f"NIST SP 800-88 sanitization verified for {hardware.number} ({hardware.get_sanitization_status_display()}).",
    )
    return redirect("assets:it_hardware_asset_detail", pk=hardware.pk)


@tenant_admin_required
@require_POST
def it_hardware_asset_retire(request, pk):
    """Retire IT hardware asset after confirming NIST SP 800-88 sanitization compliance."""
    hardware = assets_object(request, ItHardwareAsset, pk)
    if hardware.is_locked:
        messages.warning(
            request,
            f"IT Hardware Asset {hardware.number} is already {hardware.get_status_display()}.",
        )
        return redirect("assets:it_hardware_asset_detail", pk=hardware.pk)
    if hardware.sanitization_required and hardware.sanitization_status not in (
        "not_required",
        "wiped_verified",
        "certificate_on_file",
    ):
        messages.error(
            request,
            f"Cannot retire {hardware.number}: NIST SP 800-88 sanitization must be verified first.",
        )
        return redirect("assets:it_hardware_asset_detail", pk=hardware.pk)
    with transaction.atomic():
        hardware.status = "sanitized_retired"
        hardware.retired_at = timezone.now()
        hardware.save(update_fields=["status", "retired_at", "updated_at"])
        write_audit_log(request.user, hardware, "retire", tenant=request.tenant)
    messages.success(request, f"IT Hardware Asset {hardware.number} sanitized & retired.")
    return redirect("assets:it_hardware_asset_detail", pk=hardware.pk)
