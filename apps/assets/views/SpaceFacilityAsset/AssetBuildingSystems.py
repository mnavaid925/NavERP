"""Views for AssetBuildingSystem (11.17 HVAC & Building Systems)."""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.SpaceFacilityAsset.AssetBuildingSystems import AssetBuildingSystemForm
from apps.assets.models.SpaceFacilityAsset.AssetBuildingSystems import AssetBuildingSystem
from apps.assets.models.SpaceFacilityAsset.AssetFacilitySpaces import AssetFacilitySpace
from apps.assets.views._common import assets_object, assets_scope
from apps.assets.views.SpaceFacilityAsset._helpers import (
    PAGE_SIZE,
    apply_choice_filter,
    apply_fk_filter,
    csv_export_response,
    parse_pos_int,
)
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


def _filtered_systems_queryset(request):
    today = timezone.now().date()
    base_qs = assets_scope(AssetBuildingSystem.objects.all(), request)
    qs = base_qs.select_related(
        "facility_space",
        "service_vendor",
        "org_unit",
        "operating_permit",
    ).defer("notes")

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(name__icontains=q)
            | Q(manufacturer__icontains=q)
            | Q(model_number__icontains=q)
            | Q(serial_number__icontains=q)
            | Q(ashrae_nfpa_code_ref__icontains=q)
            | Q(facility_space__code__icontains=q)
        )

    qs = apply_choice_filter(
        qs, request, "system_domain", allowed_values=dict(AssetBuildingSystem.SYSTEM_DOMAIN_CHOICES)
    )
    qs = apply_choice_filter(
        qs, request, "subsystem_type", allowed_values=dict(AssetBuildingSystem.SUBSYSTEM_TYPE_CHOICES)
    )
    qs = apply_choice_filter(
        qs, request, "comfort_status", allowed_values=dict(AssetBuildingSystem.COMFORT_STATUS_CHOICES)
    )
    qs = apply_choice_filter(
        qs, request, "condition_grade", allowed_values=dict(AssetBuildingSystem.CONDITION_GRADE_CHOICES)
    )
    qs = apply_choice_filter(
        qs, request, "status", allowed_values=dict(AssetBuildingSystem.STATUS_CHOICES)
    )
    qs = apply_fk_filter(qs, request, "facility_space")
    return base_qs, qs.order_by("system_domain", "name", "-number"), q, today


@login_required
def asset_building_system_list(request):
    """List tenant-scoped HVAC & building systems with comfort-band and inspection KPIs."""
    base_qs, qs, q, today = _filtered_systems_queryset(request)

    kpis = base_qs.aggregate(
        total=Count("id"),
        operational=Count("id", filter=Q(status="operational")),
        comfort_alert=Count("id", filter=Q(comfort_status__in=("drift_warning", "out_of_band"))),
        overdue_insp=Count(
            "id",
            filter=Q(next_inspection_due_date__lt=today) & ~Q(status="decommissioned"),
        ),
    )

    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    spaces = (
        assets_scope(AssetFacilitySpace.objects.all(), request)
        .only("id", "number", "code", "name")
        .order_by("code", "name")
    )

    return render(
        request,
        "assets/spacefacilityasset/asset_building_system/list.html",
        {
            "systems": page_obj,
            "paginator": paginator,
            "page_obj": page_obj,
            "is_paginated": page_obj.has_other_pages(),
            "total_count": kpis["total"] or 0,
            "operational_count": kpis["operational"] or 0,
            "comfort_alert_count": kpis["comfort_alert"] or 0,
            "overdue_inspection_count": kpis["overdue_insp"] or 0,
            "domain_choices": AssetBuildingSystem.SYSTEM_DOMAIN_CHOICES,
            "subsystem_choices": AssetBuildingSystem.SUBSYSTEM_TYPE_CHOICES,
            "comfort_choices": AssetBuildingSystem.COMFORT_STATUS_CHOICES,
            "condition_choices": AssetBuildingSystem.CONDITION_GRADE_CHOICES,
            "status_choices": AssetBuildingSystem.STATUS_CHOICES,
            "spaces": spaces,
            "search_query": q,
        },
    )


