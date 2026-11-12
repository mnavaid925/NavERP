"""
Unit tests for Module 11.17: Space & Facility Asset Management Models & Validators.
Covers AssetFacilitySpace [AFSP-], AssetBuildingSystem [AFBS-],
AssetFurnitureFixture [AFFE-], AssetSpaceChargeback [AFCB-],
shared validators, auto-numbering, constraints, badge classes,
derived metrics, status computation, upload hardening, on_delete behavior,
and cross-tenant FK isolation.
"""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone

import apps.assets.models as assets_models
import apps.assets.models.SpaceFacilityAsset as sfa_models
from apps.accounting.models import JournalEntry
from apps.assets.models import (
    AssetBuildingSystem,
    AssetFacilitySpace,
    AssetFurnitureFixture,
    AssetSpaceChargeback,
)
from apps.assets.models.SpaceFacilityAsset import (
    AssetBuildingSystem as DirectAssetBuildingSystem,
    AssetFacilitySpace as DirectAssetFacilitySpace,
    AssetFurnitureFixture as DirectAssetFurnitureFixture,
    AssetSpaceChargeback as DirectAssetSpaceChargeback,
)
from apps.assets.models.SpaceFacilityAsset._validators import (
    MAX_UPLOAD_BYTES,
    add_field_error,
    validate_non_negative,
    validate_pct_range,
    validate_safe_floor_plan_upload,
    validate_space_parent_cycle,
    validate_tenant_fks,
)

pytestmark = pytest.mark.django_db

_SPACEFACILITY_VALID_BADGE_CLASSES = {
    "badge-green",
    "badge-red",
    "badge-amber",
    "badge-info",
    "badge-muted",
    "badge-slate",
}


# =====================================================================
# Module-level Helpers (Must start with _spacefacility_*)
# =====================================================================


def _spacefacility_create_space(tenant, code="RM-101", name="Suite 101", **kwargs):
    data = {
        "tenant": tenant,
        "code": code,
        "name": name,
        "space_level": "room",
        "space_category": "office_workspace",
        "gross_area_sqft": Decimal("1200.00"),
        "rentable_area_sqft": Decimal("1100.00"),
        "usable_area_sqft": Decimal("1000.00"),
        "common_area_sqft": Decimal("100.00"),
        "annual_rate_per_sqft": Decimal("35.00"),
        "design_seat_capacity": 10,
        "current_headcount": 6,
        "status": "active",
    }
    data.update(kwargs)
    return AssetFacilitySpace.objects.create(**data)


def _spacefacility_create_system(tenant, space, name="AHU Unit 1", **kwargs):
    data = {
        "tenant": tenant,
        "name": name,
        "system_domain": "hvac_climate",
        "subsystem_type": "ahu_air_handler",
        "facility_space": space,
        "status": "operational",
    }
    data.update(kwargs)
    return AssetBuildingSystem.objects.create(**data)


def _spacefacility_create_furniture(tenant, space, name="Desk Pod 1", **kwargs):
    data = {
        "tenant": tenant,
        "name": name,
        "ffe_category": "workstation_desk",
        "facility_space": space,
        "quantity": 2,
        "unit_replacement_cost": Decimal("750.00"),
        "move_status": "in_place",
    }
    data.update(kwargs)
    return AssetFurnitureFixture.objects.create(**data)


def _spacefacility_create_chargeback(tenant, space, **kwargs):
    today = timezone.localdate()
    data = {
        "tenant": tenant,
        "title": "Monthly Space Chargeback",
        "coordination_type": "space_chargeback",
        "allocation_basis": "usable_sqft",
        "facility_space": space,
        "period_start": today.replace(day=1),
        "period_end": today,
        "base_cost_amount": Decimal("1000.00"),
        "status": "draft",
    }
    data.update(kwargs)
    return AssetSpaceChargeback.objects.create(**data)


# =====================================================================
# 1. Package Re-exports & Contract Registration
# =====================================================================


def test_spacefacility_package_reexports():
    expected_sfa = [
        "AssetFacilitySpace",
        "AssetBuildingSystem",
        "AssetFurnitureFixture",
        "AssetSpaceChargeback",
    ]
    assert sfa_models.__all__ == expected_sfa
    assert AssetFacilitySpace is DirectAssetFacilitySpace
    assert AssetBuildingSystem is DirectAssetBuildingSystem
    assert AssetFurnitureFixture is DirectAssetFurnitureFixture
    assert AssetSpaceChargeback is DirectAssetSpaceChargeback

    for symbol in expected_sfa:
        assert symbol in assets_models.__all__
        assert getattr(assets_models, symbol) is getattr(sfa_models, symbol)


