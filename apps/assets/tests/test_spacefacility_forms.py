"""
Unit tests for Module 11.17: Space & Facility Asset Management Forms & Helpers.
Covers AssetFacilitySpaceForm, AssetBuildingSystemForm, AssetFurnitureFixtureForm,
AssetSpaceChargebackForm, _helpers.py (scope_tenant_querysets, validate_safe_floor_plan_upload),
mass-assignment exclusion invariant, tenant FK queryset isolation & cross-tenant rejection,
document access_classification scoping (I4), query budget (I7), and domain validation.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

import apps.assets.forms as assets_forms
import apps.assets.forms.SpaceFacilityAsset as sfa_forms
from apps.accounting.models import Currency, Invoice
from apps.assets.forms import (
    AssetBuildingSystemForm,
    AssetFacilitySpaceForm,
    AssetFurnitureFixtureForm,
    AssetSpaceChargebackForm,
    reject_foreign,
)
from apps.assets.forms.SpaceFacilityAsset import (
    AssetBuildingSystemForm as DirectAssetBuildingSystemForm,
    AssetFacilitySpaceForm as DirectAssetFacilitySpaceForm,
    AssetFurnitureFixtureForm as DirectAssetFurnitureFixtureForm,
    AssetSpaceChargebackForm as DirectAssetSpaceChargebackForm,
)
from apps.assets.forms.SpaceFacilityAsset._helpers import scope_tenant_querysets
from apps.assets.models import (
    AssetEnergyReading,
    AssetFacilitySpace,
)
from apps.assets.models.SpaceFacilityAsset._validators import MAX_UPLOAD_BYTES

pytestmark = pytest.mark.django_db


# =====================================================================
# Module-level Helpers (Must start with _spacefacility_*)
# =====================================================================


def _spacefacility_base_space_payload(**overrides):
    data = {
        "code": "HQ-F3-R301",
        "name": "Engineering Collaboration Suite 301",
        "space_level": "room",
        "space_category": "office_workspace",
        "gross_area_sqft": "1500.00",
        "rentable_area_sqft": "1350.00",
        "usable_area_sqft": "1200.00",
        "common_area_sqft": "150.00",
        "annual_rate_per_sqft": "45.00",
        "design_seat_capacity": "20",
        "current_headcount": "12",
        "cad_layer_ref": "A-AREA-301",
        "bim_guid": "bim-guid-301",
        "bim_level_ref": "Level 03",
        "drawing_revision": "Rev C",
        "notes": "Suite 301 workspace.",
    }
    data.update(overrides)
    return data


def _spacefacility_base_system_payload(facility_space, **overrides):
    today = timezone.localdate()
    data = {
        "name": "AHU-03 West Wing",
        "system_domain": "hvac_climate",
        "subsystem_type": "ahu_air_handler",
        "facility_space": str(facility_space.pk),
        "pin_x_pct": "35.50",
        "pin_y_pct": "60.25",
        "manufacturer": "Trane",
        "model_number": "CSAA-250",
        "serial_number": "TRN-301-01",
        "load_or_voltage_rating": "480V 3-Phase",
        "ashrae_nfpa_code_ref": "ASHRAE 90.1",
        "served_area_sqft": "5000.00",
        "design_capacity_btu_kw": "250.00",
        "refrigerant_type": "R-410A",
        "setpoint_temp_c": "21.50",
        "measured_temp_c": "21.80",
        "target_humidity_pct": "45.00",
        "measured_humidity_pct": "46.50",
        "airflow_cfm": "8500.00",
        "energy_efficiency_rating": "SEER 18",
        "condition_grade": "good",
        "criticality_tier": "tier_2_mission_crit",
        "remaining_useful_life_years": "14",
        "replacement_cost_estimate": "75000.00",
        "last_statutory_inspection_date": (today - timedelta(days=30)).isoformat(),
        "next_inspection_due_date": (today + timedelta(days=335)).isoformat(),
        "notes": "Quarterly belt check completed.",
    }
    data.update(overrides)
    return data


def _spacefacility_base_furniture_payload(facility_space, **overrides):
    today = timezone.localdate()
    data = {
        "name": "Acoustic Pod Cluster 4B",
        "ffe_category": "workstation_desk",
        "asset_tag_code": "FFE-TAG-402",
        "manufacturer": "Herman Miller",
        "model_sku": "HM-POD-04",
        "finish_material": "Walnut / Graphite",
        "facility_space": str(facility_space.pk),
        "quantity": "4",
        "unit_replacement_cost": "2200.00",
        "pin_x_pct": "40.00",
        "pin_y_pct": "55.00",
        "condition_grade": "good",
        "reconfiguration_batch_ref": "IMAC-2026-Q4",
        "move_scheduled_date": (today + timedelta(days=14)).isoformat(),
        "estimated_move_cost": "450.00",
        "move_notes": "Requires weekend freight elevator booking.",
    }
    data.update(overrides)
    return data


def _spacefacility_base_chargeback_payload(facility_space, **overrides):
    today = timezone.localdate()
    data = {
        "title": "Q4 Engineering Floor Space Chargeback",
        "coordination_type": "space_chargeback",
        "allocation_basis": "usable_sqft",
        "facility_space": str(facility_space.pk),
        "period_start": today.replace(day=1).isoformat(),
        "period_end": today.isoformat(),
        "amortization_end_date": (today + timedelta(days=180)).isoformat(),
        "allocated_area_sqft": "1200.00",
        "allocation_share_pct": "50.00",
        "base_cost_amount": "3200.00",
        "shared_cam_amount": "450.00",
        "utility_recovery_amount": "225.00",
        "ti_improvement_cost": "500.00",
        "ti_allowance_offset": "150.00",
        "notes": "Standard monthly allocation.",
    }
    data.update(overrides)
    return data


# =====================================================================
# 1. Package Re-exports
# =====================================================================


def test_spacefacility_forms_package_reexports():
    expected = [
        "AssetFacilitySpaceForm",
        "AssetBuildingSystemForm",
        "AssetFurnitureFixtureForm",
        "AssetSpaceChargebackForm",
    ]
    assert sfa_forms.__all__ == expected
    assert AssetFacilitySpaceForm is DirectAssetFacilitySpaceForm
    assert AssetBuildingSystemForm is DirectAssetBuildingSystemForm
    assert AssetFurnitureFixtureForm is DirectAssetFurnitureFixtureForm
    assert AssetSpaceChargebackForm is DirectAssetSpaceChargebackForm

    for symbol in expected:
        assert symbol in assets_forms.__all__
        assert getattr(assets_forms, symbol) is getattr(sfa_forms, symbol)


# =====================================================================
# 2. Mass-Assignment Exclusion Invariant
# =====================================================================


def test_spacefacility_mass_assignment_exclusions_invariant(tenant_a, admin_user):
    forbidden_common = {
        "tenant",
        "number",
        "status",
        "comfort_status",
        "occupancy_status",
        "move_status",
        "journal_entry",
        "movement_log",
        "approved_by",
        "approved_at",
        "move_completed_at",
        "net_chargeback_amount",
        "original_floor_plan_name",
        "created_at",
        "updated_at",
    }

    space_form = AssetFacilitySpaceForm(tenant=tenant_a, user=admin_user)
    system_form = AssetBuildingSystemForm(tenant=tenant_a, user=admin_user)
    furniture_form = AssetFurnitureFixtureForm(tenant=tenant_a)
    chargeback_form = AssetSpaceChargebackForm(tenant=tenant_a)

    for form in (space_form, system_form, furniture_form, chargeback_form):
        meta_fields = set(form.Meta.fields)
        form_fields = set(form.fields.keys())
        assert forbidden_common.isdisjoint(meta_fields), (
            f"{type(form).__name__}.Meta.fields leaked forbidden fields: "
            f"{forbidden_common & meta_fields}"
        )
        assert forbidden_common.isdisjoint(form_fields), (
            f"{type(form).__name__}.fields leaked forbidden fields: "
            f"{forbidden_common & form_fields}"
        )


# =====================================================================
# 3. Tenant FK Queryset Isolation & Cross-Tenant Rejection
# =====================================================================


def test_spacefacility_space_form_tenant_isolation_and_rejection(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    sfa_space_building_a,
    sfa_space_b,
    org_unit_a,
    org_unit_b,
    location_a,
    location_b,
    integration_gis_mapping_a,
    integration_gis_mapping_b,
    adk_document_a,
    adk_document_b,
):
    none_form = AssetFacilitySpaceForm(tenant=None, user=None)
    for field_name in AssetFacilitySpaceForm._TENANT_FK_MAP:
        assert none_form.fields[field_name].queryset.count() == 0

    form_a = AssetFacilitySpaceForm(tenant=tenant_a, user=admin_user)
    assert sfa_space_building_a in form_a.fields["parent"].queryset
    assert sfa_space_b not in form_a.fields["parent"].queryset
    assert org_unit_a in form_a.fields["org_unit"].queryset
    assert org_unit_b not in form_a.fields["org_unit"].queryset
    assert location_a in form_a.fields["scm_location"].queryset
    assert location_b not in form_a.fields["scm_location"].queryset
    assert integration_gis_mapping_a in form_a.fields["gis_mapping"].queryset
    assert integration_gis_mapping_b not in form_a.fields["gis_mapping"].queryset
    assert adk_document_a in form_a.fields["floor_plan_document"].queryset
    assert adk_document_b not in form_a.fields["floor_plan_document"].queryset
    assert admin_user in form_a.fields["space_steward"].queryset
    assert admin_b not in form_a.fields["space_steward"].queryset

    form_b = AssetFacilitySpaceForm(tenant=tenant_b, user=admin_b)
    assert sfa_space_b in form_b.fields["parent"].queryset
    assert sfa_space_building_a not in form_b.fields["parent"].queryset

    foreign_cases = [
        ("parent", sfa_space_b.pk),
        ("org_unit", org_unit_b.pk),
        ("scm_location", location_b.pk),
        ("gis_mapping", integration_gis_mapping_b.pk),
        ("floor_plan_document", adk_document_b.pk),
        ("space_steward", admin_b.pk),
    ]
    for field_name, foreign_pk in foreign_cases:
        payload = _spacefacility_base_space_payload(**{field_name: str(foreign_pk)})
        bad_form = AssetFacilitySpaceForm(data=payload, tenant=tenant_a, user=admin_user)
        assert not bad_form.is_valid()
        assert field_name in bad_form.errors


def test_spacefacility_system_form_tenant_isolation_and_rejection(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    sfa_space_floor_a,
    sfa_space_b,
    operational_asset_a,
    operational_asset_b,
    fixed_asset_a,
    fixed_asset_b,
    energy_reading_a,
    energy_reading_b,
    maintenance_schedule_a,
    maintenance_schedule_b,
    permit_license_a,
    permit_license_b,
    adk_document_a,
    adk_document_b,
    vendor_party_a,
    vendor_party_b,
    org_unit_a,
    org_unit_b,
):
    none_form = AssetBuildingSystemForm(tenant=None, user=None)
    for field_name in AssetBuildingSystemForm._TENANT_FK_MAP:
        assert none_form.fields[field_name].queryset.count() == 0

    form_a = AssetBuildingSystemForm(tenant=tenant_a, user=admin_user)
    pairs = [
        ("facility_space", sfa_space_floor_a, sfa_space_b),
        ("operational_asset", operational_asset_a, operational_asset_b),
        ("fixed_asset", fixed_asset_a, fixed_asset_b),
        ("latest_energy_reading", energy_reading_a, energy_reading_b),
        ("maintenance_schedule", maintenance_schedule_a, maintenance_schedule_b),
        ("operating_permit", permit_license_a, permit_license_b),
        ("schematic_document", adk_document_a, adk_document_b),
        ("service_vendor", vendor_party_a, vendor_party_b),
        ("org_unit", org_unit_a, org_unit_b),
    ]
    for field_name, obj_a, obj_b in pairs:
        qs = form_a.fields[field_name].queryset
        assert obj_a in qs
        assert obj_b not in qs

    form_b = AssetBuildingSystemForm(tenant=tenant_b, user=admin_b)
    assert sfa_space_b in form_b.fields["facility_space"].queryset
    assert sfa_space_floor_a not in form_b.fields["facility_space"].queryset

    for field_name, _obj_a, obj_b in pairs:
        space_arg = obj_b if field_name == "facility_space" else sfa_space_floor_a
        overrides = {} if field_name == "facility_space" else {field_name: str(obj_b.pk)}
        payload = _spacefacility_base_system_payload(space_arg, **overrides)
        bad_form = AssetBuildingSystemForm(data=payload, tenant=tenant_a, user=admin_user)
        assert not bad_form.is_valid()
        assert field_name in bad_form.errors


def test_spacefacility_furniture_form_tenant_isolation_and_rejection(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    sfa_space_building_a,
    sfa_space_floor_a,
    sfa_space_b,
    vendor_party_a,
    vendor_party_b,
    org_unit_a,
    org_unit_b,
    operational_asset_a,
    operational_asset_b,
    fixed_asset_a,
    fixed_asset_b,
):
    none_form = AssetFurnitureFixtureForm(tenant=None)
    for field_name in AssetFurnitureFixtureForm._TENANT_FK_MAP:
        assert none_form.fields[field_name].queryset.count() == 0

    form_a = AssetFurnitureFixtureForm(tenant=tenant_a)
    pairs = [
        ("facility_space", sfa_space_floor_a, sfa_space_b),
        ("target_space", sfa_space_building_a, sfa_space_b),
        ("custodian_party", vendor_party_a, vendor_party_b),
        ("assigned_org_unit", org_unit_a, org_unit_b),
        ("operational_asset", operational_asset_a, operational_asset_b),
        ("fixed_asset", fixed_asset_a, fixed_asset_b),
        ("move_coordinator", admin_user, admin_b),
    ]
    for field_name, obj_a, obj_b in pairs:
        qs = form_a.fields[field_name].queryset
        assert obj_a in qs
        assert obj_b not in qs

    form_b = AssetFurnitureFixtureForm(tenant=tenant_b)
    assert sfa_space_b in form_b.fields["facility_space"].queryset
    assert sfa_space_floor_a not in form_b.fields["facility_space"].queryset

    for field_name, _obj_a, obj_b in pairs:
        space_arg = obj_b if field_name == "facility_space" else sfa_space_floor_a
        overrides = {} if field_name == "facility_space" else {field_name: str(obj_b.pk)}
        payload = _spacefacility_base_furniture_payload(space_arg, **overrides)
        bad_form = AssetFurnitureFixtureForm(data=payload, tenant=tenant_a)
        assert not bad_form.is_valid()
        assert field_name in bad_form.errors


def test_spacefacility_chargeback_form_tenant_isolation_and_global_currency(
    tenant_a,
    tenant_b,
    sfa_space_floor_a,
    sfa_space_b,
    sfa_building_system_hvac_a,
    sfa_building_system_b,
    lease_contract_a,
    lease_contract_b,
    fixed_asset_a,
    fixed_asset_b,
    org_unit_a,
    org_unit_b,
    vendor_party_a,
    vendor_party_b,
    currency_usd,
    integration_open_fiscal_period_a,
    integration_open_fiscal_period_b,
    expense_account_a,
    accum_account_a,
    expense_account_b,
    accum_account_b,
):
    inactive_currency = Currency.objects.create(
        code="XIN",
        name="Inactive Test Currency",
        symbol="X",
        is_active=False,
    )
    today = timezone.localdate()
    invoice_a = Invoice.objects.create(
        tenant=tenant_a,
        kind="invoice",
        party=vendor_party_a,
        issue_date=today,
        due_date=today + timedelta(days=30),
        currency=currency_usd,
    )
    invoice_b = Invoice.objects.create(
        tenant=tenant_b,
        kind="invoice",
        party=vendor_party_b,
        issue_date=today,
        due_date=today + timedelta(days=30),
        currency=currency_usd,
    )

    none_form = AssetSpaceChargebackForm(tenant=None)
    for field_name in AssetSpaceChargebackForm._TENANT_FK_MAP:
        assert none_form.fields[field_name].queryset.count() == 0
    assert currency_usd in none_form.fields["currency"].queryset
    assert inactive_currency not in none_form.fields["currency"].queryset

    form_a = AssetSpaceChargebackForm(tenant=tenant_a)
    pairs = [
        ("facility_space", sfa_space_floor_a, sfa_space_b),
        ("shared_building_system", sfa_building_system_hvac_a, sfa_building_system_b),
        ("lease_contract", lease_contract_a, lease_contract_b),
        ("fixed_asset", fixed_asset_a, fixed_asset_b),
        ("charged_org_unit", org_unit_a, org_unit_b),
        ("occupant_party", vendor_party_a, vendor_party_b),
        ("fiscal_period", integration_open_fiscal_period_a, integration_open_fiscal_period_b),
        ("expense_gl_account", expense_account_a, expense_account_b),
        ("recovery_gl_account", accum_account_a, accum_account_b),
        ("ar_invoice", invoice_a, invoice_b),
    ]
    for field_name, obj_a, obj_b in pairs:
        qs = form_a.fields[field_name].queryset
        assert obj_a in qs
        assert obj_b not in qs

    assert currency_usd in form_a.fields["currency"].queryset
    assert inactive_currency not in form_a.fields["currency"].queryset

    form_b = AssetSpaceChargebackForm(tenant=tenant_b)
    assert sfa_space_b in form_b.fields["facility_space"].queryset
    assert sfa_space_floor_a not in form_b.fields["facility_space"].queryset
    assert currency_usd in form_b.fields["currency"].queryset

    for field_name, _obj_a, obj_b in pairs:
        space_arg = obj_b if field_name == "facility_space" else sfa_space_floor_a
        overrides = {} if field_name == "facility_space" else {field_name: str(obj_b.pk)}
        payload = _spacefacility_base_chargeback_payload(
            space_arg,
            currency=str(currency_usd.pk),
            **overrides,
        )
        bad_form = AssetSpaceChargebackForm(data=payload, tenant=tenant_a)
        assert not bad_form.is_valid()
        assert field_name in bad_form.errors

    valid_payload = _spacefacility_base_chargeback_payload(
        sfa_space_floor_a,
        currency=str(currency_usd.pk),
        fiscal_period=str(integration_open_fiscal_period_a.pk),
        expense_gl_account=str(expense_account_a.pk),
        recovery_gl_account=str(accum_account_a.pk),
    )
    ok_form = AssetSpaceChargebackForm(data=valid_payload, tenant=tenant_a)
    assert ok_form.is_valid(), ok_form.errors


def test_spacefacility_scope_helper_and_reject_foreign(
    tenant_a,
    sfa_space_building_a,
    sfa_space_b,
):
    form = AssetFacilitySpaceForm(
        data=_spacefacility_base_space_payload(code="HQ-F3-RF1"),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    scope_tenant_querysets(form, {"parent": AssetFacilitySpace, "nonexistent": AssetFacilitySpace})
    assert "nonexistent" not in form.fields

    cleaned = {"parent": sfa_space_b}
    reject_foreign(form, cleaned, ["parent"])
    assert "parent" in form.errors


# =====================================================================
# 4. Document access_classification Scoping (I4)
# =====================================================================


def test_spacefacility_document_access_classification_scoping(
    tenant_a,
    admin_user,
    member_user,
    sfa_space_floor_a,
    adk_document_a,
    adk_document_restricted_a,
):
    # Member user: restricted document excluded & rejected on both Space & BuildingSystem forms
    space_member_form = AssetFacilitySpaceForm(tenant=tenant_a, user=member_user)
    space_doc_qs = space_member_form.fields["floor_plan_document"].queryset
    assert adk_document_a in space_doc_qs
    assert adk_document_restricted_a not in space_doc_qs

    bad_space_form = AssetFacilitySpaceForm(
        data=_spacefacility_base_space_payload(
            code="HQ-F3-SEC1",
            floor_plan_document=str(adk_document_restricted_a.pk),
        ),
        tenant=tenant_a,
        user=member_user,
    )
    assert not bad_space_form.is_valid()
    assert "floor_plan_document" in bad_space_form.errors

    sys_member_form = AssetBuildingSystemForm(tenant=tenant_a, user=member_user)
    sys_doc_qs = sys_member_form.fields["schematic_document"].queryset
    assert adk_document_a in sys_doc_qs
    assert adk_document_restricted_a not in sys_doc_qs

    bad_sys_form = AssetBuildingSystemForm(
        data=_spacefacility_base_system_payload(
            sfa_space_floor_a,
            schematic_document=str(adk_document_restricted_a.pk),
        ),
        tenant=tenant_a,
        user=member_user,
    )
    assert not bad_sys_form.is_valid()
    assert "schematic_document" in bad_sys_form.errors

    # Admin user: restricted document included & accepted on both forms
    space_admin_form = AssetFacilitySpaceForm(tenant=tenant_a, user=admin_user)
    assert adk_document_restricted_a in space_admin_form.fields["floor_plan_document"].queryset

    ok_space_form = AssetFacilitySpaceForm(
        data=_spacefacility_base_space_payload(
            code="HQ-F3-SEC2",
            floor_plan_document=str(adk_document_restricted_a.pk),
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert ok_space_form.is_valid(), ok_space_form.errors

    sys_admin_form = AssetBuildingSystemForm(tenant=tenant_a, user=admin_user)
    assert adk_document_restricted_a in sys_admin_form.fields["schematic_document"].queryset

    ok_sys_form = AssetBuildingSystemForm(
        data=_spacefacility_base_system_payload(
            sfa_space_floor_a,
            schematic_document=str(adk_document_restricted_a.pk),
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert ok_sys_form.is_valid(), ok_sys_form.errors


# =====================================================================
# 5. Query Budget (I7)
# =====================================================================


def test_spacefacility_building_system_form_query_budget(
    django_assert_max_num_queries,
    tenant_a,
    admin_user,
    fixed_asset_a,
    operational_asset_a,
    vendor_party_a,
    energy_reading_a,
):
    now = timezone.now()
    for idx in range(12):
        AssetEnergyReading.objects.create(
            tenant=tenant_a,
            fixed_asset=fixed_asset_a,
            operational_asset=operational_asset_a,
            utility_provider=vendor_party_a,
            recorded_by=admin_user,
            reading_timestamp=now - timedelta(hours=idx + 1),
            utility_type="electricity",
            consumption_value=Decimal("100.0000") + Decimal(idx),
            unit_of_measure="kWh",
            status="pending",
        )

    with django_assert_max_num_queries(10):
        form = AssetBuildingSystemForm(tenant=tenant_a, user=admin_user)
        rendered = str(form["latest_energy_reading"])

    assert energy_reading_a.number in rendered
    assert fixed_asset_a.name in rendered


# =====================================================================
# 6. Domain Validation & Negative Inputs
# =====================================================================


def test_spacefacility_space_form_parent_exclusion_cycle_and_uniqueness(
    tenant_a,
    tenant_b,
    admin_user,
    sfa_space_building_a,
    sfa_space_floor_a,
):
    # Edit instance excluded from parent queryset
    edit_building_form = AssetFacilitySpaceForm(
        instance=sfa_space_building_a,
        tenant=tenant_a,
        user=admin_user,
    )
    parent_qs = edit_building_form.fields["parent"].queryset
    assert sfa_space_building_a not in parent_qs
    assert sfa_space_floor_a in parent_qs

    # Self-parenting rejected
    self_form = AssetFacilitySpaceForm(
        data=_spacefacility_base_space_payload(
            code=sfa_space_building_a.code,
            name=sfa_space_building_a.name,
            parent=str(sfa_space_building_a.pk),
        ),
        instance=sfa_space_building_a,
        tenant=tenant_a,
        user=admin_user,
    )
    assert not self_form.is_valid()
    assert "parent" in self_form.errors

    # Descendant cycle rejected (sfa_space_floor_a.parent == sfa_space_building_a)
    cycle_form = AssetFacilitySpaceForm(
        data=_spacefacility_base_space_payload(
            code=sfa_space_building_a.code,
            name=sfa_space_building_a.name,
            parent=str(sfa_space_floor_a.pk),
        ),
        instance=sfa_space_building_a,
        tenant=tenant_a,
        user=admin_user,
    )
    assert not cycle_form.is_valid()
    assert "parent" in cycle_form.errors

    # Duplicate code within same tenant rejected; same code in other tenant allowed
    dup_form = AssetFacilitySpaceForm(
        data=_spacefacility_base_space_payload(code=sfa_space_floor_a.code.lower()),
        tenant=tenant_a,
        user=admin_user,
    )
    assert not dup_form.is_valid()
    assert "__all__" in dup_form.errors
    assert "already exists" in " ".join(dup_form.errors["__all__"]).lower()

    other_tenant_form = AssetFacilitySpaceForm(
        data=_spacefacility_base_space_payload(code=sfa_space_floor_a.code),
        tenant=tenant_b,
    )
    assert other_tenant_form.is_valid(), other_tenant_form.errors


def test_spacefacility_space_form_uploads_areas_code_and_special_decimals(
    tenant_a,
    admin_user,
):
    # .svg upload rejected
    svg_file = SimpleUploadedFile("floor.svg", b"<svg></svg>", content_type="image/svg+xml")
    svg_form = AssetFacilitySpaceForm(
        data=_spacefacility_base_space_payload(code="HQ-F4-SVG"),
        files={"floor_plan_image": svg_file},
        tenant=tenant_a,
        user=admin_user,
    )
    assert not svg_form.is_valid()
    assert "floor_plan_image" in svg_form.errors

    # Oversized upload rejected
    big_file = SimpleUploadedFile("floor.pdf", b"%PDF-1.4", content_type="application/pdf")
    big_file.size = MAX_UPLOAD_BYTES + 1
    big_form = AssetFacilitySpaceForm(
        data=_spacefacility_base_space_payload(code="HQ-F4-BIG"),
        files={"floor_plan_image": big_file},
        tenant=tenant_a,
        user=admin_user,
    )
    assert not big_form.is_valid()
    assert "floor_plan_image" in big_form.errors

    # Valid PNG upload accepted & code trimmed/uppercased
    png_file = SimpleUploadedFile("floor.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")
    ok_form = AssetFacilitySpaceForm(
        data=_spacefacility_base_space_payload(code="  hq-f4-ok  "),
        files={"floor_plan_image": png_file},
        tenant=tenant_a,
        user=admin_user,
    )
    assert ok_form.is_valid(), ok_form.errors
    assert ok_form.cleaned_data["code"] == "HQ-F4-OK"

    # Whitespace-only code rejected
    blank_code_form = AssetFacilitySpaceForm(
        data=_spacefacility_base_space_payload(code="   "),
        tenant=tenant_a,
        user=admin_user,
    )
    assert not blank_code_form.is_valid()
    assert "code" in blank_code_form.errors

    # Negative area/rate fields rejected
    for neg_field in (
        "gross_area_sqft",
        "rentable_area_sqft",
        "usable_area_sqft",
        "common_area_sqft",
        "annual_rate_per_sqft",
    ):
        neg_form = AssetFacilitySpaceForm(
            data=_spacefacility_base_space_payload(
                code=f"HQ-NEG-{neg_field[:6]}",
                **{neg_field: "-1.00"},
            ),
            tenant=tenant_a,
            user=admin_user,
        )
        assert not neg_form.is_valid()
        assert neg_field in neg_form.errors

    # NaN and Infinity decimals rejected cleanly
    for bad_val in ("NaN", "Infinity", "-Infinity"):
        nan_form = AssetFacilitySpaceForm(
            data=_spacefacility_base_space_payload(
                code="HQ-F4-DEC",
                gross_area_sqft=bad_val,
                annual_rate_per_sqft=bad_val,
            ),
            tenant=tenant_a,
            user=admin_user,
        )
        assert not nan_form.is_valid()
        assert "gross_area_sqft" in nan_form.errors
        assert "annual_rate_per_sqft" in nan_form.errors


def test_spacefacility_building_system_form_validation_bounds_and_negatives(
    tenant_a,
    admin_user,
    sfa_space_floor_a,
):
    ok_form = AssetBuildingSystemForm(
        data=_spacefacility_base_system_payload(sfa_space_floor_a),
        tenant=tenant_a,
        user=admin_user,
    )
    assert ok_form.is_valid(), ok_form.errors

    # Percentage bounds (< 0 and > 100)
    for pct_field in ("pin_x_pct", "pin_y_pct", "target_humidity_pct", "measured_humidity_pct"):
        for bad_pct in ("-0.01", "100.01"):
            bad_form = AssetBuildingSystemForm(
                data=_spacefacility_base_system_payload(
                    sfa_space_floor_a,
                    **{pct_field: bad_pct},
                ),
                tenant=tenant_a,
                user=admin_user,
            )
            assert not bad_form.is_valid()
            assert pct_field in bad_form.errors

    # Inspection date inversion rejected
    today = timezone.localdate()
    date_form = AssetBuildingSystemForm(
        data=_spacefacility_base_system_payload(
            sfa_space_floor_a,
            last_statutory_inspection_date=today.isoformat(),
            next_inspection_due_date=(today - timedelta(days=1)).isoformat(),
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert not date_form.is_valid()
    assert "next_inspection_due_date" in date_form.errors

    # Negative numeric fields rejected
    for neg_field in (
        "served_area_sqft",
        "design_capacity_btu_kw",
        "airflow_cfm",
        "replacement_cost_estimate",
        "remaining_useful_life_years",
    ):
        neg_val = "-1" if neg_field == "remaining_useful_life_years" else "-5.00"
        neg_form = AssetBuildingSystemForm(
            data=_spacefacility_base_system_payload(
                sfa_space_floor_a,
                **{neg_field: neg_val},
            ),
            tenant=tenant_a,
            user=admin_user,
        )
        assert not neg_form.is_valid()
        assert neg_field in neg_form.errors

    # NaN / Infinity rejected cleanly
    for special in ("NaN", "Infinity"):
        special_form = AssetBuildingSystemForm(
            data=_spacefacility_base_system_payload(
                sfa_space_floor_a,
                served_area_sqft=special,
                pin_x_pct=special,
            ),
            tenant=tenant_a,
            user=admin_user,
        )
        assert not special_form.is_valid()
        assert "served_area_sqft" in special_form.errors
        assert "pin_x_pct" in special_form.errors


def test_spacefacility_furniture_form_validation_and_negatives(
    tenant_a,
    sfa_space_building_a,
    sfa_space_floor_a,
):
    ok_form = AssetFurnitureFixtureForm(
        data=_spacefacility_base_furniture_payload(
            sfa_space_floor_a,
            target_space=str(sfa_space_building_a.pk),
        ),
        tenant=tenant_a,
    )
    assert ok_form.is_valid(), ok_form.errors

    # target_space == facility_space rejected
    same_space_form = AssetFurnitureFixtureForm(
        data=_spacefacility_base_furniture_payload(
            sfa_space_floor_a,
            target_space=str(sfa_space_floor_a.pk),
        ),
        tenant=tenant_a,
    )
    assert not same_space_form.is_valid()
    assert "target_space" in same_space_form.errors

    # quantity < 1 rejected
    for bad_qty in ("0", "-3"):
        qty_form = AssetFurnitureFixtureForm(
            data=_spacefacility_base_furniture_payload(sfa_space_floor_a, quantity=bad_qty),
            tenant=tenant_a,
        )
        assert not qty_form.is_valid()
        assert "quantity" in qty_form.errors

    # Negative costs rejected
    for cost_field in ("unit_replacement_cost", "estimated_move_cost"):
        neg_cost_form = AssetFurnitureFixtureForm(
            data=_spacefacility_base_furniture_payload(
                sfa_space_floor_a,
                **{cost_field: "-10.00"},
            ),
            tenant=tenant_a,
        )
        assert not neg_cost_form.is_valid()
        assert cost_field in neg_cost_form.errors

    # Pin bounds & NaN/Infinity rejected
    for pct_field in ("pin_x_pct", "pin_y_pct"):
        bad_pct_form = AssetFurnitureFixtureForm(
            data=_spacefacility_base_furniture_payload(
                sfa_space_floor_a,
                **{pct_field: "101.00"},
            ),
            tenant=tenant_a,
        )
        assert not bad_pct_form.is_valid()
        assert pct_field in bad_pct_form.errors

    nan_form = AssetFurnitureFixtureForm(
        data=_spacefacility_base_furniture_payload(
            sfa_space_floor_a,
            unit_replacement_cost="NaN",
            estimated_move_cost="Infinity",
        ),
        tenant=tenant_a,
    )
    assert not nan_form.is_valid()
    assert "unit_replacement_cost" in nan_form.errors
    assert "estimated_move_cost" in nan_form.errors


def test_spacefacility_chargeback_form_validation_overflow_and_required(
    tenant_a,
    sfa_space_floor_a,
    expense_account_a,
):
    today = timezone.localdate()

    # Empty required fields rejected
    empty_form = AssetSpaceChargebackForm(data={}, tenant=tenant_a)
    assert not empty_form.is_valid()
    for required_field in ("title", "facility_space", "period_start", "period_end"):
        assert required_field in empty_form.errors

    # period_end < period_start rejected
    bad_period_form = AssetSpaceChargebackForm(
        data=_spacefacility_base_chargeback_payload(
            sfa_space_floor_a,
            period_start=today.isoformat(),
            period_end=(today - timedelta(days=1)).isoformat(),
        ),
        tenant=tenant_a,
    )
    assert not bad_period_form.is_valid()
    assert "period_end" in bad_period_form.errors

    # amortization_end_date < period_start rejected
    bad_amort_form = AssetSpaceChargebackForm(
        data=_spacefacility_base_chargeback_payload(
            sfa_space_floor_a,
            period_start=today.isoformat(),
            period_end=today.isoformat(),
            amortization_end_date=(today - timedelta(days=2)).isoformat(),
        ),
        tenant=tenant_a,
    )
    assert not bad_amort_form.is_valid()
    assert "amortization_end_date" in bad_amort_form.errors

    # expense_gl_account == recovery_gl_account rejected
    same_gl_form = AssetSpaceChargebackForm(
        data=_spacefacility_base_chargeback_payload(
            sfa_space_floor_a,
            expense_gl_account=str(expense_account_a.pk),
            recovery_gl_account=str(expense_account_a.pk),
        ),
        tenant=tenant_a,
    )
    assert not same_gl_form.is_valid()
    assert "recovery_gl_account" in same_gl_form.errors

    # Combined 16-digit base_cost_amount overflow (> 99999999999999.99) rejected on base_cost_amount
    overflow_form = AssetSpaceChargebackForm(
        data=_spacefacility_base_chargeback_payload(
            sfa_space_floor_a,
            base_cost_amount="99999999999999.00",
            shared_cam_amount="10.00",
            utility_recovery_amount="0.00",
            ti_improvement_cost="0.00",
            ti_allowance_offset="0.00",
        ),
        tenant=tenant_a,
    )
    assert not overflow_form.is_valid()
    assert "base_cost_amount" in overflow_form.errors

    # Allocation share % bounds & negative amounts rejected
    bad_share_form = AssetSpaceChargebackForm(
        data=_spacefacility_base_chargeback_payload(
            sfa_space_floor_a,
            allocation_share_pct="105.00",
        ),
        tenant=tenant_a,
    )
    assert not bad_share_form.is_valid()
    assert "allocation_share_pct" in bad_share_form.errors

    for neg_field in (
        "allocated_area_sqft",
        "base_cost_amount",
        "shared_cam_amount",
        "utility_recovery_amount",
        "ti_improvement_cost",
        "ti_allowance_offset",
    ):
        neg_form = AssetSpaceChargebackForm(
            data=_spacefacility_base_chargeback_payload(
                sfa_space_floor_a,
                **{neg_field: "-1.00"},
            ),
            tenant=tenant_a,
        )
        assert not neg_form.is_valid()
        assert neg_field in neg_form.errors

    # NaN / Infinity rejected cleanly
    nan_form = AssetSpaceChargebackForm(
        data=_spacefacility_base_chargeback_payload(
            sfa_space_floor_a,
            base_cost_amount="NaN",
            shared_cam_amount="Infinity",
        ),
        tenant=tenant_a,
    )
    assert not nan_form.is_valid()
    assert "base_cost_amount" in nan_form.errors
    assert "shared_cam_amount" in nan_form.errors
