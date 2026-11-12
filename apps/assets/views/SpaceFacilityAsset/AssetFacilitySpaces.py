"""Views for AssetFacilitySpace (11.17 Floor Plan & Space Mapping)."""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, ProtectedError, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.assets.forms.SpaceFacilityAsset.AssetFacilitySpaces import AssetFacilitySpaceForm
from apps.assets.models.AssetDocumentKnowledge._validators import is_asset_document_readable
from apps.assets.models.SpaceFacilityAsset.AssetFacilitySpaces import AssetFacilitySpace
from apps.assets.views._common import assets_object, assets_scope
from apps.assets.views.SpaceFacilityAsset._helpers import (
    PAGE_SIZE,
    apply_choice_filter,
    apply_fk_filter,
    csv_export_response,
    is_tenant_admin_user,
    serve_protected_floor_plan,
)
from apps.core.decorators import tenant_admin_required
from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log


def _filtered_spaces_queryset(request):
    base_qs = assets_scope(AssetFacilitySpace.objects.all(), request)
    qs = base_qs.select_related(
        "parent",
        "org_unit",
    ).defer("notes")

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(code__icontains=q)
            | Q(name__icontains=q)
            | Q(cad_layer_ref__icontains=q)
            | Q(bim_guid__icontains=q)
            | Q(bim_level_ref__icontains=q)
        )

    qs = apply_choice_filter(
        qs, request, "space_level", allowed_values=dict(AssetFacilitySpace.SPACE_LEVEL_CHOICES)
    )
    qs = apply_choice_filter(
        qs, request, "space_category", allowed_values=dict(AssetFacilitySpace.SPACE_CATEGORY_CHOICES)
    )
    qs = apply_choice_filter(
        qs,
        request,
        "occupancy_status",
        allowed_values=dict(AssetFacilitySpace.OCCUPANCY_STATUS_CHOICES),
    )
    qs = apply_choice_filter(
        qs, request, "status", allowed_values=dict(AssetFacilitySpace.STATUS_CHOICES)
    )
    qs = apply_fk_filter(qs, request, "org_unit")
    qs = apply_fk_filter(qs, request, "parent")
    return base_qs, qs.order_by("code", "name", "-number"), q


def _can_delete_space(space):
    if space.is_locked:
        return False
    return not (
        space.child_spaces.exists()
        or space.building_systems.exists()
        or space.furniture_fixtures.exists()
        or space.space_chargebacks.exists()
        or space.incoming_furniture_fixtures.exists()
    )


@login_required
def asset_facility_space_list(request):
    """List tenant-scoped facility spaces, BOMA metrics, and utilization."""
    base_qs, qs, q = _filtered_spaces_queryset(request)

    kpis = base_qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        underutilized=Count("id", filter=Q(occupancy_status="underutilized")),
        vacant=Count("id", filter=Q(occupancy_status="vacant")),
        usable_sqft=Sum("usable_area_sqft", filter=Q(status="active")),
    )

    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    org_units = (
        OrgUnit.objects.filter(tenant=request.tenant)
        .only("id", "name")
        .order_by("name")
    )
    parent_spaces = (
        assets_scope(AssetFacilitySpace.objects.all(), request)
        .filter(space_level__in=("building", "floor", "wing_zone"))
        .only("id", "number", "code", "name")
        .order_by("code", "name")
    )

    return render(
        request,
        "assets/spacefacilityasset/asset_facility_space/list.html",
        {
            "spaces": page_obj,
            "paginator": paginator,
            "page_obj": page_obj,
            "is_paginated": page_obj.has_other_pages(),
            "total_count": kpis["total"] or 0,
            "active_count": kpis["active"] or 0,
            "underutilized_count": kpis["underutilized"] or 0,
            "vacant_count": kpis["vacant"] or 0,
            "total_usable_sqft": kpis["usable_sqft"] or Decimal("0.00"),
            "level_choices": AssetFacilitySpace.SPACE_LEVEL_CHOICES,
            "category_choices": AssetFacilitySpace.SPACE_CATEGORY_CHOICES,
            "occupancy_choices": AssetFacilitySpace.OCCUPANCY_STATUS_CHOICES,
            "status_choices": AssetFacilitySpace.STATUS_CHOICES,
            "org_units": org_units,
            "parent_spaces": parent_spaces,
            "search_query": q,
        },
    )


@login_required
def asset_facility_space_export_csv(request):
    """Export filtered facility spaces as a formula-safe CSV attachment."""
    _, qs, _ = _filtered_spaces_queryset(request)
    headers = [
        "Number",
        "Code",
        "Name",
        "Level",
        "Category",
        "Parent Space",
        "Org Unit",
        "Gross SqFt",
        "Rentable SqFt",
        "Usable SqFt",
        "Seat Capacity",
        "Headcount",
        "Utilization %",
        "Occupancy Status",
        "Status",
        "CAD Layer",
        "BIM GUID",
    ]
    rows = (
        [
            s.number,
            s.code,
            s.name,
            s.get_space_level_display(),
            s.get_space_category_display(),
            s.parent.code if s.parent else "",
            s.org_unit.name if s.org_unit else "",
            s.gross_area_sqft,
            s.rentable_area_sqft,
            s.usable_area_sqft,
            s.design_seat_capacity,
            s.current_headcount,
            s.utilization_pct,
            s.get_occupancy_status_display(),
            s.get_status_display(),
            s.cad_layer_ref,
            s.bim_guid,
        ]
        for s in qs.iterator(chunk_size=500)
    )
    return csv_export_response(filename="facility_spaces.csv", headers=headers, rows=rows)