# =====================================================================
# 2. Shared Validators (_validators.py)
# =====================================================================


def test_spacefacility_add_field_error_accumulates():
    errors = {}
    add_field_error(errors, "code", "First error")
    assert errors == {"code": ["First error"]}

    add_field_error(errors, "code", "Second error")
    assert errors == {"code": ["First error", "Second error"]}

    errors["scalar"] = "Initial scalar"
    add_field_error(errors, "scalar", "Appended scalar")
    assert errors == {
        "code": ["First error", "Second error"],
        "scalar": ["Initial scalar", "Appended scalar"],
    }


def test_spacefacility_validate_non_negative_and_pct_range():
    errors = {}
    validate_non_negative(None, errors, "a", "Field A")
    validate_non_negative(Decimal("0.00"), errors, "b", "Field B")
    validate_non_negative(Decimal("12.50"), errors, "c", "Field C")
    validate_non_negative(Decimal("-0.01"), errors, "d", "Field D")
    assert list(errors.keys()) == ["d"]

    pct_errors = {}
    validate_pct_range(None, pct_errors, "p0", "Pin 0")
    validate_pct_range(Decimal("0.00"), pct_errors, "p1", "Pin 1")
    validate_pct_range(Decimal("100.00"), pct_errors, "p2", "Pin 2")
    validate_pct_range(Decimal("-0.01"), pct_errors, "p_low", "Pin Low")
    validate_pct_range(Decimal("100.01"), pct_errors, "p_high", "Pin High")
    assert set(pct_errors.keys()) == {"p_low", "p_high"}


def test_spacefacility_validate_tenant_fks_requires_tenant_and_matches(
    tenant_a, tenant_b, org_unit_a, org_unit_b
):
    no_tenant_obj = SimpleNamespace(tenant_id=None, org_unit_id=org_unit_a.pk, org_unit=org_unit_a)
    errors = {}
    validate_tenant_fks(no_tenant_obj, errors, ("org_unit",))
    assert "__all__" in errors

    same_tenant_obj = SimpleNamespace(
        tenant_id=tenant_a.pk,
        org_unit_id=org_unit_a.pk,
        org_unit=org_unit_a,
    )
    ok_errors = {}
    validate_tenant_fks(same_tenant_obj, ok_errors, ("org_unit",))
    assert ok_errors == {}

    cross_tenant_obj = SimpleNamespace(
        tenant_id=tenant_a.pk,
        org_unit_id=org_unit_b.pk,
        org_unit=org_unit_b,
    )
    bad_errors = {}
    validate_tenant_fks(cross_tenant_obj, bad_errors, ("org_unit",))
    assert "org_unit" in bad_errors


def test_spacefacility_validate_safe_floor_plan_upload_rules():
    assert validate_safe_floor_plan_upload(None) is None

    committed_existing = SimpleNamespace(name="floor.svg", _committed=True, size=999)
    assert validate_safe_floor_plan_upload(committed_existing) is committed_existing

    svg_file = SimpleUploadedFile("floor.svg", b"<svg></svg>", content_type="image/svg+xml")
    with pytest.raises(ValidationError):
        validate_safe_floor_plan_upload(svg_file)

    no_ext_file = SimpleUploadedFile("floorplan", b"binary", content_type="application/octet-stream")
    with pytest.raises(ValidationError):
        validate_safe_floor_plan_upload(no_ext_file)

    oversize_file = SimpleNamespace(name="big_plan.pdf", size=MAX_UPLOAD_BYTES + 1, _committed=False)
    # Simulate an UploadedFile instance-like rejection via SimpleUploadedFile subclass
    big_upload = SimpleUploadedFile("big_plan.pdf", b"%PDF-1.4")
    big_upload.size = MAX_UPLOAD_BYTES + 1
    with pytest.raises(ValidationError):
        validate_safe_floor_plan_upload(big_upload)
    assert oversize_file.size > MAX_UPLOAD_BYTES

    valid_png = SimpleUploadedFile("floor.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")
    assert validate_safe_floor_plan_upload(valid_png) is valid_png


