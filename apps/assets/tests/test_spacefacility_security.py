"""
Security, multi-tenant IDOR, RBAC, HTTP method enforcement, AssetDocument ACL (I4),
upload/download hardening, CSV formula neutralization, XSS escaping, mass-assignment,
and lock/protect integrity tests for Module 11.17: Space & Facility Asset Management.
"""

import csv
import io
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import ProtectedError
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import JournalEntry
from apps.assets.models import (
    AssetBuildingSystem,
    AssetFacilitySpace,
    AssetFurnitureFixture,
    AssetSpaceChargeback,
)

pytestmark = pytest.mark.django_db

_SPACEFACILITY_SAMPLE_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc`\x00\x00"
    b"\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
)


# =====================================================================
# Module-level Helpers (Must start with _spacefacility_*)
# =====================================================================


def _spacefacility_space_payload(**overrides):
    data = {
        "code": "SFA-SEC-101",
        "name": "Security Test Suite 101",
        "space_level": "room",
        "space_category": "office_workspace",
        "gross_area_sqft": "1600.00",
        "rentable_area_sqft": "1440.00",
        "usable_area_sqft": "1280.00",
        "common_area_sqft": "160.00",
        "annual_rate_per_sqft": "42.00",
        "design_seat_capacity": "16",
        "current_headcount": "10",
        "cad_layer_ref": "A-SEC-101",
        "bim_guid": "guid-sec-101",
        "bim_level_ref": "Level 01",
        "drawing_revision": "Rev A",
        "notes": "Security test space.",
    }
    data.update(overrides)
    return data


def _spacefacility_system_payload(facility_space, **overrides):
    today = timezone.localdate()
    data = {
        "name": "Security Test AHU-01",
        "system_domain": "hvac_climate",
        "subsystem_type": "ahu_air_handler",
        "facility_space": str(facility_space.pk),
        "pin_x_pct": "20.00",
        "pin_y_pct": "30.00",
        "manufacturer": "Trane",
        "model_number": "SEC-100",
        "serial_number": "SN-SEC-AHU-01",
        "load_or_voltage_rating": "480V 3-Phase",
        "ashrae_nfpa_code_ref": "ASHRAE 90.1",
        "served_area_sqft": "5000.00",
        "design_capacity_btu_kw": "220.00",
        "refrigerant_type": "R-410A",
        "setpoint_temp_c": "22.00",
        "measured_temp_c": "22.20",
        "target_humidity_pct": "45.00",
        "measured_humidity_pct": "45.50",
        "airflow_cfm": "8000.00",
        "energy_efficiency_rating": "SEER 17",
        "condition_grade": "good",
        "criticality_tier": "tier_2_mission_crit",
        "remaining_useful_life_years": "12",
        "replacement_cost_estimate": "65000.00",
        "last_statutory_inspection_date": (today - timedelta(days=20)).isoformat(),
        "next_inspection_due_date": (today + timedelta(days=345)).isoformat(),
        "notes": "Security test building system.",
    }
    data.update(overrides)
    return data


def _spacefacility_furniture_payload(facility_space, **overrides):
    today = timezone.localdate()
    data = {
        "name": "Security Test Workstation Cluster",
        "ffe_category": "workstation_desk",
        "asset_tag_code": "SFA-SEC-FFE-01",
        "manufacturer": "Steelcase",
        "model_sku": "SC-SEC-01",
        "finish_material": "Maple",
        "facility_space": str(facility_space.pk),
        "quantity": "4",
        "unit_replacement_cost": "1400.00",
        "pin_x_pct": "35.00",
        "pin_y_pct": "45.00",
        "condition_grade": "good",
        "reconfiguration_batch_ref": "IMAC-SEC-01",
        "move_scheduled_date": (today + timedelta(days=10)).isoformat(),
        "estimated_move_cost": "300.00",
        "move_notes": "Security test FF&E item.",
    }
    data.update(overrides)
    return data


def _spacefacility_chargeback_payload(facility_space, **overrides):
    today = timezone.localdate()
    data = {
        "title": "Security Test Space Chargeback",
        "coordination_type": "space_chargeback",
        "allocation_basis": "usable_sqft",
        "facility_space": str(facility_space.pk),
        "period_start": today.replace(day=1).isoformat(),
        "period_end": today.isoformat(),
        "amortization_end_date": (today + timedelta(days=90)).isoformat(),
        "allocated_area_sqft": "1280.00",
        "allocation_share_pct": "50.00",
        "base_cost_amount": "2400.00",
        "shared_cam_amount": "350.00",
        "utility_recovery_amount": "150.00",
        "ti_improvement_cost": "300.00",
        "ti_allowance_offset": "100.00",
        "notes": "Security test chargeback.",
    }
    data.update(overrides)
    return data


def _spacefacility_parse_csv(response):
    content = response.content.decode("utf-8")
    return list(csv.reader(io.StringIO(content)))


# =====================================================================
# 1. Cross-Tenant IDOR & Data Isolation
# =====================================================================


def test_spacefacility_idor_all_pk_endpoints_return_404_and_preserve_tenant_b_state(
    tmp_path,
    settings,
    client_a,
    client_b,
    sfa_space_building_a,
    sfa_space_b,
    sfa_building_system_hvac_a,
    sfa_building_system_b,
    sfa_furniture_a,
    sfa_furniture_b,
    sfa_chargeback_draft_a,
    sfa_chargeback_b,
):
    settings.MEDIA_ROOT = str(tmp_path)

    # Give tenant_b space a real uploaded floor plan so download IDOR is tested with an existing file.
    sfa_space_b.floor_plan_image = SimpleUploadedFile(
        "globex_floor_plan.png",
        _SPACEFACILITY_SAMPLE_PNG,
        content_type="image/png",
    )
    sfa_space_b.save()

    space_b_name = sfa_space_b.name
    space_b_status = sfa_space_b.status
    sys_b_name = sfa_building_system_b.name
    sys_b_status = sfa_building_system_b.status
    ffe_b_name = sfa_furniture_b.name
    ffe_b_status = sfa_furniture_b.move_status
    cb_b_title = sfa_chargeback_b.title
    cb_b_status = sfa_chargeback_b.status

    # --- AssetFacilitySpace pk-scoped GET + POST ---
    for url_name in (
        "assets:asset_facility_space_detail",
        "assets:asset_facility_space_edit",
        "assets:asset_facility_space_floor_plan_download",
    ):
        resp = client_a.get(reverse(url_name, args=[sfa_space_b.pk]))
        assert resp.status_code == 404, url_name

    for url_name, data in (
        (
            "assets:asset_facility_space_edit",
            _spacefacility_space_payload(code=sfa_space_b.code, name="IDOR Overwrite"),
        ),
        ("assets:asset_facility_space_delete", {}),
        ("assets:asset_facility_space_recalculate_utilization", {}),
        ("assets:asset_facility_space_mark_under_renovation", {}),
        ("assets:asset_facility_space_activate", {}),
        ("assets:asset_facility_space_decommission", {}),
    ):
        resp = client_a.post(reverse(url_name, args=[sfa_space_b.pk]), data=data)
        assert resp.status_code == 404, url_name

    # --- AssetBuildingSystem pk-scoped GET + POST ---
    for url_name in (
        "assets:asset_building_system_detail",
        "assets:asset_building_system_edit",
    ):
        resp = client_a.get(reverse(url_name, args=[sfa_building_system_b.pk]))
        assert resp.status_code == 404, url_name

    for url_name, data in (
        (
            "assets:asset_building_system_edit",
            _spacefacility_system_payload(sfa_space_building_a, name="IDOR System"),
        ),
        ("assets:asset_building_system_delete", {}),
        ("assets:asset_building_system_evaluate_comfort", {}),
        ("assets:asset_building_system_record_inspection", {}),
        ("assets:asset_building_system_flag_maintenance", {}),
        ("assets:asset_building_system_restore_operational", {}),
        ("assets:asset_building_system_decommission", {}),
    ):
        resp = client_a.post(reverse(url_name, args=[sfa_building_system_b.pk]), data=data)
        assert resp.status_code == 404, url_name

    # --- AssetFurnitureFixture pk-scoped GET + POST ---
    for url_name in (
        "assets:asset_furniture_fixture_detail",
        "assets:asset_furniture_fixture_edit",
    ):
        resp = client_a.get(reverse(url_name, args=[sfa_furniture_b.pk]))
        assert resp.status_code == 404, url_name

    for url_name, data in (
        (
            "assets:asset_furniture_fixture_edit",
            _spacefacility_furniture_payload(sfa_space_building_a, name="IDOR FFE"),
        ),
        ("assets:asset_furniture_fixture_delete", {}),
        ("assets:asset_furniture_fixture_request_move", {}),
        ("assets:asset_furniture_fixture_schedule_reconfig", {}),
        ("assets:asset_furniture_fixture_complete_move", {}),
        ("assets:asset_furniture_fixture_retire", {}),
    ):
        resp = client_a.post(reverse(url_name, args=[sfa_furniture_b.pk]), data=data)
        assert resp.status_code == 404, url_name

    # --- AssetSpaceChargeback pk-scoped GET + POST ---
    for url_name in (
        "assets:asset_space_chargeback_detail",
        "assets:asset_space_chargeback_edit",
    ):
        resp = client_a.get(reverse(url_name, args=[sfa_chargeback_b.pk]))
        assert resp.status_code == 404, url_name

    for url_name, data in (
        (
            "assets:asset_space_chargeback_edit",
            _spacefacility_chargeback_payload(sfa_space_building_a, title="IDOR CB"),
        ),
        ("assets:asset_space_chargeback_delete", {}),
        ("assets:asset_space_chargeback_submit_approval", {}),
        ("assets:asset_space_chargeback_approve", {}),
        ("assets:asset_space_chargeback_post_gl", {}),
        ("assets:asset_space_chargeback_dispute", {}),
        ("assets:asset_space_chargeback_close", {}),
    ):
        resp = client_a.post(reverse(url_name, args=[sfa_chargeback_b.pk]), data=data)
        assert resp.status_code == 404, url_name

    # Symmetric reverse check: client_b cannot access tenant_a records
    for url_name, pk in (
        ("assets:asset_facility_space_detail", sfa_space_building_a.pk),
        ("assets:asset_building_system_detail", sfa_building_system_hvac_a.pk),
        ("assets:asset_furniture_fixture_detail", sfa_furniture_a.pk),
        ("assets:asset_space_chargeback_detail", sfa_chargeback_draft_a.pk),
    ):
        assert client_b.get(reverse(url_name, args=[pk])).status_code == 404

    # Verify zero tenant_b state mutated
    sfa_space_b.refresh_from_db()
    sfa_building_system_b.refresh_from_db()
    sfa_furniture_b.refresh_from_db()
    sfa_chargeback_b.refresh_from_db()
    assert sfa_space_b.name == space_b_name
    assert sfa_space_b.status == space_b_status
    assert sfa_building_system_b.name == sys_b_name
    assert sfa_building_system_b.status == sys_b_status
    assert sfa_furniture_b.name == ffe_b_name
    assert sfa_furniture_b.move_status == ffe_b_status
    assert sfa_chargeback_b.title == cb_b_title
    assert sfa_chargeback_b.status == cb_b_status


def test_spacefacility_lists_board_prefills_and_csv_never_leak_tenant_b(
    client_a,
    sfa_space_building_a,
    sfa_space_b,
    sfa_building_system_hvac_a,
    sfa_building_system_infra_a,
    sfa_building_system_b,
    sfa_furniture_a,
    sfa_furniture_b,
    sfa_chargeback_draft_a,
    sfa_chargeback_b,
):
    # Lists and infrastructure board (including ?facility_space=<sfa_space_b.pk>)
    for url in (
        reverse("assets:asset_facility_space_list"),
        reverse("assets:asset_building_system_list"),
        reverse("assets:asset_furniture_fixture_list"),
        reverse("assets:asset_space_chargeback_list"),
        reverse("assets:asset_infrastructure_board"),
        f"{reverse('assets:asset_infrastructure_board')}?facility_space={sfa_space_b.pk}",
    ):
        resp = client_a.get(url)
        assert resp.status_code == 200
        body = resp.content.decode("utf-8")
        assert sfa_space_b.number not in body
        assert sfa_space_b.name not in body
        assert sfa_building_system_b.number not in body
        assert sfa_building_system_b.name not in body
        assert sfa_furniture_b.number not in body
        assert sfa_furniture_b.name not in body
        assert sfa_chargeback_b.number not in body
        assert sfa_chargeback_b.title not in body

    # Create GET prefills with foreign ?facility_space=<sfa_space_b.pk> must ignore foreign PK
    for url_name in (
        "assets:asset_building_system_create",
        "assets:asset_furniture_fixture_create",
        "assets:asset_space_chargeback_create",
    ):
        resp = client_a.get(f"{reverse(url_name)}?facility_space={sfa_space_b.pk}")
        assert resp.status_code == 200
        form = resp.context["form"]
        assert "facility_space" not in form.initial
        html = resp.content.decode("utf-8")
        assert sfa_space_b.name not in html
        assert f'value="{sfa_space_b.pk}"' not in html

    # CSV exports (all 4 + infra_only=1) never disclose tenant_b records
    for url in (
        reverse("assets:asset_facility_space_export_csv"),
        reverse("assets:asset_building_system_export_csv"),
        f"{reverse('assets:asset_building_system_export_csv')}?infra_only=1",
        reverse("assets:asset_furniture_fixture_export_csv"),
        reverse("assets:asset_space_chargeback_export_csv"),
    ):
        resp = client_a.get(url)
        assert resp.status_code == 200
        csv_text = resp.content.decode("utf-8")
        assert sfa_space_b.number not in csv_text
        assert sfa_building_system_b.number not in csv_text
        assert sfa_furniture_b.number not in csv_text
        assert sfa_chargeback_b.number not in csv_text


def test_spacefacility_cross_tenant_fk_injection_rejected_on_create_and_edit(
    client_a,
    tenant_a,
    sfa_space_building_a,
    sfa_space_floor_a,
    sfa_space_b,
    sfa_building_system_hvac_a,
    sfa_building_system_b,
    sfa_furniture_a,
    sfa_chargeback_draft_a,
):
    # 1. AssetFacilitySpace: parent=sfa_space_b.pk
    space_count_before = AssetFacilitySpace.objects.filter(tenant=tenant_a).count()
    resp_sp_c = client_a.post(
        reverse("assets:asset_facility_space_create"),
        data=_spacefacility_space_payload(code="SFA-FK-INJ", parent=str(sfa_space_b.pk)),
    )
    assert resp_sp_c.status_code == 200
    assert resp_sp_c.context["form"].errors
    assert AssetFacilitySpace.objects.filter(tenant=tenant_a).count() == space_count_before

    resp_sp_e = client_a.post(
        reverse("assets:asset_facility_space_edit", args=[sfa_space_floor_a.pk]),
        data=_spacefacility_space_payload(
            code=sfa_space_floor_a.code,
            name="Should Not Save Parent B",
            parent=str(sfa_space_b.pk),
        ),
    )
    assert resp_sp_e.status_code == 200
    assert resp_sp_e.context["form"].errors
    sfa_space_floor_a.refresh_from_db()
    assert sfa_space_floor_a.parent_id == sfa_space_building_a.pk

    # 2. AssetBuildingSystem: facility_space=sfa_space_b.pk
    sys_count_before = AssetBuildingSystem.objects.filter(tenant=tenant_a).count()
    resp_bs_c = client_a.post(
        reverse("assets:asset_building_system_create"),
        data=_spacefacility_system_payload(sfa_space_b, name="FK Inj System"),
    )
    assert resp_bs_c.status_code == 200
    assert resp_bs_c.context["form"].errors
    assert AssetBuildingSystem.objects.filter(tenant=tenant_a).count() == sys_count_before

    resp_bs_e = client_a.post(
        reverse("assets:asset_building_system_edit", args=[sfa_building_system_hvac_a.pk]),
        data=_spacefacility_system_payload(sfa_space_b, name="Should Not Save Sys B"),
    )
    assert resp_bs_e.status_code == 200
    assert resp_bs_e.context["form"].errors
    sfa_building_system_hvac_a.refresh_from_db()
    assert sfa_building_system_hvac_a.facility_space_id == sfa_space_floor_a.pk

    # 3. AssetFurnitureFixture: facility_space=sfa_space_b.pk and target_space=sfa_space_b.pk
    ffe_count_before = AssetFurnitureFixture.objects.filter(tenant=tenant_a).count()
    resp_ff_c = client_a.post(
        reverse("assets:asset_furniture_fixture_create"),
        data=_spacefacility_furniture_payload(sfa_space_b, name="FK Inj FFE"),
    )
    assert resp_ff_c.status_code == 200
    assert resp_ff_c.context["form"].errors
    assert AssetFurnitureFixture.objects.filter(tenant=tenant_a).count() == ffe_count_before

    resp_ff_e = client_a.post(
        reverse("assets:asset_furniture_fixture_edit", args=[sfa_furniture_a.pk]),
        data=_spacefacility_furniture_payload(
            sfa_space_floor_a,
            target_space=str(sfa_space_b.pk),
            name="Should Not Save Target B",
        ),
    )
    assert resp_ff_e.status_code == 200
    assert resp_ff_e.context["form"].errors
    sfa_furniture_a.refresh_from_db()
    assert sfa_furniture_a.target_space_id is None

    # 4. AssetSpaceChargeback: facility_space=sfa_space_b.pk and shared_building_system=sfa_building_system_b.pk
    cb_count_before = AssetSpaceChargeback.objects.filter(tenant=tenant_a).count()
    resp_cb_c = client_a.post(
        reverse("assets:asset_space_chargeback_create"),
        data=_spacefacility_chargeback_payload(sfa_space_b, title="FK Inj CB"),
    )
    assert resp_cb_c.status_code == 200
    assert resp_cb_c.context["form"].errors
    assert AssetSpaceChargeback.objects.filter(tenant=tenant_a).count() == cb_count_before

    resp_cb_e = client_a.post(
        reverse("assets:asset_space_chargeback_edit", args=[sfa_chargeback_draft_a.pk]),
        data=_spacefacility_chargeback_payload(
            sfa_space_floor_a,
            shared_building_system=str(sfa_building_system_b.pk),
            title="Should Not Save Sys B",
        ),
    )
    assert resp_cb_e.status_code == 200
    assert resp_cb_e.context["form"].errors
    sfa_chargeback_draft_a.refresh_from_db()
    assert sfa_chargeback_draft_a.shared_building_system_id == sfa_building_system_hvac_a.pk


# =====================================================================
# 2. @tenant_admin_required RBAC (403) & Template Button Hiding
# =====================================================================


def test_spacefacility_non_admin_rbac_403_on_delete_decommission_retire_and_chargeback_actions(
    tenant_a,
    sfa_member_client_a,
    sfa_space_building_a,
    sfa_space_floor_a,
    sfa_building_system_hvac_a,
    sfa_furniture_a,
    sfa_chargeback_draft_a,
    sfa_chargeback_approved_a,
):
    # Create fresh unlinked deletable records so delete checks hit @tenant_admin_required -> 403
    deletable_space = AssetFacilitySpace.objects.create(
        tenant=tenant_a,
        code="SFA-DEL-01",
        name="Deletable Space",
        space_level="room",
        space_category="office_workspace",
    )
    deletable_system = AssetBuildingSystem.objects.create(
        tenant=tenant_a,
        name="Deletable System",
        system_domain="hvac_climate",
        subsystem_type="vav_terminal",
        facility_space=sfa_space_floor_a,
    )
    deletable_ffe = AssetFurnitureFixture.objects.create(
        tenant=tenant_a,
        name="Deletable FFE",
        ffe_category="ergonomic_seating",
        facility_space=sfa_space_floor_a,
    )

    # All 4 *_delete endpoints return 403 for non-admin
    for url_name, pk in (
        ("assets:asset_facility_space_delete", deletable_space.pk),
        ("assets:asset_building_system_delete", deletable_system.pk),
        ("assets:asset_furniture_fixture_delete", deletable_ffe.pk),
        ("assets:asset_space_chargeback_delete", sfa_chargeback_draft_a.pk),
    ):
        resp = sfa_member_client_a.post(reverse(url_name, args=[pk]))
        assert resp.status_code == 403, url_name

    assert AssetFacilitySpace.objects.filter(pk=deletable_space.pk).exists()
    assert AssetBuildingSystem.objects.filter(pk=deletable_system.pk).exists()
    assert AssetFurnitureFixture.objects.filter(pk=deletable_ffe.pk).exists()
    assert AssetSpaceChargeback.objects.filter(pk=sfa_chargeback_draft_a.pk).exists()

    # Decommission & Retire -> 403
    assert (
        sfa_member_client_a.post(
            reverse("assets:asset_facility_space_decommission", args=[deletable_space.pk])
        ).status_code
        == 403
    )
    assert (
        sfa_member_client_a.post(
            reverse("assets:asset_building_system_decommission", args=[sfa_building_system_hvac_a.pk])
        ).status_code
        == 403
    )
    assert (
        sfa_member_client_a.post(
            reverse("assets:asset_furniture_fixture_retire", args=[sfa_furniture_a.pk])
        ).status_code
        == 403
    )

    # Chargeback approve, post_gl, close, and dispute on approved -> 403
    assert (
        sfa_member_client_a.post(
            reverse("assets:asset_space_chargeback_approve", args=[sfa_chargeback_draft_a.pk])
        ).status_code
        == 403
    )
    assert (
        sfa_member_client_a.post(
            reverse("assets:asset_space_chargeback_post_gl", args=[sfa_chargeback_approved_a.pk])
        ).status_code
        == 403
    )
    assert (
        sfa_member_client_a.post(
            reverse("assets:asset_space_chargeback_close", args=[sfa_chargeback_approved_a.pk])
        ).status_code
        == 403
    )
    assert (
        sfa_member_client_a.post(
            reverse("assets:asset_space_chargeback_dispute", args=[sfa_chargeback_approved_a.pk])
        ).status_code
        == 403
    )

    # Verify decommissioned space cannot be reactivated by non-admin (status stays decommissioned)
    AssetFacilitySpace.objects.filter(pk=deletable_space.pk).update(status="decommissioned")
    resp_act = sfa_member_client_a.post(
        reverse("assets:asset_facility_space_activate", args=[deletable_space.pk])
    )
    assert resp_act.status_code == 302
    deletable_space.refresh_from_db()
    assert deletable_space.status == "decommissioned"

    sfa_chargeback_approved_a.refresh_from_db()
    assert sfa_chargeback_approved_a.status == "approved"
    assert sfa_chargeback_approved_a.journal_entry_id is None
    assert sfa_chargeback_approved_a.approved_by_id is not None


def test_spacefacility_templates_hide_admin_only_buttons_from_non_admin(
    tenant_a,
    client_a,
    sfa_member_client_a,
    sfa_space_floor_a,
    sfa_building_system_hvac_a,
    sfa_furniture_a,
    sfa_chargeback_draft_a,
    sfa_chargeback_approved_a,
):
    # Create an unlinked deletable space so can_delete=True for admin_user
    deletable_space = AssetFacilitySpace.objects.create(
        tenant=tenant_a,
        code="SFA-BTN-01",
        name="Button Visibility Space",
        space_level="room",
        space_category="office_workspace",
    )

    # 1. List templates: non-admin sees no delete action forms; admin sees delete forms
    for list_url_name, delete_url_name, obj_pk in (
        ("assets:asset_facility_space_list", "assets:asset_facility_space_delete", deletable_space.pk),
        ("assets:asset_building_system_list", "assets:asset_building_system_delete", sfa_building_system_hvac_a.pk),
        ("assets:asset_furniture_fixture_list", "assets:asset_furniture_fixture_delete", sfa_furniture_a.pk),
        ("assets:asset_space_chargeback_list", "assets:asset_space_chargeback_delete", sfa_chargeback_draft_a.pk),
    ):
        del_path = reverse(delete_url_name, args=[obj_pk])
        member_html = sfa_member_client_a.get(reverse(list_url_name)).content.decode("utf-8")
        admin_html = client_a.get(reverse(list_url_name)).content.decode("utf-8")
        assert del_path not in member_html
        assert del_path in admin_html

    # 2. Detail templates hide admin-only action buttons from non-admin
    # Space detail (active deletable space + decommissioned space)
    sp_detail_url = reverse("assets:asset_facility_space_detail", args=[deletable_space.pk])
    sp_member_html = sfa_member_client_a.get(sp_detail_url).content.decode("utf-8")
    sp_admin_html = client_a.get(sp_detail_url).content.decode("utf-8")
    assert reverse("assets:asset_facility_space_delete", args=[deletable_space.pk]) not in sp_member_html
    assert reverse("assets:asset_facility_space_decommission", args=[deletable_space.pk]) not in sp_member_html
    assert reverse("assets:asset_facility_space_delete", args=[deletable_space.pk]) in sp_admin_html
    assert reverse("assets:asset_facility_space_decommission", args=[deletable_space.pk]) in sp_admin_html

    # Decommissioned space hides activate button from non-admin
    AssetFacilitySpace.objects.filter(pk=deletable_space.pk).update(status="decommissioned")
    sp_dec_member_html = sfa_member_client_a.get(sp_detail_url).content.decode("utf-8")
    assert reverse("assets:asset_facility_space_activate", args=[deletable_space.pk]) not in sp_dec_member_html

    # Building system detail
    bs_detail_url = reverse("assets:asset_building_system_detail", args=[sfa_building_system_hvac_a.pk])
    bs_member_html = sfa_member_client_a.get(bs_detail_url).content.decode("utf-8")
    bs_admin_html = client_a.get(bs_detail_url).content.decode("utf-8")
    assert reverse("assets:asset_building_system_delete", args=[sfa_building_system_hvac_a.pk]) not in bs_member_html
    assert reverse("assets:asset_building_system_decommission", args=[sfa_building_system_hvac_a.pk]) not in bs_member_html
    assert reverse("assets:asset_building_system_delete", args=[sfa_building_system_hvac_a.pk]) in bs_admin_html
    assert reverse("assets:asset_building_system_decommission", args=[sfa_building_system_hvac_a.pk]) in bs_admin_html

    # FF&E detail
    ff_detail_url = reverse("assets:asset_furniture_fixture_detail", args=[sfa_furniture_a.pk])
    ff_member_html = sfa_member_client_a.get(ff_detail_url).content.decode("utf-8")
    ff_admin_html = client_a.get(ff_detail_url).content.decode("utf-8")
    assert reverse("assets:asset_furniture_fixture_delete", args=[sfa_furniture_a.pk]) not in ff_member_html
    assert reverse("assets:asset_furniture_fixture_retire", args=[sfa_furniture_a.pk]) not in ff_member_html
    assert reverse("assets:asset_furniture_fixture_delete", args=[sfa_furniture_a.pk]) in ff_admin_html
    assert reverse("assets:asset_furniture_fixture_retire", args=[sfa_furniture_a.pk]) in ff_admin_html

    # Chargeback detail (draft + approved)
    cb_draft_url = reverse("assets:asset_space_chargeback_detail", args=[sfa_chargeback_draft_a.pk])
    cb_draft_member_html = sfa_member_client_a.get(cb_draft_url).content.decode("utf-8")
    cb_draft_admin_html = client_a.get(cb_draft_url).content.decode("utf-8")
    assert reverse("assets:asset_space_chargeback_delete", args=[sfa_chargeback_draft_a.pk]) not in cb_draft_member_html
    assert reverse("assets:asset_space_chargeback_approve", args=[sfa_chargeback_draft_a.pk]) not in cb_draft_member_html
    assert reverse("assets:asset_space_chargeback_delete", args=[sfa_chargeback_draft_a.pk]) in cb_draft_admin_html
    assert reverse("assets:asset_space_chargeback_approve", args=[sfa_chargeback_draft_a.pk]) in cb_draft_admin_html

    cb_app_url = reverse("assets:asset_space_chargeback_detail", args=[sfa_chargeback_approved_a.pk])
    cb_app_member_html = sfa_member_client_a.get(cb_app_url).content.decode("utf-8")
    cb_app_admin_html = client_a.get(cb_app_url).content.decode("utf-8")
    assert reverse("assets:asset_space_chargeback_dispute", args=[sfa_chargeback_approved_a.pk]) not in cb_app_member_html
    assert reverse("assets:asset_space_chargeback_post_gl", args=[sfa_chargeback_approved_a.pk]) not in cb_app_member_html
    assert reverse("assets:asset_space_chargeback_close", args=[sfa_chargeback_approved_a.pk]) not in cb_app_member_html
    assert reverse("assets:asset_space_chargeback_dispute", args=[sfa_chargeback_approved_a.pk]) in cb_app_admin_html
    assert reverse("assets:asset_space_chargeback_post_gl", args=[sfa_chargeback_approved_a.pk]) in cb_app_admin_html
    assert reverse("assets:asset_space_chargeback_close", args=[sfa_chargeback_approved_a.pk]) in cb_app_admin_html


# =====================================================================
# 3. HTTP Method Enforcement (405 Method Not Allowed)
# =====================================================================


def test_spacefacility_get_on_post_only_endpoints_returns_405(
    client_a,
    sfa_space_floor_a,
    sfa_building_system_hvac_a,
    sfa_furniture_a,
    sfa_chargeback_draft_a,
):
    post_only_endpoints = [
        ("assets:asset_facility_space_delete", sfa_space_floor_a.pk),
        ("assets:asset_facility_space_recalculate_utilization", sfa_space_floor_a.pk),
        ("assets:asset_facility_space_mark_under_renovation", sfa_space_floor_a.pk),
        ("assets:asset_facility_space_activate", sfa_space_floor_a.pk),
        ("assets:asset_facility_space_decommission", sfa_space_floor_a.pk),
        ("assets:asset_building_system_delete", sfa_building_system_hvac_a.pk),
        ("assets:asset_building_system_evaluate_comfort", sfa_building_system_hvac_a.pk),
        ("assets:asset_building_system_record_inspection", sfa_building_system_hvac_a.pk),
        ("assets:asset_building_system_flag_maintenance", sfa_building_system_hvac_a.pk),
        ("assets:asset_building_system_restore_operational", sfa_building_system_hvac_a.pk),
        ("assets:asset_building_system_decommission", sfa_building_system_hvac_a.pk),
        ("assets:asset_furniture_fixture_delete", sfa_furniture_a.pk),
        ("assets:asset_furniture_fixture_request_move", sfa_furniture_a.pk),
        ("assets:asset_furniture_fixture_schedule_reconfig", sfa_furniture_a.pk),
        ("assets:asset_furniture_fixture_complete_move", sfa_furniture_a.pk),
        ("assets:asset_furniture_fixture_retire", sfa_furniture_a.pk),
        ("assets:asset_space_chargeback_delete", sfa_chargeback_draft_a.pk),
        ("assets:asset_space_chargeback_submit_approval", sfa_chargeback_draft_a.pk),
        ("assets:asset_space_chargeback_approve", sfa_chargeback_draft_a.pk),
        ("assets:asset_space_chargeback_post_gl", sfa_chargeback_draft_a.pk),
        ("assets:asset_space_chargeback_dispute", sfa_chargeback_draft_a.pk),
        ("assets:asset_space_chargeback_close", sfa_chargeback_draft_a.pk),
    ]
    for url_name, pk in post_only_endpoints:
        resp = client_a.get(reverse(url_name, args=[pk]))
        assert resp.status_code == 405, url_name


# =====================================================================
# 4. Cross-Feature AssetDocument access_classification ACL (I4)
# =====================================================================


def test_spacefacility_restricted_document_acl_on_space_and_building_system(
    client_a,
    sfa_member_client_a,
    tenant_a,
    adk_document_restricted_a,
    sfa_space_floor_a,
    sfa_building_system_hvac_a,
):
    sfa_space_floor_a.floor_plan_document = adk_document_restricted_a
    sfa_space_floor_a.save(update_fields=["floor_plan_document", "updated_at"])

    sfa_building_system_hvac_a.schematic_document = adk_document_restricted_a
    sfa_building_system_hvac_a.save(update_fields=["schematic_document", "updated_at"])

    doc_num = adk_document_restricted_a.number
    doc_title = adk_document_restricted_a.title
    doc_detail_url = reverse("assets:asset_document_detail", args=[adk_document_restricted_a.pk])

    # Detail pages: non-admin sees "Restricted Document" without number/title/link; admin sees number & link
    for detail_url in (
        reverse("assets:asset_facility_space_detail", args=[sfa_space_floor_a.pk]),
        reverse("assets:asset_building_system_detail", args=[sfa_building_system_hvac_a.pk]),
    ):
        member_html = sfa_member_client_a.get(detail_url).content.decode("utf-8")
        admin_html = client_a.get(detail_url).content.decode("utf-8")
        assert "Restricted Document" in member_html
        assert doc_num not in member_html
        assert doc_title not in member_html
        assert doc_detail_url not in member_html
        assert doc_num in admin_html
        assert doc_detail_url in admin_html

    # Form HTML: non-admin excludes restricted doc option; admin includes it
    for form_url in (
        reverse("assets:asset_facility_space_create"),
        reverse("assets:asset_facility_space_edit", args=[sfa_space_floor_a.pk]),
        reverse("assets:asset_building_system_create"),
        reverse("assets:asset_building_system_edit", args=[sfa_building_system_hvac_a.pk]),
    ):
        member_form_html = sfa_member_client_a.get(form_url).content.decode("utf-8")
        admin_form_html = client_a.get(form_url).content.decode("utf-8")
        assert doc_title not in member_form_html
        assert doc_num not in member_form_html
        assert doc_title in admin_form_html

    # Non-admin POST tampering with adk_document_restricted_a.pk rejected
    space_count = AssetFacilitySpace.objects.filter(tenant=tenant_a).count()
    resp_sp_tamper = sfa_member_client_a.post(
        reverse("assets:asset_facility_space_create"),
        data=_spacefacility_space_payload(
            code="SFA-ACL-01",
            floor_plan_document=str(adk_document_restricted_a.pk),
        ),
    )
    assert resp_sp_tamper.status_code == 200
    assert "floor_plan_document" in resp_sp_tamper.context["form"].errors
    assert AssetFacilitySpace.objects.filter(tenant=tenant_a).count() == space_count

    sys_count = AssetBuildingSystem.objects.filter(tenant=tenant_a).count()
    resp_bs_tamper = sfa_member_client_a.post(
        reverse("assets:asset_building_system_create"),
        data=_spacefacility_system_payload(
            sfa_space_floor_a,
            name="ACL Tamper System",
            schematic_document=str(adk_document_restricted_a.pk),
        ),
    )
    assert resp_bs_tamper.status_code == 200
    assert "schematic_document" in resp_bs_tamper.context["form"].errors
    assert AssetBuildingSystem.objects.filter(tenant=tenant_a).count() == sys_count


# =====================================================================
# 5. Upload & Protected Download Hardening
# =====================================================================


def test_spacefacility_svg_upload_rejected_by_post_and_model_clean(
    tmp_path,
    settings,
    client_a,
    tenant_a,
    sfa_space_floor_a,
):
    settings.MEDIA_ROOT = str(tmp_path)
    svg_payload = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'

    # HTTP POST create
    count_before = AssetFacilitySpace.objects.filter(tenant=tenant_a).count()
    svg_create = SimpleUploadedFile("xss.svg", svg_payload, content_type="image/svg+xml")
    resp_create = client_a.post(
        reverse("assets:asset_facility_space_create"),
        data={
            **_spacefacility_space_payload(code="SFA-SVG-01"),
            "floor_plan_image": svg_create,
        },
    )
    assert resp_create.status_code == 200
    assert "floor_plan_image" in resp_create.context["form"].errors
    assert AssetFacilitySpace.objects.filter(tenant=tenant_a).count() == count_before

    # HTTP POST edit
    svg_edit = SimpleUploadedFile("evil.svg", svg_payload, content_type="image/svg+xml")
    resp_edit = client_a.post(
        reverse("assets:asset_facility_space_edit", args=[sfa_space_floor_a.pk]),
        data={
            **_spacefacility_space_payload(code=sfa_space_floor_a.code, name="SVG Edit"),
            "floor_plan_image": svg_edit,
        },
    )
    assert resp_edit.status_code == 200
    assert "floor_plan_image" in resp_edit.context["form"].errors
    sfa_space_floor_a.refresh_from_db()
    assert not sfa_space_floor_a.floor_plan_image

    # Model full_clean() directly
    bad_space = AssetFacilitySpace(
        tenant=tenant_a,
        code="SFA-SVG-MOD",
        name="Model SVG Check",
        floor_plan_image=SimpleUploadedFile("model.svg", svg_payload, content_type="image/svg+xml"),
    )
    with pytest.raises(ValidationError) as exc_info:
        bad_space.full_clean()
    assert "floor_plan_image" in exc_info.value.error_dict


def test_spacefacility_floor_plan_download_headers_and_no_raw_media_url(
    tmp_path,
    settings,
    client_a,
    sfa_space_floor_a,
):
    settings.MEDIA_ROOT = str(tmp_path)

    # Space without floor plan returns 404 on download endpoint
    download_url = reverse("assets:asset_facility_space_floor_plan_download", args=[sfa_space_floor_a.pk])
    assert client_a.get(download_url).status_code == 404

    # Upload valid PNG, then test unsafe chars in original_floor_plan_name are stripped
    png_file = SimpleUploadedFile("floor_plan_v1.png", _SPACEFACILITY_SAMPLE_PNG, content_type="image/png")
    sfa_space_floor_a.floor_plan_image = png_file
    sfa_space_floor_a.save()
    AssetFacilitySpace.objects.filter(pk=sfa_space_floor_a.pk).update(
        original_floor_plan_name='evil"\r\n;floor/plan\\v1.png'
    )
    sfa_space_floor_a.refresh_from_db()

    # Detail page uses protected download URL and never leaks raw /media/ URL
    detail_html = client_a.get(
        reverse("assets:asset_facility_space_detail", args=[sfa_space_floor_a.pk])
    ).content.decode("utf-8")
    assert download_url in detail_html
    assert sfa_space_floor_a.floor_plan_image.url not in detail_html
    assert "/media/" not in detail_html

    # Download response headers
    resp_dl = client_a.get(download_url)
    assert resp_dl.status_code == 200
    assert resp_dl["X-Content-Type-Options"] == "nosniff"
    cd = resp_dl["Content-Disposition"]
    assert cd.startswith("attachment;")
    assert "\r" not in cd and "\n" not in cd
    assert ";" not in cd.split(";", 1)[1]
    assert "\\" not in cd


# =====================================================================
# 6. CSV Formula Injection & XSS Escaping
# =====================================================================


def test_spacefacility_csv_formula_injection_neutralized_all_entities(
    client_a,
    tenant_a,
    sfa_space_floor_a,
):
    today = timezone.localdate()

    sp = AssetFacilitySpace.objects.create(
        tenant=tenant_a,
        code="=CODE1",
        name="+SUM(1,2)",
        cad_layer_ref="-CMD|calc",
        bim_guid="@HYPERLINK(1)",
    )
    bs = AssetBuildingSystem.objects.create(
        tenant=tenant_a,
        name="=SYS(1)",
        system_domain="electrical_power",
        subsystem_type="switchgear_panel",
        facility_space=sfa_space_floor_a,
        ashrae_nfpa_code_ref="@NFPA70E",
    )
    ff = AssetFurnitureFixture.objects.create(
        tenant=tenant_a,
        name="-FFE_FORMULA",
        ffe_category="workstation_desk",
        asset_tag_code="+TAG123",
        reconfiguration_batch_ref="@BATCH1",
        facility_space=sfa_space_floor_a,
    )
    cb = AssetSpaceChargeback.objects.create(
        tenant=tenant_a,
        title="=CB_FORMULA(A1)",
        facility_space=sfa_space_floor_a,
        period_start=today.replace(day=1),
        period_end=today,
        base_cost_amount=Decimal("100.00"),
    )

    sp_rows = _spacefacility_parse_csv(client_a.get(reverse("assets:asset_facility_space_export_csv")))
    sp_row = next(r for r in sp_rows if r[0] == sp.number)
    assert sp_row[1] == "'=CODE1"
    assert sp_row[2] == "'+SUM(1,2)"
    assert sp_row[15] == "'-CMD|calc"
    assert sp_row[16] == "'@HYPERLINK(1)"

    for bs_url in (
        reverse("assets:asset_building_system_export_csv"),
        f"{reverse('assets:asset_building_system_export_csv')}?infra_only=1",
    ):
        bs_rows = _spacefacility_parse_csv(client_a.get(bs_url))
        bs_row = next(r for r in bs_rows if r[0] == bs.number)
        assert bs_row[1] == "'=SYS(1)"
        assert bs_row[5] == "'@NFPA70E"

    ff_rows = _spacefacility_parse_csv(client_a.get(reverse("assets:asset_furniture_fixture_export_csv")))
    ff_row = next(r for r in ff_rows if r[0] == ff.number)
    assert ff_row[1] == "'-FFE_FORMULA"
    assert ff_row[3] == "'+TAG123"
    assert ff_row[12] == "'@BATCH1"

    cb_rows = _spacefacility_parse_csv(client_a.get(reverse("assets:asset_space_chargeback_export_csv")))
    cb_row = next(r for r in cb_rows if r[0] == cb.number)
    assert cb_row[1] == "'=CB_FORMULA(A1)"


def test_spacefacility_xss_script_payloads_escaped_in_list_board_and_detail(
    client_a,
    tenant_a,
    sfa_space_floor_a,
):
    today = timezone.localdate()
    xss = "<script>alert(1)</script>"
    escaped_xss = "&lt;script&gt;alert(1)&lt;/script&gt;"

    sp = AssetFacilitySpace.objects.create(
        tenant=tenant_a,
        code="SFA-XSS-01",
        name=f"XSS Space {xss}",
        notes=f"Note {xss}",
    )
    bs = AssetBuildingSystem.objects.create(
        tenant=tenant_a,
        name=f"XSS System {xss}",
        system_domain="electrical_power",
        subsystem_type="switchgear_panel",
        facility_space=sp,
        notes=f"Note {xss}",
    )
    ff = AssetFurnitureFixture.objects.create(
        tenant=tenant_a,
        name=f"XSS FFE {xss}",
        ffe_category="workstation_desk",
        facility_space=sp,
        move_notes=f"Move {xss}",
    )
    cb = AssetSpaceChargeback.objects.create(
        tenant=tenant_a,
        title=f"XSS CB {xss}",
        facility_space=sp,
        period_start=today.replace(day=1),
        period_end=today,
        base_cost_amount=Decimal("250.00"),
        notes=f"Note {xss}",
    )

    urls_to_check = [
        reverse("assets:asset_facility_space_list"),
        reverse("assets:asset_facility_space_detail", args=[sp.pk]),
        reverse("assets:asset_building_system_list"),
        reverse("assets:asset_infrastructure_board"),
        reverse("assets:asset_building_system_detail", args=[bs.pk]),
        reverse("assets:asset_furniture_fixture_list"),
        reverse("assets:asset_furniture_fixture_detail", args=[ff.pk]),
        reverse("assets:asset_space_chargeback_list"),
        reverse("assets:asset_space_chargeback_detail", args=[cb.pk]),
    ]
    for url in urls_to_check:
        resp = client_a.get(url)
        assert resp.status_code == 200, url
        html = resp.content.decode("utf-8")
        assert xss not in html, url
        assert escaped_xss in html, url


# =====================================================================
# 7. Mass-Assignment & Lock / Protect Tampering
# =====================================================================


def test_spacefacility_mass_assignment_tampering_ignored_on_create_and_edit(
    client_a,
    tenant_a,
    tenant_b,
    admin_user,
    sfa_space_floor_a,
    sfa_building_system_hvac_a,
    sfa_furniture_a,
    sfa_chargeback_draft_a,
):
    # 1. Space create tampering
    resp_sp = client_a.post(
        reverse("assets:asset_facility_space_create"),
        data=_spacefacility_space_payload(
            code="SFA-MA-01",
            tenant=str(tenant_b.pk),
            number="FORGED-9999",
            status="decommissioned",
            occupancy_status="offline",
            original_floor_plan_name="forged.png",
        ),
    )
    assert resp_sp.status_code == 302
    sp = AssetFacilitySpace.objects.get(tenant=tenant_a, code="SFA-MA-01")
    assert sp.tenant_id == tenant_a.pk
    assert sp.number.startswith("AFSP-")
    assert sp.number != "FORGED-9999"
    assert sp.status == "active"
    assert sp.occupancy_status == "occupied"
    assert sp.original_floor_plan_name == ""

    # 2. Building system create tampering
    resp_bs = client_a.post(
        reverse("assets:asset_building_system_create"),
        data=_spacefacility_system_payload(
            sfa_space_floor_a,
            name="Mass Assign System",
            tenant=str(tenant_b.pk),
            number="FORGED-BS",
            status="decommissioned",
            comfort_status="out_of_band",
        ),
    )
    assert resp_bs.status_code == 302
    bs = AssetBuildingSystem.objects.get(tenant=tenant_a, name="Mass Assign System")
    assert bs.tenant_id == tenant_a.pk
    assert bs.number.startswith("AFBS-")
    assert bs.status == "operational"
    assert bs.comfort_status == "optimal"

    # 3. FF&E create tampering
    resp_ff = client_a.post(
        reverse("assets:asset_furniture_fixture_create"),
        data=_spacefacility_furniture_payload(
            sfa_space_floor_a,
            name="Mass Assign FFE",
            tenant=str(tenant_b.pk),
            number="FORGED-FFE",
            move_status="retired",
        ),
    )
    assert resp_ff.status_code == 302
    ff = AssetFurnitureFixture.objects.get(tenant=tenant_a, name="Mass Assign FFE")
    assert ff.tenant_id == tenant_a.pk
    assert ff.number.startswith("AFFE-")
    assert ff.move_status == "in_place"

    # 4. Chargeback create & edit tampering
    resp_cb = client_a.post(
        reverse("assets:asset_space_chargeback_create"),
        data=_spacefacility_chargeback_payload(
            sfa_space_floor_a,
            title="Mass Assign CB",
            tenant=str(tenant_b.pk),
            number="FORGED-CB",
            status="posted_to_gl",
            net_chargeback_amount="0.01",
            approved_by=str(admin_user.pk),
            journal_entry="999999",
        ),
    )
    assert resp_cb.status_code == 302
    cb = AssetSpaceChargeback.objects.get(tenant=tenant_a, title="Mass Assign CB")
    assert cb.tenant_id == tenant_a.pk
    assert cb.number.startswith("AFCB-")
    assert cb.status == "draft"
    assert cb.net_chargeback_amount == Decimal("3100.00")
    assert cb.approved_by_id is None
    assert cb.journal_entry_id is None

    # Edit tampering on existing records preserves tenant, number, and server-owned fields
    orig_cb_num = sfa_chargeback_draft_a.number
    resp_cb_e = client_a.post(
        reverse("assets:asset_space_chargeback_edit", args=[sfa_chargeback_draft_a.pk]),
        data=_spacefacility_chargeback_payload(
            sfa_space_floor_a,
            title="Edited CB Tamper",
            tenant=str(tenant_b.pk),
            number="FORGED-CB-EDIT",
            status="approved",
            net_chargeback_amount="1.00",
            approved_by=str(admin_user.pk),
        ),
    )
    assert resp_cb_e.status_code == 302
    sfa_chargeback_draft_a.refresh_from_db()
    assert sfa_chargeback_draft_a.tenant_id == tenant_a.pk
    assert sfa_chargeback_draft_a.number == orig_cb_num
    assert sfa_chargeback_draft_a.status == "draft"
    assert sfa_chargeback_draft_a.approved_by_id is None
    assert sfa_chargeback_draft_a.net_chargeback_amount == Decimal("3100.00")


def test_spacefacility_locked_records_reject_edit_delete_and_protect_journal_entry(
    client_a,
    tenant_a,
    sfa_space_floor_a,
    sfa_building_system_hvac_a,
    sfa_furniture_a,
    sfa_chargeback_approved_a,
):
    # 1. Decommissioned Space rejects edit GET/POST & delete POST
    dec_space = AssetFacilitySpace.objects.create(
        tenant=tenant_a,
        code="SFA-LOCK-01",
        name="Locked Space",
        status="decommissioned",
    )
    assert client_a.get(reverse("assets:asset_facility_space_edit", args=[dec_space.pk])).status_code == 302
    assert (
        client_a.post(
            reverse("assets:asset_facility_space_edit", args=[dec_space.pk]),
            data=_spacefacility_space_payload(code=dec_space.code, name="Mutated Locked Space"),
        ).status_code
        == 302
    )
    assert client_a.post(reverse("assets:asset_facility_space_delete", args=[dec_space.pk])).status_code == 302
    dec_space.refresh_from_db()
    assert dec_space.name == "Locked Space"

    # 2. Decommissioned Building System rejects edit GET/POST & delete POST
    AssetBuildingSystem.objects.filter(pk=sfa_building_system_hvac_a.pk).update(status="decommissioned")
    sfa_building_system_hvac_a.refresh_from_db()
    orig_sys_name = sfa_building_system_hvac_a.name
    assert (
        client_a.get(
            reverse("assets:asset_building_system_edit", args=[sfa_building_system_hvac_a.pk])
        ).status_code
        == 302
    )
    assert (
        client_a.post(
            reverse("assets:asset_building_system_edit", args=[sfa_building_system_hvac_a.pk]),
            data=_spacefacility_system_payload(sfa_space_floor_a, name="Mutated Locked System"),
        ).status_code
        == 302
    )
    assert (
        client_a.post(
            reverse("assets:asset_building_system_delete", args=[sfa_building_system_hvac_a.pk])
        ).status_code
        == 302
    )
    sfa_building_system_hvac_a.refresh_from_db()
    assert sfa_building_system_hvac_a.name == orig_sys_name

    # 3. Retired FF&E rejects edit GET/POST & delete POST
    AssetFurnitureFixture.objects.filter(pk=sfa_furniture_a.pk).update(move_status="retired")
    sfa_furniture_a.refresh_from_db()
    orig_ffe_name = sfa_furniture_a.name
    assert (
        client_a.get(reverse("assets:asset_furniture_fixture_edit", args=[sfa_furniture_a.pk])).status_code
        == 302
    )
    assert (
        client_a.post(
            reverse("assets:asset_furniture_fixture_edit", args=[sfa_furniture_a.pk]),
            data=_spacefacility_furniture_payload(sfa_space_floor_a, name="Mutated Retired FFE"),
        ).status_code
        == 302
    )
    assert (
        client_a.post(reverse("assets:asset_furniture_fixture_delete", args=[sfa_furniture_a.pk])).status_code
        == 302
    )
    sfa_furniture_a.refresh_from_db()
    assert sfa_furniture_a.name == orig_ffe_name

    # 4. Approved chargeback rejects edit GET/POST & delete POST
    orig_cb_title = sfa_chargeback_approved_a.title
    assert (
        client_a.get(
            reverse("assets:asset_space_chargeback_edit", args=[sfa_chargeback_approved_a.pk])
        ).status_code
        == 302
    )
    assert (
        client_a.post(
            reverse("assets:asset_space_chargeback_edit", args=[sfa_chargeback_approved_a.pk]),
            data=_spacefacility_chargeback_payload(sfa_space_floor_a, title="Mutated Approved CB"),
        ).status_code
        == 302
    )
    assert (
        client_a.post(
            reverse("assets:asset_space_chargeback_delete", args=[sfa_chargeback_approved_a.pk])
        ).status_code
        == 302
    )
    sfa_chargeback_approved_a.refresh_from_db()
    assert sfa_chargeback_approved_a.title == orig_cb_title

    # 5. Post to GL, verify posted_to_gl & closed lock guards + JournalEntry PROTECT (I1)
    resp_post = client_a.post(
        reverse("assets:asset_space_chargeback_post_gl", args=[sfa_chargeback_approved_a.pk])
    )
    assert resp_post.status_code == 302
    sfa_chargeback_approved_a.refresh_from_db()
    assert sfa_chargeback_approved_a.status == "posted_to_gl"
    je = sfa_chargeback_approved_a.journal_entry
    assert je is not None

    assert (
        client_a.post(
            reverse("assets:asset_space_chargeback_edit", args=[sfa_chargeback_approved_a.pk]),
            data=_spacefacility_chargeback_payload(sfa_space_floor_a, title="Mutated Posted CB"),
        ).status_code
        == 302
    )
    assert (
        client_a.post(
            reverse("assets:asset_space_chargeback_delete", args=[sfa_chargeback_approved_a.pk])
        ).status_code
        == 302
    )
    sfa_chargeback_approved_a.refresh_from_db()
    assert sfa_chargeback_approved_a.title == orig_cb_title

    with pytest.raises(ProtectedError):
        je.delete()
    assert JournalEntry.objects.filter(pk=je.pk).exists()
    assert AssetSpaceChargeback.objects.filter(pk=sfa_chargeback_approved_a.pk).exists()

    # Close and verify closed status also rejects edit/delete
    assert (
        client_a.post(
            reverse("assets:asset_space_chargeback_close", args=[sfa_chargeback_approved_a.pk])
        ).status_code
        == 302
    )
    sfa_chargeback_approved_a.refresh_from_db()
    assert sfa_chargeback_approved_a.status == "closed"
    assert (
        client_a.post(
            reverse("assets:asset_space_chargeback_edit", args=[sfa_chargeback_approved_a.pk]),
            data=_spacefacility_chargeback_payload(sfa_space_floor_a, title="Mutated Closed CB"),
        ).status_code
        == 302
    )
    assert (
        client_a.post(
            reverse("assets:asset_space_chargeback_delete", args=[sfa_chargeback_approved_a.pk])
        ).status_code
        == 302
    )
    sfa_chargeback_approved_a.refresh_from_db()
    assert sfa_chargeback_approved_a.title == orig_cb_title