@login_required
def asset_facility_space_create(request):
    """Create a new architectural facility space record."""
    if request.tenant is None:
        messages.error(request, "An active tenant workspace is required to create a facility space.")
        return redirect("assets:asset_facility_space_list")

    if request.method == "POST":
        form = AssetFacilitySpaceForm(
            request.POST, request.FILES, tenant=request.tenant, user=request.user
        )
        if form.is_valid():
            with transaction.atomic():
                space = form.save(commit=False)
                space.tenant = request.tenant
                space.save()
                write_audit_log(
                    request.user,
                    space,
                    "create",
                    changes={"number": space.number, "code": space.code, "level": space.space_level},
                    tenant=request.tenant,
                )
            messages.success(request, f"Facility space {space.number} ({space.code}) created.")
            return redirect("assets:asset_facility_space_detail", pk=space.pk)
    else:
        form = AssetFacilitySpaceForm(tenant=request.tenant, user=request.user)

    return render(
        request,
        "assets/spacefacilityasset/asset_facility_space/form.html",
        {
            "form": form,
            "space": None,
            "is_edit": False,
            "title": "New Facility Space",
        },
    )


@login_required
def asset_facility_space_detail(request, pk):
    """Display space BOMA metrics, CAD/BIM mapping, child spaces, systems, FF&E, and chargebacks."""
    space = assets_object(
        request,
        AssetFacilitySpace,
        pk,
        select_related=(
            "parent",
            "org_unit",
            "scm_location",
            "gis_mapping",
            "floor_plan_document",
            "space_steward",
        ),
    )
    child_spaces = list(
        space.child_spaces.filter(tenant=request.tenant).order_by("code", "name")[:20]
    )
    mounted_systems = list(
        space.building_systems.filter(tenant=request.tenant)
        .order_by("system_domain", "name")[:20]
    )
    placed_ffe = list(
        space.furniture_fixtures.filter(tenant=request.tenant)
        .order_by("ffe_category", "name")[:20]
    )
    active_chargebacks = list(
        space.space_chargebacks.filter(tenant=request.tenant)
        .order_by("-period_start")[:10]
    )

    admin_user = is_tenant_admin_user(request.user)
    if not admin_user or space.is_locked:
        can_delete = False
    elif child_spaces or mounted_systems or placed_ffe or active_chargebacks:
        can_delete = False
    else:
        can_delete = not space.incoming_furniture_fixtures.exists()

    return render(
        request,
        "assets/spacefacilityasset/asset_facility_space/detail.html",
        {
            "space": space,
            "child_spaces": child_spaces,
            "mounted_systems": mounted_systems,
            "placed_ffe": placed_ffe,
            "active_chargebacks": active_chargebacks,
            "can_edit": not space.is_locked,
            "can_delete": can_delete,
            "can_view_floor_plan_document": is_asset_document_readable(
                space.floor_plan_document, request.user
            ),
        },
    )


@login_required
def asset_facility_space_edit(request, pk):
    """Edit an active/planned/renovation facility space."""
    if request.method == "POST":
        with transaction.atomic():
            space = get_object_or_404(
                assets_scope(AssetFacilitySpace.objects.select_for_update(), request),
                pk=pk,
            )
            if space.is_locked:
                messages.error(
                    request,
                    f"Facility space {space.number} is decommissioned and locked from editing.",
                )
                return redirect("assets:asset_facility_space_detail", pk=space.pk)
            form = AssetFacilitySpaceForm(
                request.POST, request.FILES, instance=space, tenant=request.tenant, user=request.user
            )
            if form.is_valid():
                space = form.save()
                write_audit_log(
                    request.user,
                    space,
                    "update",
                    changes={"number": space.number, "code": space.code},
                    tenant=request.tenant,
                )
                messages.success(request, f"Facility space {space.number} updated.")
                return redirect("assets:asset_facility_space_detail", pk=space.pk)
    else:
        space = assets_object(request, AssetFacilitySpace, pk)
        if space.is_locked:
            messages.error(
                request,
                f"Facility space {space.number} is decommissioned and locked from editing.",
            )
            return redirect("assets:asset_facility_space_detail", pk=space.pk)
        form = AssetFacilitySpaceForm(instance=space, tenant=request.tenant, user=request.user)

    return render(
        request,
        "assets/spacefacilityasset/asset_facility_space/form.html",
        {
            "form": form,
            "space": space,
            "is_edit": True,
            "title": f"Edit {space.number} — {space.code}",
        },
    )