def test_spacefacility_validate_space_parent_cycle_max_depth(tenant_a):
    root = _spacefacility_create_space(tenant_a, code="D-00", name="Depth 0")
    cur = root
    for idx in range(1, 5):
        cur = _spacefacility_create_space(tenant_a, code=f"D-{idx:02d}", name=f"Depth {idx}", parent=cur)

    leaf = AssetFacilitySpace(tenant=tenant_a, code="D-LEAF", name="Leaf", parent=cur)
    errors = {}
    validate_space_parent_cycle(leaf, errors, max_depth=3)
    assert "parent" in errors


# =====================================================================
# 3. Auto-Numbering & Tenant-Scoped Uniqueness
# =====================================================================


def test_spacefacility_auto_number_prefixes_and_tenant_uniqueness(
    tenant_a,
    tenant_b,
    sfa_space_building_a,
    sfa_space_b,
    sfa_building_system_hvac_a,
    sfa_building_system_b,
    sfa_furniture_a,
    sfa_furniture_b,
    sfa_chargeback_draft_a,
    sfa_chargeback_b,
):
    assert sfa_space_building_a.number.startswith("AFSP-")
    assert sfa_space_b.number.startswith("AFSP-")
    assert sfa_building_system_hvac_a.number.startswith("AFBS-")
    assert sfa_building_system_b.number.startswith("AFBS-")
    assert sfa_furniture_a.number.startswith("AFFE-")
    assert sfa_furniture_b.number.startswith("AFFE-")
    assert sfa_chargeback_draft_a.number.startswith("AFCB-")
    assert sfa_chargeback_b.number.startswith("AFCB-")

    assert sfa_space_building_a.number == sfa_space_b.number == "AFSP-00001"
    assert sfa_building_system_hvac_a.number == sfa_building_system_b.number == "AFBS-00001"
    assert sfa_furniture_a.number == sfa_furniture_b.number == "AFFE-00001"
    assert sfa_chargeback_draft_a.number == sfa_chargeback_b.number == "AFCB-00001"

    # Same number rejected within same tenant, allowed across tenants
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssetFacilitySpace.objects.create(
                tenant=tenant_a,
                number=sfa_space_building_a.number,
                code="DUP-NUM-A",
                name="Duplicate Number",
            )

    custom_num = "AFSP-99999"
    space_a_custom = AssetFacilitySpace.objects.create(
        tenant=tenant_a,
        number=custom_num,
        code="X-NUM-A",
        name="Custom Number Tenant A",
    )
    space_b_custom = AssetFacilitySpace.objects.create(
        tenant=tenant_b,
        number=custom_num,
        code="X-NUM-B",
        name="Same Number Tenant B",
    )
    assert space_a_custom.number == space_b_custom.number == custom_num

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssetBuildingSystem.objects.create(
                tenant=tenant_a,
                number=sfa_building_system_hvac_a.number,
                name="Dup Sys",
                facility_space=sfa_space_building_a,
            )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssetFurnitureFixture.objects.create(
                tenant=tenant_a,
                number=sfa_furniture_a.number,
                name="Dup FFE",
                facility_space=sfa_space_building_a,
            )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssetSpaceChargeback.objects.create(
                tenant=tenant_a,
                number=sfa_chargeback_draft_a.number,
                title="Dup CB",
                facility_space=sfa_space_building_a,
                period_start=timezone.localdate(),
                period_end=timezone.localdate(),
            )


def test_spacefacility_space_code_uniqueness_and_blank_ffe_tag_safety(tenant_a, tenant_b, sfa_space_building_a):
    # Space code normalized to uppercase; duplicate code in same tenant violates constraint
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _spacefacility_create_space(tenant_a, code="sfa-bldg-a", name="Dup Code Lowercase")

    # Same code in tenant_b succeeds
    other_tenant_space = _spacefacility_create_space(
        tenant_b,
        code=sfa_space_building_a.code,
        name="Tenant B Same Code",
    )
    assert other_tenant_space.code == sfa_space_building_a.code

    # AssetFurnitureFixture allows multiple rows with blank asset_tag_code in the same tenant
    ffe1 = _spacefacility_create_furniture(tenant_a, sfa_space_building_a, name="Blank Tag 1", asset_tag_code="")
    ffe2 = _spacefacility_create_furniture(tenant_a, sfa_space_building_a, name="Blank Tag 2", asset_tag_code="")
    assert ffe1.pk != ffe2.pk


# =====================================================================
# 4. AssetFacilitySpace Invariants
# =====================================================================