@login_required
def asset_building_system_export_csv(request):
    """Export filtered building systems as a formula-safe CSV attachment."""
    _, qs, _, _ = _filtered_systems_queryset(request)
    headers = [
        "Number",
        "Name",
        "Domain",
        "Subsystem",
        "Space",
        "Code / Standard",
        "Setpoint C",
        "Measured C",
        "Comfort Status",
        "Condition",
        "Criticality",
        "Next Inspection Due",
        "Status",
    ]
    rows = (
        [
            s.number,
            s.name,
            s.get_system_domain_display(),
            s.get_subsystem_type_display(),
            s.facility_space.code if s.facility_space else "",
            s.ashrae_nfpa_code_ref,
            s.setpoint_temp_c if s.setpoint_temp_c is not None else "",
            s.measured_temp_c if s.measured_temp_c is not None else "",
            s.get_comfort_status_display(),
            s.get_condition_grade_display(),
            s.get_criticality_tier_display(),
            s.next_inspection_due_date or "",
            s.get_status_display(),
        ]
        for s in qs.iterator(chunk_size=500)
    )
    return csv_export_response(filename="building_systems.csv", headers=headers, rows=rows)


@login_required
def asset_building_system_create(request):
    """Create a new HVAC or building infrastructure system."""
    if request.tenant is None:
        messages.error(request, "An active tenant workspace is required to create a building system.")
        return redirect("assets:asset_building_system_list")

    if request.method == "POST":
        form = AssetBuildingSystemForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                system = form.save(commit=False)
                system.tenant = request.tenant
                system.save()
                write_audit_log(
                    request.user,
                    system,
                    "create",
                    changes={"number": system.number, "domain": system.system_domain},
                    tenant=request.tenant,
                )
            messages.success(request, f"Building system {system.number} created.")
            return redirect("assets:asset_building_system_detail", pk=system.pk)
    else:
        initial = {}
        space_id = parse_pos_int(request.GET.get("facility_space"))
        if space_id is not None:
            space = (
                assets_scope(AssetFacilitySpace.objects.all(), request)
                .filter(pk=space_id)
                .only("pk")
                .first()
            )
            if space is not None:
                initial["facility_space"] = space.pk
        form = AssetBuildingSystemForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "assets/spacefacilityasset/asset_building_system/form.html",
        {
            "form": form,
            "system": None,
            "is_edit": False,
            "title": "New Building System",
        },
    )


@login_required
def asset_building_system_detail(request, pk):
    """Display HVAC comfort optimization, MEP specs, FCA metrics, and chargebacks."""
    system = assets_object(
        request,
        AssetBuildingSystem,
        pk,
        select_related=(
            "facility_space",
            "operational_asset",
            "fixed_asset",
            "latest_energy_reading",
            "maintenance_schedule",
            "operating_permit",
            "schematic_document",
            "service_vendor",
            "org_unit",
        ),
    )
    linked_chargebacks = (
        system.space_chargebacks.filter(tenant=request.tenant)
        .select_related("charged_org_unit", "occupant_party")
        .order_by("-period_start")[:10]
    )

    return render(
        request,
        "assets/spacefacilityasset/asset_building_system/detail.html",
        {
            "system": system,
            "linked_chargebacks": linked_chargebacks,
            "can_edit": not system.is_locked,
            "can_delete": not system.is_locked,
        },
    )