@login_required
@tenant_admin_required
@require_POST
def asset_facility_space_delete(request, pk):
    """Delete an unlinked, non-decommissioned facility space (tenant admin only)."""
    label = "facility space"
    try:
        with transaction.atomic():
            space = get_object_or_404(
                assets_scope(AssetFacilitySpace.objects.select_for_update(), request),
                pk=pk,
            )
            label = space.number
            if not _can_delete_space(space):
                messages.error(
                    request,
                    f"Cannot delete {space.number}: decommissioned spaces or spaces with linked systems, FF&E, child spaces, or chargebacks cannot be deleted.",
                )
                return redirect("assets:asset_facility_space_detail", pk=space.pk)
            write_audit_log(
                request.user,
                space,
                "delete",
                changes={"number": space.number, "code": space.code},
                tenant=request.tenant,
            )
            space.delete()
    except ProtectedError:
        messages.error(
            request,
            f"Cannot delete {label}: dependent systems, FF&E, or chargebacks still reference it.",
        )
        return redirect("assets:asset_facility_space_detail", pk=pk)

    messages.success(request, f"Facility space {label} deleted.")
    return redirect("assets:asset_facility_space_list")


@login_required
def asset_facility_space_floor_plan_download(request, pk):
    """Download the uploaded floor plan attachment with nosniff and attachment headers."""
    space = assets_object(request, AssetFacilitySpace, pk)
    return serve_protected_floor_plan(space)


@login_required
@require_POST
def asset_facility_space_recalculate_utilization(request, pk):
    """Recompute occupancy status and utilization metrics for a space."""
    with transaction.atomic():
        space = get_object_or_404(
            assets_scope(AssetFacilitySpace.objects.select_for_update(), request),
            pk=pk,
        )
        if space.is_locked:
            messages.error(request, f"Facility space {space.number} is decommissioned and locked.")
            return redirect("assets:asset_facility_space_detail", pk=space.pk)
        new_occ = space.compute_occupancy_status()
        space.occupancy_status = new_occ
        space.save(update_fields=["occupancy_status", "updated_at"])
        write_audit_log(
            request.user,
            space,
            "recalc",
            changes={
                "occupancy_status": new_occ,
                "utilization_pct": str(space.utilization_pct),
            },
            tenant=request.tenant,
        )
    messages.success(
        request,
        f"Space {space.number} utilization recalculated ({space.utilization_pct}% — {space.get_occupancy_status_display()}).",
    )
    return redirect("assets:asset_facility_space_detail", pk=space.pk)


@login_required
@require_POST
def asset_facility_space_mark_under_renovation(request, pk):
    """Place an active/planned space into Under Renovation status."""
    with transaction.atomic():
        space = get_object_or_404(
            assets_scope(AssetFacilitySpace.objects.select_for_update(), request),
            pk=pk,
        )
        if space.is_locked:
            messages.error(request, f"Space {space.number} is decommissioned.")
            return redirect("assets:asset_facility_space_detail", pk=space.pk)
        space.status = "under_renovation"
        space.save()
        write_audit_log(
            request.user,
            space,
            "renovate",
            changes={"status": "under_renovation"},
            tenant=request.tenant,
        )
    messages.success(request, f"Space {space.number} marked Under Renovation.")
    return redirect("assets:asset_facility_space_detail", pk=space.pk)


@login_required
@require_POST
def asset_facility_space_activate(request, pk):
    """Activate a planned or renovation space."""
    with transaction.atomic():
        space = get_object_or_404(
            assets_scope(AssetFacilitySpace.objects.select_for_update(), request),
            pk=pk,
        )
        if space.status == "decommissioned" and not is_tenant_admin_user(request.user):
            messages.error(
                request,
                f"Only a workspace admin can reactivate decommissioned space {space.number}.",
            )
            return redirect("assets:asset_facility_space_detail", pk=space.pk)
        space.status = "active"
        space.save()
        write_audit_log(
            request.user,
            space,
            "activate",
            changes={"status": "active"},
            tenant=request.tenant,
        )
    messages.success(request, f"Space {space.number} is now Active.")
    return redirect("assets:asset_facility_space_detail", pk=space.pk)


@tenant_admin_required
@require_POST
def asset_facility_space_decommission(request, pk):
    """Decommission a facility space (admin only)."""
    with transaction.atomic():
        space = get_object_or_404(
            assets_scope(AssetFacilitySpace.objects.select_for_update(), request),
            pk=pk,
        )
        if space.status == "decommissioned":
            messages.info(request, f"Space {space.number} is already decommissioned.")
            return redirect("assets:asset_facility_space_detail", pk=space.pk)
        space.status = "decommissioned"
        space.save()
        write_audit_log(
            request.user,
            space,
            "decomm",
            changes={"status": "decommissioned"},
            tenant=request.tenant,
        )
    messages.success(request, f"Space {space.number} decommissioned.")
    return redirect("assets:asset_facility_space_detail", pk=space.pk)