def test_spacefacility_space_utilization_cost_and_occupancy_thresholds(tenant_a):
    # Zero capacity -> utilization 0.00; headcount 0 -> vacant
    vacant = _spacefacility_create_space(
        tenant_a,
        code="occ-vac",
        name="Vacant Room",
        rentable_area_sqft=Decimal("0.00"),
        usable_area_sqft=Decimal("500.00"),
        annual_rate_per_sqft=Decimal("20.00"),
        design_seat_capacity=0,
        current_headcount=0,
        status="active",
    )
    assert vacant.code == "OCC-VAC"
    assert vacant.utilization_pct == Decimal("0.00")
    assert vacant.annual_space_cost == Decimal("10000.00")  # falls back to usable_area_sqft
    assert vacant.occupancy_status == "vacant"

    # Underutilized (< 50%): 4 / 10 = 40.00%
    under = _spacefacility_create_space(
        tenant_a,
        code="OCC-UND",
        name="Underutilized Room",
        rentable_area_sqft=Decimal("1000.00"),
        usable_area_sqft=Decimal("800.00"),
        annual_rate_per_sqft=Decimal("30.00"),
        design_seat_capacity=10,
        current_headcount=4,
        status="active",
    )
    assert under.utilization_pct == Decimal("40.00")
    assert under.annual_space_cost == Decimal("30000.00")
    assert under.occupancy_status == "underutilized"

    # Occupied (>= 50%): 5 / 10 = 50.00%
    occ_boundary = _spacefacility_create_space(
        tenant_a,
        code="OCC-50",
        name="Boundary Occupied Room",
        design_seat_capacity=10,
        current_headcount=5,
        status="active",
    )
    assert occ_boundary.utilization_pct == Decimal("50.00")
    assert occ_boundary.occupancy_status == "occupied"

    # Over-capacity (> 100%) still computes exact utilization_pct and "occupied"
    occ_over = _spacefacility_create_space(
        tenant_a,
        code="OCC-OVER",
        name="Over-Seated Room",
        design_seat_capacity=10,
        current_headcount=12,
        status="active",
    )
    assert occ_over.utilization_pct == Decimal("120.00")
    assert occ_over.occupancy_status == "occupied"

    # Offline statuses override headcount
    for offline_status in ("under_renovation", "decommissioned"):
        occ_over.status = offline_status
        occ_over.save()
        assert occ_over.occupancy_status == "offline"


def test_spacefacility_space_clean_validation_and_cycles(
    tenant_a, tenant_b, sfa_space_building_a, sfa_space_floor_a, sfa_space_b, org_unit_b, location_b, admin_b
):
    # Blank code rejected
    blank_code = AssetFacilitySpace(tenant=tenant_a, code="   ", name="No Code")
    with pytest.raises(ValidationError) as exc_info:
        blank_code.full_clean()
    assert "code" in exc_info.value.message_dict

    # Negative areas and rate rejected
    neg_space = AssetFacilitySpace(
        tenant=tenant_a,
        code="NEG-1",
        name="Negative Areas",
        gross_area_sqft=Decimal("-1.00"),
        rentable_area_sqft=Decimal("-2.00"),
        usable_area_sqft=Decimal("-3.00"),
        common_area_sqft=Decimal("-4.00"),
        annual_rate_per_sqft=Decimal("-5.00"),
    )
    with pytest.raises(ValidationError) as neg_exc:
        neg_space.full_clean()
    for fld in (
        "gross_area_sqft",
        "rentable_area_sqft",
        "usable_area_sqft",
        "common_area_sqft",
        "annual_rate_per_sqft",
    ):
        assert fld in neg_exc.value.message_dict

    # Self-parenting rejected
    sfa_space_building_a.parent = sfa_space_building_a
    with pytest.raises(ValidationError) as self_exc:
        sfa_space_building_a.full_clean()
    assert "parent" in self_exc.value.message_dict
    sfa_space_building_a.parent = None

    # Descendant cycle rejected (building -> floor -> room, setting building.parent = room)
    room_a = _spacefacility_create_space(
        tenant_a, code="RM-CYC", name="Cycle Room", parent=sfa_space_floor_a
    )
    sfa_space_building_a.parent = room_a
    with pytest.raises(ValidationError) as cyc_exc:
        sfa_space_building_a.full_clean()
    assert "parent" in cyc_exc.value.message_dict
    sfa_space_building_a.parent = None

    # Cross-tenant FK rejection
    cross = AssetFacilitySpace(
        tenant=tenant_a,
        code="XTEN-1",
        name="Cross Tenant Space",
        parent=sfa_space_b,
        org_unit=org_unit_b,
        scm_location=location_b,
        space_steward=admin_b,
    )
    with pytest.raises(ValidationError) as xten_exc:
        cross.full_clean()
    for fld in ("parent", "org_unit", "scm_location", "space_steward"):
        assert fld in xten_exc.value.message_dict


