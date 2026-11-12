"""Views for AssetFurnitureFixture (11.17 Furniture & Fixture Tracking / IMAC)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, ProtectedError, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.SpaceFacilityAsset.AssetFurnitureFixtures import AssetFurnitureFixtureForm
from apps.assets.models.AssetInventoryTracking.AssetMovementLogs import AssetMovementLog
from apps.assets.models.SpaceFacilityAsset.AssetFacilitySpaces import AssetFacilitySpace
from apps.assets.models.SpaceFacilityAsset.AssetFurnitureFixtures import AssetFurnitureFixture
from apps.assets.views._common import assets_object, assets_scope
from apps.assets.views.SpaceFacilityAsset._helpers import (
    PAGE_SIZE,
    apply_choice_filter,
    apply_fk_filter,
    csv_export_response,
    is_tenant_admin_user,
    parse_pos_int,
)
from apps.core.decorators import tenant_admin_required
from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log


def _filtered_fixtures_queryset(request):
    base_qs = assets_scope(AssetFurnitureFixture.objects.all(), request)
    qs = base_qs.select_related(
        "facility_space",
        "target_space",
        "assigned_org_unit",
    ).defer("move_notes")

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(name__icontains=q)
            | Q(asset_tag_code__icontains=q)
            | Q(manufacturer__icontains=q)
            | Q(model_sku__icontains=q)
            | Q(reconfiguration_batch_ref__icontains=q)
            | Q(facility_space__code__icontains=q)
        )

    qs = apply_choice_filter(
        qs, request, "ffe_category", allowed_values=dict(AssetFurnitureFixture.FFE_CATEGORY_CHOICES)
    )
    qs = apply_choice_filter(
        qs, request, "condition_grade", allowed_values=dict(AssetFurnitureFixture.CONDITION_GRADE_CHOICES)
    )
    qs = apply_choice_filter(
        qs, request, "move_status", allowed_values=dict(AssetFurnitureFixture.MOVE_STATUS_CHOICES)
    )
    qs = apply_fk_filter(qs, request, "facility_space")
    qs = apply_fk_filter(qs, request, "assigned_org_unit")
    return base_qs, qs, q


@login_required
def asset_furniture_fixture_list(request):
    """List FF&E inventory & IMAC schedule with KPI aggregates and filters."""
    base_qs, qs, q = _filtered_fixtures_queryset(request)
    kpis = base_qs.aggregate(
        total=Count("id"),
        pending_moves=Count(
            "id",
            filter=Q(move_status__in=("move_requested", "scheduled_reconfig", "in_transit")),
        ),
        in_place=Count("id", filter=Q(move_status__in=("in_place", "relocated"))),
        total_qty=Sum("quantity"),
    )

    paginator = Paginator(qs.order_by("facility_space", "name", "-number"), PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    spaces = (
        assets_scope(AssetFacilitySpace.objects.all(), request)
        .only("id", "number", "code", "name")
        .order_by("code", "name")
    )
    org_units = (
        assets_scope(OrgUnit.objects.all(), request)
        .only("id", "name")
        .order_by("name")
    )

    return render(
        request,
        "assets/spacefacilityasset/asset_furniture_fixture/list.html",
        {
            "fixtures": page_obj,
            "paginator": paginator,
            "page_obj": page_obj,
            "is_paginated": page_obj.has_other_pages(),
            "total_count": kpis["total"] or 0,
            "pending_move_count": kpis["pending_moves"] or 0,
            "in_place_count": kpis["in_place"] or 0,
            "total_quantity": kpis["total_qty"] or 0,
            "category_choices": AssetFurnitureFixture.FFE_CATEGORY_CHOICES,
            "condition_choices": AssetFurnitureFixture.CONDITION_GRADE_CHOICES,
            "move_status_choices": AssetFurnitureFixture.MOVE_STATUS_CHOICES,
            "spaces": spaces,
            "org_units": org_units,
            "search_query": q,
        },
    )


@login_required
def asset_furniture_fixture_export_csv(request):
    """Export filtered FF&E & IMAC register as formula-safe CSV."""
    _base, qs, _q = _filtered_fixtures_queryset(request)
    rows = (
        [
            item.number,
            item.name,
            item.get_ffe_category_display(),
            item.asset_tag_code,
            item.facility_space.code if item.facility_space else "",
            item.target_space.code if item.target_space else "",
            item.assigned_org_unit.name if item.assigned_org_unit else "",
            item.quantity,
            f"{item.unit_replacement_cost:.2f}",
            f"{item.total_replacement_value:.2f}",
            item.get_condition_grade_display(),
            item.get_move_status_display(),
            item.reconfiguration_batch_ref,
            item.move_scheduled_date.isoformat() if item.move_scheduled_date else "",
        ]
        for item in qs.order_by("facility_space__code", "name", "-number").iterator(chunk_size=500)
    )
    return csv_export_response(
        filename="asset_furniture_fixtures.csv",
        headers=[
            "Number",
            "Name",
            "Category",
            "Asset Tag",
            "Current Space",
            "Target Space",
            "Org Unit",
            "Quantity",
            "Unit Cost",
            "Total Replacement Value",
            "Condition",
            "Move Status",
            "IMAC Batch",
            "Scheduled Date",
        ],
        rows=rows,
    )


@login_required
def asset_furniture_fixture_create(request):
    """Create a new FF&E record with optional tenant-scoped ?facility_space= prefill."""
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        messages.error(request, "An active tenant workspace is required to create an FF&E item.")
        return redirect("assets:asset_furniture_fixture_list")
    initial = {}
    space_pk = parse_pos_int(request.GET.get("facility_space"))
    if space_pk is not None and tenant is not None:
        space = AssetFacilitySpace.objects.filter(tenant=tenant, pk=space_pk).first()
        if space is not None:
            initial["facility_space"] = space.pk

    if request.method == "POST":
        form = AssetFurnitureFixtureForm(request.POST, tenant=tenant)
        if form.is_valid():
            with transaction.atomic():
                fixture = form.save(commit=False)
                fixture.tenant = tenant
                fixture.save()
                write_audit_log(
                    request.user,
                    fixture,
                    "create",
                    changes={"number": fixture.number, "category": fixture.ffe_category},
                    tenant=tenant,
                )
            messages.success(request, f"Furniture / fixture {fixture.number} created.")
            return redirect("assets:asset_furniture_fixture_detail", pk=fixture.pk)
    else:
        form = AssetFurnitureFixtureForm(initial=initial, tenant=tenant)

    return render(
        request,
        "assets/spacefacilityasset/asset_furniture_fixture/form.html",
        {
            "form": form,
            "fixture": None,
            "is_edit": False,
            "title": "New Furniture / Fixture",
        },
    )


@login_required
def asset_furniture_fixture_detail(request, pk):
    """View FF&E specifications, IMAC move plan, and AssetMovementLog link."""
    fixture = get_object_or_404(
        assets_scope(
            AssetFurnitureFixture.objects.select_related(
                "facility_space",
                "target_space",
                "custodian_party",
                "assigned_org_unit",
                "operational_asset",
                "fixed_asset",
                "movement_log",
                "move_coordinator",
            ),
            request,
        ),
        pk=pk,
    )
    can_edit = not fixture.is_locked
    can_complete_move = (
        not fixture.is_locked
        and fixture.target_space_id is not None
        and fixture.target_space_id != fixture.facility_space_id
    )
    return render(
        request,
        "assets/spacefacilityasset/asset_furniture_fixture/detail.html",
        {
            "fixture": fixture,
            "can_edit": can_edit,
            "can_delete": is_tenant_admin_user(request.user) and can_edit,
            "can_complete_move": can_complete_move,
        },
    )


@login_required
def asset_furniture_fixture_edit(request, pk):
    """Edit FF&E record when not retired."""
    tenant = getattr(request, "tenant", None)
    if request.method == "POST":
        with transaction.atomic():
            fixture = get_object_or_404(
                assets_scope(AssetFurnitureFixture.objects.select_for_update(), request),
                pk=pk,
            )
            if fixture.is_locked:
                messages.error(request, f"Retired FF&E item {fixture.number} cannot be edited.")
                return redirect("assets:asset_furniture_fixture_detail", pk=fixture.pk)
            form = AssetFurnitureFixtureForm(request.POST, instance=fixture, tenant=tenant)
            if form.is_valid():
                fixture = form.save()
                write_audit_log(
                    request.user,
                    fixture,
                    "update",
                    changes={"number": fixture.number, "category": fixture.ffe_category},
                    tenant=tenant,
                )
                messages.success(request, f"Furniture / fixture {fixture.number} updated.")
                return redirect("assets:asset_furniture_fixture_detail", pk=fixture.pk)
    else:
        fixture = assets_object(request, AssetFurnitureFixture, pk)
        if fixture.is_locked:
            messages.error(request, f"Retired FF&E item {fixture.number} cannot be edited.")
            return redirect("assets:asset_furniture_fixture_detail", pk=fixture.pk)
        form = AssetFurnitureFixtureForm(instance=fixture, tenant=tenant)

    return render(
        request,
        "assets/spacefacilityasset/asset_furniture_fixture/form.html",
        {
            "form": form,
            "fixture": fixture,
            "is_edit": True,
            "title": f"Edit {fixture.number}",
        },
    )


@login_required
@tenant_admin_required
@require_POST
def asset_furniture_fixture_delete(request, pk):
    """Delete an unlocked FF&E item (tenant admin only)."""
    number = "FF&E item"
    try:
        with transaction.atomic():
            fixture = get_object_or_404(
                assets_scope(AssetFurnitureFixture.objects.select_for_update(), request),
                pk=pk,
            )
            number = fixture.number
            if fixture.is_locked:
                messages.error(request, f"Retired FF&E item {fixture.number} cannot be deleted.")
                return redirect("assets:asset_furniture_fixture_detail", pk=fixture.pk)
            write_audit_log(
                request.user,
                fixture,
                "delete",
                changes={"number": number, "category": fixture.ffe_category},
                tenant=getattr(request, "tenant", None),
            )
            fixture.delete()
    except ProtectedError:
        messages.error(request, f"Cannot delete {number} because linked records depend on it.")
        return redirect("assets:asset_furniture_fixture_detail", pk=pk)
    messages.success(request, f"Furniture / fixture {number} deleted.")
    return redirect("assets:asset_furniture_fixture_list")


@login_required
@require_POST
def asset_furniture_fixture_request_move(request, pk):
    """Transition an active FF&E item to Move Requested."""
    with transaction.atomic():
        fixture = get_object_or_404(
            assets_scope(AssetFurnitureFixture.objects.select_for_update(), request),
            pk=pk,
        )
        if fixture.is_locked:
            messages.error(request, f"Retired item {fixture.number} cannot request a move.")
            return redirect("assets:asset_furniture_fixture_detail", pk=fixture.pk)
        if not fixture.target_space_id or fixture.target_space_id == fixture.facility_space_id:
            messages.error(request, "Set a different target space before requesting an IMAC move.")
            return redirect("assets:asset_furniture_fixture_detail", pk=fixture.pk)
        fixture.move_status = "move_requested"
        fixture.save(update_fields=["move_status", "updated_at"])
        write_audit_log(
            request.user,
            fixture,
            "req_move",
            changes={"number": fixture.number, "target_space": fixture.target_space.code},
            tenant=fixture.tenant,
        )
    messages.success(request, f"IMAC move requested for {fixture.number}.")
    return redirect("assets:asset_furniture_fixture_detail", pk=fixture.pk)


@login_required
@require_POST
def asset_furniture_fixture_schedule_reconfig(request, pk):
    """Schedule workspace reconfiguration / move batch for FF&E item."""
    with transaction.atomic():
        fixture = get_object_or_404(
            assets_scope(AssetFurnitureFixture.objects.select_for_update(), request),
            pk=pk,
        )
        if fixture.is_locked:
            messages.error(request, f"Retired item {fixture.number} cannot be scheduled.")
            return redirect("assets:asset_furniture_fixture_detail", pk=fixture.pk)
        if not fixture.target_space_id or fixture.target_space_id == fixture.facility_space_id:
            messages.error(request, "Set a different target space before scheduling reconfiguration.")
            return redirect("assets:asset_furniture_fixture_detail", pk=fixture.pk)
        fixture.move_status = "scheduled_reconfig"
        fixture.save(update_fields=["move_status", "updated_at"])
        write_audit_log(
            request.user,
            fixture,
            "sched_mv",
            changes={"number": fixture.number, "batch": fixture.reconfiguration_batch_ref},
            tenant=fixture.tenant,
        )
    messages.success(request, f"Reconfiguration scheduled for {fixture.number}.")
    return redirect("assets:asset_furniture_fixture_detail", pk=fixture.pk)


@login_required
@require_POST
def asset_furniture_fixture_complete_move(request, pk):
    """Execute relocation to target_space and log AssetMovementLog when operational_asset is linked."""
    with transaction.atomic():
        fixture = get_object_or_404(
            assets_scope(
                AssetFurnitureFixture.objects.select_for_update().select_related(
                    "facility_space",
                    "target_space",
                    "facility_space__scm_location",
                    "target_space__scm_location",
                    "facility_space__org_unit",
                    "target_space__org_unit",
                    "assigned_org_unit",
                    "operational_asset",
                ),
                request,
            ),
            pk=pk,
        )
        if fixture.is_locked:
            messages.error(request, f"Retired item {fixture.number} cannot be relocated.")
            return redirect("assets:asset_furniture_fixture_detail", pk=fixture.pk)
        if not fixture.target_space_id or fixture.target_space_id == fixture.facility_space_id:
            messages.error(request, "Target space must be set and distinct from the current space to complete a move.")
            return redirect("assets:asset_furniture_fixture_detail", pk=fixture.pk)

        origin_space = fixture.facility_space
        dest_space = fixture.target_space
        origin_code = origin_space.code
        dest_code = dest_space.code

        fixture.facility_space = dest_space
        fixture.target_space = None
        fixture.move_status = "relocated"
        fixture.move_completed_at = timezone.now()

        if fixture.operational_asset_id:
            movement = AssetMovementLog.objects.create(
                tenant=fixture.tenant,
                title=f"IMAC Relocation: {fixture.number} ({origin_code} -> {dest_code})"[:200],
                asset=fixture.operational_asset,
                movement_type="room_reassignment",
                from_location=origin_space.scm_location,
                from_org_unit=fixture.assigned_org_unit or origin_space.org_unit,
                from_room_bin=f"{origin_code} — {origin_space.name}"[:100],
                to_location=dest_space.scm_location,
                to_org_unit=dest_space.org_unit or fixture.assigned_org_unit,
                to_room_bin=f"{dest_code} — {dest_space.name}"[:100],
                from_custodian=fixture.custodian_party,
                to_custodian=fixture.custodian_party,
                status="received",
            )
            fixture.movement_log = movement

        fixture.save(
            update_fields=[
                "facility_space",
                "target_space",
                "move_status",
                "move_completed_at",
                "movement_log",
                "updated_at",
            ]
        )
        write_audit_log(
            request.user,
            fixture,
            "comp_move",
            changes={"number": fixture.number, "from": origin_code, "to": dest_code},
            tenant=fixture.tenant,
        )
    messages.success(request, f"Moved {fixture.number} from {origin_code} to {dest_code}.")
    return redirect("assets:asset_furniture_fixture_detail", pk=fixture.pk)


@login_required
@tenant_admin_required
@require_POST
def asset_furniture_fixture_retire(request, pk):
    """Retire and lock an FF&E item (tenant admin only)."""
    with transaction.atomic():
        fixture = get_object_or_404(
            assets_scope(AssetFurnitureFixture.objects.select_for_update(), request),
            pk=pk,
        )
        if fixture.move_status == "retired":
            messages.info(request, f"FF&E item {fixture.number} is already retired.")
            return redirect("assets:asset_furniture_fixture_detail", pk=fixture.pk)
        fixture.move_status = "retired"
        fixture.save(update_fields=["move_status", "updated_at"])
        write_audit_log(
            request.user,
            fixture,
            "retire",
            changes={"number": fixture.number, "move_status": "retired"},
            tenant=fixture.tenant,
        )
    messages.warning(request, f"FF&E item {fixture.number} retired and locked.")
    return redirect("assets:asset_furniture_fixture_detail", pk=fixture.pk)