@login_required
def asset_building_system_edit(request, pk):
    """Edit an active or standby building system."""
    system = assets_object(request, AssetBuildingSystem, pk)
    if system.is_locked:
        messages.error(
            request,
            f"Building system {system.number} is decommissioned and locked from editing.",
        )
        return redirect("assets:asset_building_system_detail", pk=system.pk)

    if request.method == "POST":
        form = AssetBuildingSystemForm(request.POST, instance=system, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                system = form.save()
                write_audit_log(
                    request.user,
                    system,
                    "update",
                    changes={"number": system.number, "domain": system.system_domain},
                    tenant=request.tenant,
                )
            messages.success(request, f"Building system {system.number} updated.")
            return redirect("assets:asset_building_system_detail", pk=system.pk)
    else:
        form = AssetBuildingSystemForm(instance=system, tenant=request.tenant)

    return render(
        request,
        "assets/spacefacilityasset/asset_building_system/form.html",
        {
            "form": form,
            "system": system,
            "is_edit": True,
            "title": f"Edit {system.number} — {system.name}",
        },
    )


@login_required
@require_POST
def asset_building_system_delete(request, pk):
    """Delete a non-decommissioned building system."""
    system = assets_object(request, AssetBuildingSystem, pk)
    if system.is_locked:
        messages.error(request, f"Cannot delete {system.number}: system is decommissioned.")
        return redirect("assets:asset_building_system_detail", pk=system.pk)

    label = system.number
    try:
        with transaction.atomic():
            write_audit_log(
                request.user,
                system,
                "delete",
                changes={"number": system.number, "domain": system.system_domain},
                tenant=request.tenant,
            )
            system.delete()
    except ProtectedError:
        messages.error(request, f"Cannot delete {label}: dependent records reference it.")
        return redirect("assets:asset_building_system_detail", pk=pk)

    messages.success(request, f"Building system {label} deleted.")
    return redirect("assets:asset_building_system_list")


@login_required
@require_POST
def asset_building_system_evaluate_comfort(request, pk):
    """Evaluate HVAC comfort band against temperature and humidity setpoints."""
    with transaction.atomic():
        system = get_object_or_404(
            AssetBuildingSystem.objects.select_for_update(),
            pk=pk,
            tenant=request.tenant,
        )
        new_comfort = system.compute_comfort_status()
        system.comfort_status = new_comfort
        system.save(update_fields=["comfort_status", "updated_at"])
        write_audit_log(
            request.user,
            system,
            "comfort",
            changes={"comfort_status": new_comfort},
            tenant=request.tenant,
        )
    messages.success(
        request,
        f"System {system.number} comfort status evaluated: {system.get_comfort_status_display()}.",
    )
    return redirect("assets:asset_building_system_detail", pk=system.pk)


@login_required
@require_POST
def asset_building_system_record_inspection(request, pk):
    """Record a completed statutory inspection today and schedule next annual due date."""
    with transaction.atomic():
        system = get_object_or_404(
            AssetBuildingSystem.objects.select_for_update(),
            pk=pk,
            tenant=request.tenant,
        )
        if system.is_locked:
            messages.error(request, f"System {system.number} is decommissioned.")
            return redirect("assets:asset_building_system_detail", pk=system.pk)
        today = timezone.now().date()
        system.last_statutory_inspection_date = today
        system.next_inspection_due_date = today + timedelta(days=365)
        system.save()
        write_audit_log(
            request.user,
            system,
            "inspect",
            changes={"last_statutory_inspection_date": str(today)},
            tenant=request.tenant,
        )
    messages.success(
        request,
        f"Statutory inspection recorded for {system.number} (next due {system.next_inspection_due_date}).",
    )
    return redirect("assets:asset_building_system_detail", pk=system.pk)


@login_required
@require_POST
def asset_building_system_flag_maintenance(request, pk):
    """Place building system into Under Maintenance status."""
    with transaction.atomic():
        system = get_object_or_404(
            AssetBuildingSystem.objects.select_for_update(),
            pk=pk,
            tenant=request.tenant,
        )
        if system.is_locked:
            messages.error(request, f"System {system.number} is decommissioned.")
            return redirect("assets:asset_building_system_detail", pk=system.pk)
        system.status = "under_maintenance"
        system.save()
        write_audit_log(
            request.user,
            system,
            "maint",
            changes={"status": "under_maintenance"},
            tenant=request.tenant,
        )
    messages.success(request, f"System {system.number} placed Under Maintenance.")
    return redirect("assets:asset_building_system_detail", pk=system.pk)


@login_required
@require_POST
def asset_building_system_restore_operational(request, pk):
    """Restore a degraded/maintenance/standby system to Operational."""
    with transaction.atomic():
        system = get_object_or_404(
            AssetBuildingSystem.objects.select_for_update(),
            pk=pk,
            tenant=request.tenant,
        )
        if system.status == "decommissioned":
            messages.error(request, f"Decommissioned system {system.number} cannot be restored directly.")
            return redirect("assets:asset_building_system_detail", pk=system.pk)
        system.status = "operational"
        system.save()
        write_audit_log(
            request.user,
            system,
            "restore",
            changes={"status": "operational"},
            tenant=request.tenant,
        )
    messages.success(request, f"System {system.number} restored to Operational.")
    return redirect("assets:asset_building_system_detail", pk=system.pk)


@tenant_admin_required
@require_POST
def asset_building_system_decommission(request, pk):
    """Decommission a building system (admin only)."""
    with transaction.atomic():
        system = get_object_or_404(
            AssetBuildingSystem.objects.select_for_update(),
            pk=pk,
            tenant=request.tenant,
        )
        if system.status == "decommissioned":
            messages.info(request, f"System {system.number} is already decommissioned.")
            return redirect("assets:asset_building_system_detail", pk=system.pk)
        system.status = "decommissioned"
        system.save()
        write_audit_log(
            request.user,
            system,
            "decomm",
            changes={"status": "decommissioned"},
            tenant=request.tenant,
        )
    messages.success(request, f"System {system.number} decommissioned.")
    return redirect("assets:asset_building_system_detail", pk=system.pk)