def test_spacefacility_space_locks_badges_and_floor_plan_upload(tenant_a, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)

    space = _spacefacility_create_space(tenant_a, code="FP-01", name="Floor Plan Space")
    assert space.is_locked is False
    assert space.status_badge_class in _SPACEFACILITY_VALID_BADGE_CLASSES
    assert space.occupancy_badge_class in _SPACEFACILITY_VALID_BADGE_CLASSES
    assert space.level_badge_class in _SPACEFACILITY_VALID_BADGE_CLASSES
    assert str(space).startswith(space.number)

    space.status = "decommissioned"
    assert space.is_locked is True

    # Reject .svg upload via model FieldFile validator
    space.status = "active"
    space.floor_plan_image = SimpleUploadedFile("bad_plan.svg", b"<svg/>", content_type="image/svg+xml")
    with pytest.raises(ValidationError) as svg_exc:
        space.full_clean()
    assert "floor_plan_image" in svg_exc.value.message_dict

    # Accept valid .png upload and preserve original_floor_plan_name across non-upload saves
    space.floor_plan_image = SimpleUploadedFile("level2_map.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")
    space.full_clean()
    space.save()
    assert space.original_floor_plan_name == "level2_map.png"
    stored_name = space.floor_plan_image.name

    # Re-fetch and save without changing upload: original_floor_plan_name must remain preserved
    refetched = AssetFacilitySpace.objects.get(pk=space.pk)
    refetched.name = "Floor Plan Space Updated"
    refetched.full_clean()
    refetched.save()
    assert refetched.floor_plan_image.name == stored_name
    assert refetched.original_floor_plan_name == "level2_map.png"

    # Clearing floor_plan_image clears original_floor_plan_name
    refetched.floor_plan_image = None
    refetched.save()
    assert refetched.original_floor_plan_name == ""


# =====================================================================
# 5. AssetBuildingSystem Invariants
# =====================================================================


def test_spacefacility_building_system_comfort_status_thresholds(tenant_a, sfa_space_floor_a):
    # Optimal within +-1.00 C and +-5.00 %
    hvac = _spacefacility_create_system(
        tenant_a,
        sfa_space_floor_a,
        name="AHU Comfort Test",
        system_domain="hvac_climate",
        setpoint_temp_c=Decimal("22.00"),
        measured_temp_c=Decimal("22.80"),
        target_humidity_pct=Decimal("45.00"),
        measured_humidity_pct=Decimal("49.50"),
    )
    assert hvac.comfort_status == "optimal"

    # Drift warning: 1.00 < |temp| <= 2.50
    hvac.measured_temp_c = Decimal("23.50")
    hvac.save()
    assert hvac.comfort_status == "drift_warning"

    # Out of band: |temp| > 2.50
    hvac.measured_temp_c = Decimal("25.00")
    hvac.save()
    assert hvac.comfort_status == "out_of_band"

    # Humidity drift warning & out_of_band
    hvac.measured_temp_c = Decimal("22.00")
    hvac.measured_humidity_pct = Decimal("52.00")  # diff 7.00 -> drift_warning
    hvac.save()
    assert hvac.comfort_status == "drift_warning"

    hvac.measured_humidity_pct = Decimal("56.00")  # diff 11.00 -> out_of_band
    hvac.save()
    assert hvac.comfort_status == "out_of_band"

    # Offline when status is under_maintenance, standby, or decommissioned
    for off_status in ("under_maintenance", "standby", "decommissioned"):
        hvac.status = off_status
        hvac.save()
        assert hvac.comfort_status == "offline"

    # Missing telemetry or non-HVAC without telemetry -> not_applicable
    no_data = _spacefacility_create_system(
        tenant_a,
        sfa_space_floor_a,
        name="AHU No Telemetry",
        system_domain="hvac_climate",
    )
    assert no_data.comfort_status == "not_applicable"

    non_hvac = _spacefacility_create_system(
        tenant_a,
        sfa_space_floor_a,
        name="Fire Panel",
        system_domain="fire_life_safety",
        subsystem_type="fire_alarm_panel",
    )
    assert non_hvac.comfort_status == "not_applicable"


def test_spacefacility_building_system_infra_inspection_bounds_locks_and_cross_tenant(
    tenant_a,
    sfa_building_system_hvac_a,
    sfa_building_system_infra_a,
    sfa_space_floor_a,
    sfa_space_b,
    operational_asset_b,
    fixed_asset_b,
    vendor_party_b,
    org_unit_b,
):
    today = timezone.localdate()

    # Infrastructure domain grouping
    assert sfa_building_system_hvac_a.system_domain not in AssetBuildingSystem.INFRASTRUCTURE_DOMAINS
    assert sfa_building_system_infra_a.system_domain in AssetBuildingSystem.INFRASTRUCTURE_DOMAINS

    # Inspection overdue checks
    assert sfa_building_system_hvac_a.is_inspection_overdue is False
    sfa_building_system_hvac_a.next_inspection_due_date = today - timedelta(days=1)
    assert sfa_building_system_hvac_a.is_inspection_overdue is True
    sfa_building_system_hvac_a.status = "decommissioned"
    assert sfa_building_system_hvac_a.is_locked is True
    assert sfa_building_system_hvac_a.is_inspection_overdue is False

    # Badge classes
    assert sfa_building_system_hvac_a.status_badge_class in _SPACEFACILITY_VALID_BADGE_CLASSES
    assert sfa_building_system_hvac_a.comfort_badge_class in _SPACEFACILITY_VALID_BADGE_CLASSES
    assert sfa_building_system_hvac_a.condition_badge_class in _SPACEFACILITY_VALID_BADGE_CLASSES
    assert sfa_building_system_hvac_a.criticality_badge_class in _SPACEFACILITY_VALID_BADGE_CLASSES

    # Pin bounds, humidity bounds, negative numbers, inspection date inversion, cross-tenant FKs
    bad_sys = AssetBuildingSystem(
        tenant=tenant_a,
        name="Invalid System",
        facility_space=sfa_space_b,
        operational_asset=operational_asset_b,
        fixed_asset=fixed_asset_b,
        service_vendor=vendor_party_b,
        org_unit=org_unit_b,
        pin_x_pct=Decimal("-1.00"),
        pin_y_pct=Decimal("101.00"),
        target_humidity_pct=Decimal("105.00"),
        measured_humidity_pct=Decimal("-5.00"),
        served_area_sqft=Decimal("-10.00"),
        design_capacity_btu_kw=Decimal("-1.00"),
        airflow_cfm=Decimal("-1.00"),
        replacement_cost_estimate=Decimal("-100.00"),
        last_statutory_inspection_date=today,
        next_inspection_due_date=today - timedelta(days=2),
    )
    with pytest.raises(ValidationError) as exc_info:
        bad_sys.full_clean()
    expected_fields = {
        "facility_space",
        "operational_asset",
        "fixed_asset",
        "service_vendor",
        "org_unit",
        "pin_x_pct",
        "pin_y_pct",
        "target_humidity_pct",
        "measured_humidity_pct",
        "served_area_sqft",
        "design_capacity_btu_kw",
        "airflow_cfm",
        "replacement_cost_estimate",
        "next_inspection_due_date",
    }
    assert expected_fields.issubset(set(exc_info.value.message_dict.keys()))

    # facility_space PROTECT on delete
    with pytest.raises(ProtectedError):
        sfa_space_floor_a.delete()


# =====================================================================
# 6. AssetFurnitureFixture Invariants
# =====================================================================


def test_spacefacility_furniture_cost_quantity_target_space_and_deletes(
    tenant_a,
    sfa_space_building_a,
    sfa_space_floor_a,
    sfa_space_b,
    sfa_furniture_a,
    vendor_party_b,
    org_unit_b,
    operational_asset_b,
    fixed_asset_b,
    movement_a,
    movement_b,
    admin_b,
):
    # total_replacement_value = quantity * unit_replacement_cost
    assert sfa_furniture_a.quantity == 6
    assert sfa_furniture_a.unit_replacement_cost == Decimal("1500.00")
    assert sfa_furniture_a.total_replacement_value == Decimal("9000.00")

    assert sfa_furniture_a.is_locked is False
    assert sfa_furniture_a.move_status_badge_class in _SPACEFACILITY_VALID_BADGE_CLASSES
    assert sfa_furniture_a.condition_badge_class in _SPACEFACILITY_VALID_BADGE_CLASSES

    sfa_furniture_a.move_status = "retired"
    assert sfa_furniture_a.is_locked is True

    # quantity < 1, target_space == facility_space, cross-tenant FKs, pin/cost bounds
    bad_ffe = AssetFurnitureFixture(
        tenant=tenant_a,
        name="Invalid FF&E",
        facility_space=sfa_space_floor_a,
        target_space=sfa_space_floor_a,
        custodian_party=vendor_party_b,
        assigned_org_unit=org_unit_b,
        operational_asset=operational_asset_b,
        fixed_asset=fixed_asset_b,
        movement_log=movement_b,
        move_coordinator=admin_b,
        quantity=0,
        unit_replacement_cost=Decimal("-10.00"),
        estimated_move_cost=Decimal("-5.00"),
        pin_x_pct=Decimal("120.00"),
        pin_y_pct=Decimal("-1.00"),
    )
    with pytest.raises(ValidationError) as exc_info:
        bad_ffe.full_clean()
    for fld in (
        "quantity",
        "target_space",
        "custodian_party",
        "assigned_org_unit",
        "operational_asset",
        "fixed_asset",
        "movement_log",
        "move_coordinator",
        "unit_replacement_cost",
        "estimated_move_cost",
        "pin_x_pct",
        "pin_y_pct",
    ):
        assert fld in exc_info.value.message_dict

    # Cross-tenant target_space rejected while valid same-tenant different space passes
    bad_target = AssetFurnitureFixture(
        tenant=tenant_a,
        name="Cross Target Space",
        facility_space=sfa_space_floor_a,
        target_space=sfa_space_b,
        quantity=1,
    )
    with pytest.raises(ValidationError) as tgt_exc:
        bad_target.full_clean()
    assert "target_space" in tgt_exc.value.message_dict

    good_ffe = _spacefacility_create_furniture(
        tenant_a,
        sfa_space_floor_a,
        name="Movable Pod",
        target_space=sfa_space_building_a,
        movement_log=movement_a,
    )
    good_ffe.full_clean()

    # Deleting movement_log sets movement_log=None (SET_NULL) without deleting good_ffe
    movement_a.delete()
    good_ffe.refresh_from_db()
    assert good_ffe.movement_log is None

    # Deleting facility_space raises ProtectedError
    with pytest.raises(ProtectedError):
        sfa_space_floor_a.delete()


# =====================================================================
# 7. AssetSpaceChargeback Invariants
# =====================================================================


def test_spacefacility_chargeback_net_calculation_and_ti_floor(
    tenant_a, sfa_space_floor_a, sfa_chargeback_draft_a
):
    # draft fixture: base 5000 + cam 1000 + util 500 + (400 - 150) = 6750.00
    assert sfa_chargeback_draft_a.compute_net_chargeback() == Decimal("6750.00")
    assert sfa_chargeback_draft_a.net_chargeback_amount == Decimal("6750.00")

    # TI allowance > TI improvement cost is floored at 0.00 (never reduces base+cam+utility)
    cb_offset = _spacefacility_create_chargeback(
        tenant_a,
        sfa_space_floor_a,
        title="TI Allowance Exceeds TI Cost",
        base_cost_amount=Decimal("2000.00"),
        shared_cam_amount=Decimal("300.00"),
        utility_recovery_amount=Decimal("200.00"),
        ti_improvement_cost=Decimal("500.00"),
        ti_allowance_offset=Decimal("1200.00"),
    )
    assert cb_offset.compute_net_chargeback() == Decimal("2500.00")
    assert cb_offset.net_chargeback_amount == Decimal("2500.00")


def test_spacefacility_chargeback_validation_overflow_protect_and_status_locks(
    tenant_a,
    sfa_space_floor_a,
    sfa_space_b,
    sfa_building_system_b,
    org_unit_b,
    vendor_party_b,
    currency_usd,
    integration_open_fiscal_period_a,
    integration_open_fiscal_period_b,
    expense_account_a,
    expense_account_b,
    accum_account_b,
    sfa_chargeback_draft_a,
    sfa_chargeback_approved_a,
):
    today = timezone.localdate()

    # Status locks & editable statuses
    assert sfa_chargeback_draft_a.can_edit is True
    assert sfa_chargeback_draft_a.is_locked is False
    assert sfa_chargeback_draft_a.status_badge_class in _SPACEFACILITY_VALID_BADGE_CLASSES

    assert sfa_chargeback_approved_a.can_edit is False
    assert sfa_chargeback_approved_a.is_locked is True
    for editable_stat in AssetSpaceChargeback.EDITABLE_STATUSES:
        sfa_chargeback_draft_a.status = editable_stat
        assert sfa_chargeback_draft_a.can_edit is True
        assert sfa_chargeback_draft_a.is_locked is False
    for locked_stat in AssetSpaceChargeback.LOCKED_STATUSES:
        sfa_chargeback_draft_a.status = locked_stat
        assert sfa_chargeback_draft_a.can_edit is False
        assert sfa_chargeback_draft_a.is_locked is True

    # Global currency passes full_clean cleanly without tenant mismatch
    sfa_chargeback_approved_a.full_clean()

    # Overflow guard: raw_total > 99999999999999.99 rejected on base_cost_amount
    overflow_cb = AssetSpaceChargeback(
        tenant=tenant_a,
        title="Overflow Chargeback",
        facility_space=sfa_space_floor_a,
        period_start=today,
        period_end=today,
        base_cost_amount=Decimal("99999999999999.99"),
        shared_cam_amount=Decimal("0.01"),
    )
    with pytest.raises(ValidationError) as ov_exc:
        overflow_cb.full_clean()
    assert "base_cost_amount" in ov_exc.value.message_dict

    # Exact boundary passes
    overflow_cb.shared_cam_amount = Decimal("0.00")
    overflow_cb.full_clean()

    # Date inversions, identical GL accounts, pct & negative checks, cross-tenant FKs
    bad_cb = AssetSpaceChargeback(
        tenant=tenant_a,
        title="Invalid Chargeback",
        facility_space=sfa_space_b,
        shared_building_system=sfa_building_system_b,
        charged_org_unit=org_unit_b,
        occupant_party=vendor_party_b,
        currency=currency_usd,
        fiscal_period=integration_open_fiscal_period_b,
        expense_gl_account=expense_account_a,
        recovery_gl_account=expense_account_a,
        period_start=today,
        period_end=today - timedelta(days=1),
        amortization_end_date=today - timedelta(days=2),
        allocation_share_pct=Decimal("150.00"),
        allocated_area_sqft=Decimal("-1.00"),
        base_cost_amount=Decimal("-1.00"),
        shared_cam_amount=Decimal("-1.00"),
        utility_recovery_amount=Decimal("-1.00"),
        ti_improvement_cost=Decimal("-1.00"),
        ti_allowance_offset=Decimal("-1.00"),
    )
    with pytest.raises(ValidationError) as bad_exc:
        bad_cb.full_clean()
    expected_bad = {
        "facility_space",
        "shared_building_system",
        "charged_org_unit",
        "occupant_party",
        "fiscal_period",
        "recovery_gl_account",
        "period_end",
        "amortization_end_date",
        "allocation_share_pct",
        "allocated_area_sqft",
        "base_cost_amount",
        "shared_cam_amount",
        "utility_recovery_amount",
        "ti_improvement_cost",
        "ti_allowance_offset",
    }
    assert expected_bad.issubset(set(bad_exc.value.message_dict.keys()))
    assert "currency" not in bad_exc.value.message_dict

    # Also verify cross-tenant GL account rejection independently of same-account check
    xten_gl_cb = AssetSpaceChargeback(
        tenant=tenant_a,
        title="Cross Tenant GL",
        facility_space=sfa_space_floor_a,
        expense_gl_account=expense_account_b,
        recovery_gl_account=accum_account_b,
        period_start=today,
        period_end=today,
    )
    with pytest.raises(ValidationError) as gl_exc:
        xten_gl_cb.full_clean()
    assert "expense_gl_account" in gl_exc.value.message_dict
    assert "recovery_gl_account" in gl_exc.value.message_dict

    # on_delete=models.PROTECT on journal_entry
    je = JournalEntry.objects.create(
        tenant=tenant_a,
        fiscal_period=integration_open_fiscal_period_a,
        entry_date=today,
        description="Chargeback GL posting",
    )
    cb_je = _spacefacility_create_chargeback(
        tenant_a,
        sfa_space_floor_a,
        title="Protected JE Chargeback",
        journal_entry=je,
    )
    assert cb_je.journal_entry_id == je.pk
    with pytest.raises(ProtectedError):
        je.delete()
