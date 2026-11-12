"""
View, workflow, board, CSV export, upload/download, and query-budget tests for
Module 11.17: Space & Facility Asset Management.

Covers:
1. Package re-exports (`apps.assets.views`), `LIVE_LINKS["11.17"]`, and anonymous
   redirect-to-login across all key 11.17 endpoints.
2. `assets:overview` (200 OK, 11.17 KPI keys, rendered cards, query budget <= 34).
3. All 5 list/board views (`asset_facility_space_list`, `asset_building_system_list`,
   `asset_furniture_fixture_list`, `asset_space_chargeback_list`,
   `asset_infrastructure_board`) + all 4 detail views:
   - Exact pinned context keys, seeded record visibility, no template comment leaks.
   - Query budgets (`django_assert_max_num_queries`): lists/board <= 14,
     `asset_building_system_list` <= 12, details <= 10 (`asset_facility_space_detail`
     renders 4 child lists + main space + middleware/session = 12 total / <= 10
     non-session queries).
   - Choice filters, FK filters, `q=` search (including `load_or_voltage_rating`
     on board & CSV, `criticality_tier` on board & `infra_only=1` CSV), junk
     params (`abc`, `-1`, `?page=999`, `?page=abc`), and page 2 pagination.
   - `0.00` numeric measurement rendering on Building System list & detail (I10).
4. CRUD & prefills across all 4 entities:
   - `?facility_space=` prefill on child creates, POST create/edit/delete -> 302.
   - `tenant=None` superuser create GET & POST redirect cleanly without 500 (M3).
5. Floor-plan PNG upload, protected attachment download (`Content-Disposition:
   attachment`, `X-Content-Type-Options: nosniff`), and preservation of
   `original_floor_plan_name` on subsequent non-upload edits (M5).
6. All 4 CSV exports + Infrastructure Board `infra_only=1` CSV export (headers,
   `text/csv`, `nosniff`, `csv_safe` formula-injection neutralization, scope).
7. Lifecycle workflows & cross-module integrations:
   - Space: `recalculate-utilization`, `mark-renovation`, `activate`, `decommission`
     and `is_locked=True` guards.
   - Building system: `evaluate-comfort`, `record-inspection`, `flag-maintenance`,
     `restore-operational`, `decommission` and `is_locked=True` guards.
   - FF&E IMAC: `request-move` -> `schedule-reconfig` (`sched_mv`) ->
     `complete-move` (relocates `facility_space`, clears `target_space`, preserves
     `custodian_party`, creates linked `AssetMovementLog`, `comp_move`) -> `retire`.
   - Chargeback GL: `draft` -> `submit-approval` -> `approve` -> `post-gl`
     (balanced `JournalEntry(status="posted")` + 2 `JournalLine`s), blocks
     double-post, blocks closed `FiscalPeriod`, admin `dispute` clears
     `approved_by`/`approved_at`, and `close` locks the record.
"""

import csv
import io
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

import apps.assets.views as assets_views
import apps.assets.views.SpaceFacilityAsset as sfa_views
from apps.accounting.models import JournalEntry, JournalLine
from apps.assets.models import (
    AssetBuildingSystem,
    AssetFacilitySpace,
    AssetFurnitureFixture,
    AssetMovementLog,
    AssetSpaceChargeback,
)
from apps.core.models import AuditLog
from apps.core.navigation import LIVE_LINKS

User = get_user_model()

pytestmark = pytest.mark.django_db

_SPACEFACILITY_SAMPLE_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc`\x00\x00"
    b"\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
)


# =====================================================================
# Module-level Helpers (Must start with _spacefacility_*)
# =====================================================================


def _spacefacility_messages(response):
    """Return queued Django flash message strings for a response."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _spacefacility_superuser_no_tenant_client():
    """Create and authenticate a superuser whose active tenant is None."""
    su = User.objects.create_superuser(
        email="platform_super_11_17_views@naverp.test",
        username="platform_super_11_17_views",
        password="TestPass123!",
        tenant=None,
    )
    client = Client()
    client.force_login(su)
    return client


def _spacefacility_latest_audit(tenant, obj, action=None):
    ct = ContentType.objects.get_for_model(obj.__class__)
    qs = AuditLog.objects.filter(tenant=tenant, content_type=ct, object_id=obj.pk)
    if action is not None:
        qs = qs.filter(action=action)
    return qs.order_by("-at", "-pk").first()


def _spacefacility_assert_no_template_leaks(response):
    html = response.content.decode("utf-8")
    assert "{#" not in html
    assert "{% comment" not in html


def _spacefacility_space_payload(**overrides):
    data = {
        "code": "SFA-RM-301",
        "name": "Engineering Bay 301",
        "space_level": "room",
        "space_category": "office_workspace",
        "gross_area_sqft": "2500.00",
        "rentable_area_sqft": "2250.00",
        "usable_area_sqft": "2000.00",
        "common_area_sqft": "250.00",
        "annual_rate_per_sqft": "44.00",
        "design_seat_capacity": "25",
        "current_headcount": "20",
        "cad_layer_ref": "A-RM-301",
        "bim_guid": "guid-rm-301",
        "bim_level_ref": "Level 03",
        "drawing_revision": "Rev A",
        "notes": "Created via view test.",
    }
    data.update(overrides)
    return data


def _spacefacility_system_payload(facility_space, **overrides):
    today = timezone.localdate()
    data = {
        "name": "Chiller CH-03",
        "system_domain": "hvac_climate",
        "subsystem_type": "chiller_plant",
        "facility_space": str(facility_space.pk),
        "pin_x_pct": "20.00",
        "pin_y_pct": "35.00",
        "manufacturer": "Carrier",
        "model_number": "30XA-200",
        "serial_number": "CAR-1117-03",
        "load_or_voltage_rating": "480V / 3-Phase",
        "ashrae_nfpa_code_ref": "ASHRAE 90.1",
        "served_area_sqft": "6400.00",
        "design_capacity_btu_kw": "450.00",
        "refrigerant_type": "R-134a",
        "setpoint_temp_c": "21.00",
        "measured_temp_c": "21.40",
        "target_humidity_pct": "45.00",
        "measured_humidity_pct": "46.00",
        "airflow_cfm": "10500.00",
        "energy_efficiency_rating": "IPLV 19.2",
        "condition_grade": "good",
        "criticality_tier": "tier_2_mission_crit",
        "remaining_useful_life_years": "15",
        "replacement_cost_estimate": "110000.00",
        "last_statutory_inspection_date": (today - timedelta(days=10)).isoformat(),
        "next_inspection_due_date": (today + timedelta(days=355)).isoformat(),
        "notes": "Commissioned chiller unit.",
    }
    data.update(overrides)
    return data


def _spacefacility_furniture_payload(facility_space, **overrides):
    today = timezone.localdate()
    data = {
        "name": "Collaborative Bench Cluster 10",
        "ffe_category": "workstation_desk",
        "asset_tag_code": "SFA-TAG-310",
        "manufacturer": "Steelcase",
        "model_sku": "SC-BENCH-10",
        "finish_material": "Maple / Charcoal",
        "facility_space": str(facility_space.pk),
        "quantity": "8",
        "unit_replacement_cost": "1250.00",
        "pin_x_pct": "45.00",
        "pin_y_pct": "52.00",
        "condition_grade": "good",
        "reconfiguration_batch_ref": "IMAC-2026-Q4",
        "move_scheduled_date": (today + timedelta(days=14)).isoformat(),
        "estimated_move_cost": "600.00",
        "move_notes": "Phase 2 office densification.",
    }
    data.update(overrides)
    return data


def _spacefacility_chargeback_payload(facility_space, **overrides):
    today = timezone.localdate()
    data = {
        "title": "Q4 Engineering Wing Allocation",
        "coordination_type": "space_chargeback",
        "allocation_basis": "usable_sqft",
        "facility_space": str(facility_space.pk),
        "period_start": today.replace(day=1).isoformat(),
        "period_end": today.isoformat(),
        "allocated_area_sqft": "3200.00",
        "allocation_share_pct": "50.00",
        "base_cost_amount": "4000.00",
        "shared_cam_amount": "750.00",
        "utility_recovery_amount": "250.00",
        "ti_improvement_cost": "300.00",
        "ti_allowance_offset": "100.00",
        "notes": "Quarterly chargeback run.",
    }
    data.update(overrides)
    return data


def _spacefacility_make_space(tenant, code, name="Generated Space", **kwargs):
    data = {
        "tenant": tenant,
        "code": code,
        "name": name,
        "space_level": "room",
        "space_category": "office_workspace",
        "gross_area_sqft": Decimal("1000.00"),
        "rentable_area_sqft": Decimal("900.00"),
        "usable_area_sqft": Decimal("800.00"),
        "common_area_sqft": Decimal("100.00"),
        "annual_rate_per_sqft": Decimal("30.00"),
        "design_seat_capacity": 10,
        "current_headcount": 6,
        "status": "active",
    }
    data.update(kwargs)
    return AssetFacilitySpace.objects.create(**data)


def _spacefacility_make_system(tenant, space, name="Generated System", **kwargs):
    data = {
        "tenant": tenant,
        "name": name,
        "system_domain": "hvac_climate",
        "subsystem_type": "ahu_air_handler",
        "facility_space": space,
        "condition_grade": "good",
        "criticality_tier": "tier_3_operational",
        "status": "operational",
    }
    data.update(kwargs)
    return AssetBuildingSystem.objects.create(**data)


def _spacefacility_make_furniture(tenant, space, name="Generated FF&E", **kwargs):
    data = {
        "tenant": tenant,
        "name": name,
        "ffe_category": "workstation_desk",
        "facility_space": space,
        "quantity": 2,
        "unit_replacement_cost": Decimal("500.00"),
        "condition_grade": "good",
        "move_status": "in_place",
    }
    data.update(kwargs)
    return AssetFurnitureFixture.objects.create(**data)


def _spacefacility_make_chargeback(tenant, space, title="Generated Chargeback", **kwargs):
    today = timezone.localdate()
    data = {
        "tenant": tenant,
        "title": title,
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
# 1. Package Re-exports, Navigation Contract & Anonymous Redirects
# =====================================================================


def test_spacefacility_view_reexports_and_navigation_contract():
    assert len(sfa_views.__all__) == 44
    for name in sfa_views.__all__:
        assert hasattr(assets_views, name), f"{name} missing from apps.assets.views"
        assert getattr(assets_views, name) is getattr(sfa_views, name)

    assert "11.17" in LIVE_LINKS
    expected_nav = {
        "Floor Plan & Space Mapping": "assets:asset_facility_space_list",
        "HVAC & Building Systems": "assets:asset_building_system_list",
        "Furniture & Fixture Tracking": "assets:asset_furniture_fixture_list",
        "Infrastructure Asset Management": "assets:asset_infrastructure_board",
        "Tenant & Occupancy Coordination": "assets:asset_space_chargeback_list",
    }
    assert LIVE_LINKS["11.17"] == expected_nav
    for url_name in expected_nav.values():
        assert reverse(url_name)


def test_spacefacility_anonymous_redirects_to_login(
    sfa_space_floor_a,
    sfa_building_system_hvac_a,
    sfa_furniture_a,
    sfa_chargeback_draft_a,
):
    anon = Client()
    get_urls = [
        reverse("assets:overview"),
        reverse("assets:asset_facility_space_list"),
        reverse("assets:asset_facility_space_create"),
        reverse("assets:asset_facility_space_export_csv"),
        reverse("assets:asset_facility_space_detail", args=[sfa_space_floor_a.pk]),
        reverse("assets:asset_facility_space_edit", args=[sfa_space_floor_a.pk]),
        reverse(
            "assets:asset_facility_space_floor_plan_download",
            args=[sfa_space_floor_a.pk],
        ),
        reverse("assets:asset_building_system_list"),
        reverse("assets:asset_building_system_create"),
        reverse("assets:asset_building_system_export_csv"),
        reverse("assets:asset_building_system_detail", args=[sfa_building_system_hvac_a.pk]),
        reverse("assets:asset_building_system_edit", args=[sfa_building_system_hvac_a.pk]),
        reverse("assets:asset_infrastructure_board"),
        reverse("assets:asset_furniture_fixture_list"),
        reverse("assets:asset_furniture_fixture_create"),
        reverse("assets:asset_furniture_fixture_export_csv"),
        reverse("assets:asset_furniture_fixture_detail", args=[sfa_furniture_a.pk]),
        reverse("assets:asset_furniture_fixture_edit", args=[sfa_furniture_a.pk]),
        reverse("assets:asset_space_chargeback_list"),
        reverse("assets:asset_space_chargeback_create"),
        reverse("assets:asset_space_chargeback_export_csv"),
        reverse("assets:asset_space_chargeback_detail", args=[sfa_chargeback_draft_a.pk]),
        reverse("assets:asset_space_chargeback_edit", args=[sfa_chargeback_draft_a.pk]),
    ]
    for url in get_urls:
        resp = anon.get(url)
        assert resp.status_code == 302
        assert "/login" in resp["Location"]

    post_urls = [
        reverse("assets:asset_facility_space_delete", args=[sfa_space_floor_a.pk]),
        reverse(
            "assets:asset_facility_space_recalculate_utilization",
            args=[sfa_space_floor_a.pk],
        ),
        reverse(
            "assets:asset_building_system_evaluate_comfort",
            args=[sfa_building_system_hvac_a.pk],
        ),
        reverse("assets:asset_furniture_fixture_retire", args=[sfa_furniture_a.pk]),
        reverse(
            "assets:asset_space_chargeback_submit_approval",
            args=[sfa_chargeback_draft_a.pk],
        ),
        reverse("assets:asset_space_chargeback_approve", args=[sfa_chargeback_draft_a.pk]),
        reverse("assets:asset_space_chargeback_post_gl", args=[sfa_chargeback_draft_a.pk]),
    ]
    for url in post_urls:
        resp = anon.post(url)
        assert resp.status_code == 302
        assert "/login" in resp["Location"]


# =====================================================================
# 2. Overview Dashboard (11.17 KPIs & Query Budget)
# =====================================================================


def test_spacefacility_overview_kpis_and_query_budget(
    client_a,
    django_assert_max_num_queries,
    sfa_space_building_a,
    sfa_space_floor_a,
    sfa_building_system_hvac_a,
    sfa_building_system_infra_a,
    sfa_furniture_a,
    sfa_chargeback_draft_a,
    sfa_chargeback_approved_a,
):
    sfa_furniture_a.move_status = "move_requested"
    sfa_furniture_a.save(update_fields=["move_status", "updated_at"])

    with django_assert_max_num_queries(34):
        resp = client_a.get(reverse("assets:overview"))

    assert resp.status_code == 200
    _spacefacility_assert_no_template_leaks(resp)
    kpis = resp.context["kpis"]
    assert kpis["total_facility_spaces"] == 2
    assert kpis["active_facility_spaces"] == 2
    assert kpis["total_building_systems"] == 2
    assert kpis["comfort_alert_systems"] == 0
    assert kpis["total_furniture_fixtures"] == 1
    assert kpis["pending_ffe_moves"] == 1
    assert kpis["total_space_chargebacks"] == 2
    assert kpis["posted_space_chargebacks"] == 0

    body = resp.content.decode("utf-8")
    assert "Space Mapping" in body
    assert "HVAC &amp; Systems" in body
    assert "Furniture &amp; IMAC" in body
    assert "Infrastructure Board" in body
    assert "Occupancy Coordination" in body
    assert "2/2 active spaces" in body
    assert "1/1 pending moves" in body


# =====================================================================
# 3. List, Board & Detail Views, Context Keys, Filters, Pagination, I10
# =====================================================================


def test_spacefacility_list_and_board_context_visibility_and_query_budgets(
    client_a,
    django_assert_max_num_queries,
    sfa_space_building_a,
    sfa_space_floor_a,
    sfa_building_system_hvac_a,
    sfa_building_system_infra_a,
    sfa_furniture_a,
    sfa_chargeback_draft_a,
    sfa_chargeback_approved_a,
):
    # 1. Facility Spaces list <= 14 queries
    with django_assert_max_num_queries(14):
        resp_space = client_a.get(reverse("assets:asset_facility_space_list"))
    assert resp_space.status_code == 200
    _spacefacility_assert_no_template_leaks(resp_space)
    for key in (
        "spaces",
        "paginator",
        "page_obj",
        "is_paginated",
        "total_count",
        "active_count",
        "underutilized_count",
        "vacant_count",
        "total_usable_sqft",
        "level_choices",
        "category_choices",
        "occupancy_choices",
        "status_choices",
        "org_units",
        "parent_spaces",
        "search_query",
    ):
        assert key in resp_space.context
    space_html = resp_space.content.decode("utf-8")
    assert sfa_space_building_a.number in space_html
    assert sfa_space_floor_a.code in space_html

    # 2. Building Systems list <= 12 queries
    with django_assert_max_num_queries(12):
        resp_sys = client_a.get(reverse("assets:asset_building_system_list"))
    assert resp_sys.status_code == 200
    _spacefacility_assert_no_template_leaks(resp_sys)
    for key in (
        "systems",
        "paginator",
        "page_obj",
        "is_paginated",
        "total_count",
        "operational_count",
        "comfort_alert_count",
        "overdue_inspection_count",
        "domain_choices",
        "subsystem_choices",
        "comfort_choices",
        "condition_choices",
        "status_choices",
        "spaces",
        "search_query",
    ):
        assert key in resp_sys.context
    sys_html = resp_sys.content.decode("utf-8")
    assert sfa_building_system_hvac_a.number in sys_html
    assert sfa_building_system_infra_a.number in sys_html

    # 3. Infrastructure Board <= 14 queries (excludes hvac_climate)
    with django_assert_max_num_queries(14):
        resp_board = client_a.get(reverse("assets:asset_infrastructure_board"))
    assert resp_board.status_code == 200
    _spacefacility_assert_no_template_leaks(resp_board)
    for key in (
        "systems",
        "paginator",
        "page_obj",
        "is_paginated",
        "total_count",
        "critical_life_safety_count",
        "poor_critical_condition_count",
        "overdue_inspection_count",
        "total_replacement_exposure",
        "domain_choices",
        "condition_choices",
        "criticality_choices",
        "status_choices",
        "spaces",
        "search_query",
        "today",
    ):
        assert key in resp_board.context
    assert all(dom != "hvac_climate" for dom, _ in resp_board.context["domain_choices"])
    board_html = resp_board.content.decode("utf-8")
    assert sfa_building_system_infra_a.number in board_html
    assert sfa_building_system_hvac_a.number not in board_html

    # 4. Furniture & Fixtures list <= 14 queries
    with django_assert_max_num_queries(14):
        resp_ffe = client_a.get(reverse("assets:asset_furniture_fixture_list"))
    assert resp_ffe.status_code == 200
    _spacefacility_assert_no_template_leaks(resp_ffe)
    for key in (
        "fixtures",
        "paginator",
        "page_obj",
        "is_paginated",
        "total_count",
        "pending_move_count",
        "in_place_count",
        "total_quantity",
        "category_choices",
        "condition_choices",
        "move_status_choices",
        "spaces",
        "org_units",
        "search_query",
    ):
        assert key in resp_ffe.context
    assert sfa_furniture_a.number in resp_ffe.content.decode("utf-8")

    # 5. Space Chargebacks list <= 14 queries
    with django_assert_max_num_queries(14):
        resp_cb = client_a.get(reverse("assets:asset_space_chargeback_list"))
    assert resp_cb.status_code == 200
    _spacefacility_assert_no_template_leaks(resp_cb)
    for key in (
        "chargebacks",
        "paginator",
        "page_obj",
        "is_paginated",
        "total_count",
        "approved_count",
        "posted_count",
        "total_net_chargeback",
        "coordination_type_choices",
        "basis_choices",
        "status_choices",
        "spaces",
        "org_units",
        "search_query",
    ):
        assert key in resp_cb.context
    cb_html = resp_cb.content.decode("utf-8")
    assert sfa_chargeback_draft_a.number in cb_html
    assert sfa_chargeback_approved_a.number in cb_html


def test_spacefacility_detail_views_context_and_query_budgets(
    client_a,
    django_assert_max_num_queries,
    sfa_space_floor_a,
    sfa_building_system_hvac_a,
    sfa_furniture_a,
    sfa_chargeback_draft_a,
):
    # Warm session/auth before asserting strict view query budgets
    client_a.get(reverse("assets:asset_facility_space_list"))

    # Space detail executes 5 view queries (main space + 4 child lists) plus
    # auth/tenant/branding SELECTs and 3 session-save queries (SAVEPOINT/UPDATE/RELEASE)
    # = 12 total / <= 10 non-session queries (sibling details stay <= 10 total).
    with CaptureQueriesContext(connection) as ctx, django_assert_max_num_queries(12):
        resp_space = client_a.get(
            reverse("assets:asset_facility_space_detail", args=[sfa_space_floor_a.pk])
        )
    non_session_queries = [
        q["sql"]
        for q in ctx.captured_queries
        if "django_session" not in q["sql"] and not q["sql"].startswith(("SAVEPOINT", "RELEASE SAVEPOINT"))
    ]
    assert len(non_session_queries) <= 10
    assert resp_space.status_code == 200
    _spacefacility_assert_no_template_leaks(resp_space)
    for key in (
        "space",
        "child_spaces",
        "mounted_systems",
        "placed_ffe",
        "active_chargebacks",
        "can_edit",
        "can_delete",
        "can_view_floor_plan_document",
    ):
        assert key in resp_space.context
    assert sfa_space_floor_a.number in resp_space.content.decode("utf-8")

    with django_assert_max_num_queries(10):
        resp_sys = client_a.get(
            reverse(
                "assets:asset_building_system_detail",
                args=[sfa_building_system_hvac_a.pk],
            )
        )
    assert resp_sys.status_code == 200
    _spacefacility_assert_no_template_leaks(resp_sys)
    for key in (
        "system",
        "linked_chargebacks",
        "can_edit",
        "can_delete",
        "can_view_schematic_document",
    ):
        assert key in resp_sys.context
    assert sfa_building_system_hvac_a.number in resp_sys.content.decode("utf-8")

    with django_assert_max_num_queries(10):
        resp_ffe = client_a.get(
            reverse("assets:asset_furniture_fixture_detail", args=[sfa_furniture_a.pk])
        )
    assert resp_ffe.status_code == 200
    _spacefacility_assert_no_template_leaks(resp_ffe)
    for key in ("fixture", "can_edit", "can_delete", "can_complete_move"):
        assert key in resp_ffe.context
    assert sfa_furniture_a.number in resp_ffe.content.decode("utf-8")

    with django_assert_max_num_queries(10):
        resp_cb = client_a.get(
            reverse(
                "assets:asset_space_chargeback_detail",
                args=[sfa_chargeback_draft_a.pk],
            )
        )
    assert resp_cb.status_code == 200
    _spacefacility_assert_no_template_leaks(resp_cb)
    for key in (
        "chargeback",
        "can_edit",
        "can_delete",
        "can_approve",
        "can_post_gl",
        "can_dispute",
    ):
        assert key in resp_cb.context
    assert sfa_chargeback_draft_a.number in resp_cb.content.decode("utf-8")


def test_spacefacility_filters_search_and_junk_params(
    client_a,
    tenant_a,
    org_unit_a,
    sfa_space_building_a,
    sfa_space_floor_a,
    sfa_building_system_hvac_a,
    sfa_building_system_infra_a,
    sfa_furniture_a,
    sfa_chargeback_draft_a,
    sfa_chargeback_approved_a,
):
    # Space filters: space_level, parent FK, org_unit FK, q
    r = client_a.get(
        reverse("assets:asset_facility_space_list"),
        {
            "space_level": "floor",
            "parent": str(sfa_space_building_a.pk),
            "org_unit": str(org_unit_a.pk),
            "q": "Engineering Suite",
        },
    )
    assert r.status_code == 200
    assert [s.pk for s in r.context["spaces"]] == [sfa_space_floor_a.pk]

    # Building system filters: system_domain, facility_space FK, q
    r = client_a.get(
        reverse("assets:asset_building_system_list"),
        {
            "system_domain": "hvac_climate",
            "facility_space": str(sfa_space_floor_a.pk),
            "q": "ASHRAE 90.1",
        },
    )
    assert r.status_code == 200
    assert [s.pk for s in r.context["systems"]] == [sfa_building_system_hvac_a.pk]

    # Infrastructure board: q=load_or_voltage_rating & criticality_tier filter
    extra_infra = _spacefacility_make_system(
        tenant_a,
        sfa_space_building_a,
        name="Standby Generator GEN-2",
        system_domain="backup_generation",
        subsystem_type="generator_set",
        load_or_voltage_rating="1500kW Diesel",
        criticality_tier="tier_2_mission_crit",
    )
    r = client_a.get(
        reverse("assets:asset_infrastructure_board"),
        {"q": "480Y/277V 4000A", "criticality_tier": "tier_1_life_safety"},
    )
    assert r.status_code == 200
    assert [s.pk for s in r.context["systems"]] == [sfa_building_system_infra_a.pk]
    assert extra_infra.pk not in [s.pk for s in r.context["systems"]]

    # FF&E filters: ffe_category, facility_space, assigned_org_unit, q
    r = client_a.get(
        reverse("assets:asset_furniture_fixture_list"),
        {
            "ffe_category": "workstation_desk",
            "facility_space": str(sfa_space_floor_a.pk),
            "assigned_org_unit": str(org_unit_a.pk),
            "q": "SFA-FFE-A01",
        },
    )
    assert r.status_code == 200
    assert [f.pk for f in r.context["fixtures"]] == [sfa_furniture_a.pk]

    # Chargeback filters: coordination_type, status, charged_org_unit, q
    r = client_a.get(
        reverse("assets:asset_space_chargeback_list"),
        {
            "coordination_type": "cam_utility_recovery",
            "status": "approved",
            "charged_org_unit": str(org_unit_a.pk),
            "q": "Switchgear Recovery",
        },
    )
    assert r.status_code == 200
    assert [c.pk for c in r.context["chargebacks"]] == [sfa_chargeback_approved_a.pk]

    # Junk params across all 5 list/board views never 500
    junk_queries = [
        {
            "space_level": "abc",
            "space_category": "invalid",
            "occupancy_status": "xyz",
            "status": "abc",
            "org_unit": "-1",
            "parent": "abc",
            "page": "999",
        },
        {
            "system_domain": "abc",
            "subsystem_type": "abc",
            "comfort_status": "abc",
            "condition_grade": "abc",
            "status": "abc",
            "facility_space": "-1",
            "page": "abc",
        },
        {
            "system_domain": "hvac_climate",
            "criticality_tier": "abc",
            "condition_grade": "abc",
            "status": "abc",
            "facility_space": "abc",
            "page": "999",
        },
        {
            "ffe_category": "abc",
            "condition_grade": "abc",
            "move_status": "abc",
            "facility_space": "-1",
            "assigned_org_unit": "abc",
            "page": "abc",
        },
        {
            "coordination_type": "abc",
            "allocation_basis": "abc",
            "status": "abc",
            "facility_space": "-1",
            "charged_org_unit": "abc",
            "page": "999",
        },
    ]
    url_names = [
        "assets:asset_facility_space_list",
        "assets:asset_building_system_list",
        "assets:asset_infrastructure_board",
        "assets:asset_furniture_fixture_list",
        "assets:asset_space_chargeback_list",
    ]
    for url_name, params in zip(url_names, junk_queries):
        resp = client_a.get(reverse(url_name), params)
        assert resp.status_code == 200


def test_spacefacility_pagination_page_2_across_all_lists_and_board(
    client_a,
    tenant_a,
    sfa_space_building_a,
):
    for i in range(16):
        _spacefacility_make_space(tenant_a, code=f"PG-SP-{i:02d}", name=f"Paged Space {i:02d}")
        _spacefacility_make_system(
            tenant_a,
            sfa_space_building_a,
            name=f"Paged Infra {i:02d}",
            system_domain="electrical_power",
            subsystem_type="switchgear_panel",
        )
        _spacefacility_make_furniture(tenant_a, sfa_space_building_a, name=f"Paged FF&E {i:02d}")
        _spacefacility_make_chargeback(
            tenant_a, sfa_space_building_a, title=f"Paged Chargeback {i:02d}"
        )

    for url_name in (
        "assets:asset_facility_space_list",
        "assets:asset_building_system_list",
        "assets:asset_infrastructure_board",
        "assets:asset_furniture_fixture_list",
        "assets:asset_space_chargeback_list",
    ):
        resp_p1 = client_a.get(reverse(url_name))
        assert resp_p1.status_code == 200
        assert resp_p1.context["is_paginated"] is True
        assert resp_p1.context["page_obj"].number == 1
        assert len(resp_p1.context["page_obj"].object_list) == 15

        resp_p2 = client_a.get(reverse(url_name), {"page": "2"})
        assert resp_p2.status_code == 200
        assert resp_p2.context["page_obj"].number == 2
        assert len(resp_p2.context["page_obj"].object_list) >= 1


def test_spacefacility_building_system_zero_measurements_render_not_dash(
    client_a,
    tenant_a,
    sfa_space_floor_a,
):
    """Regression test for I10: 0.00 measurements render as 0.00, not em-dash."""
    zero_sys = AssetBuildingSystem.objects.create(
        tenant=tenant_a,
        name="Zero-Baseline Freeze Protection AHU",
        system_domain="hvac_climate",
        subsystem_type="ahu_air_handler",
        facility_space=sfa_space_floor_a,
        setpoint_temp_c=Decimal("0.00"),
        measured_temp_c=Decimal("0.00"),
        target_humidity_pct=Decimal("0.00"),
        measured_humidity_pct=Decimal("0.00"),
        served_area_sqft=Decimal("0.00"),
        design_capacity_btu_kw=Decimal("0.00"),
        airflow_cfm=Decimal("0.00"),
        remaining_useful_life_years=0,
        status="operational",
    )

    list_resp = client_a.get(reverse("assets:asset_building_system_list"), {"q": zero_sys.number})
    assert list_resp.status_code == 200
    list_html = list_resp.content.decode("utf-8")
    assert "0.00&deg;C / 0.00&deg;C" in list_html
    assert "—&deg;C" not in list_html

    detail_resp = client_a.get(
        reverse("assets:asset_building_system_detail", args=[zero_sys.pk])
    )
    assert detail_resp.status_code == 200
    detail_html = detail_resp.content.decode("utf-8")
    assert "0.00&deg;C / 0.00&deg;C" in detail_html
    assert "0.00% / 0.00%" in detail_html
    assert "0 yrs" in detail_html
    assert "0.00 sqft / 0.00" in detail_html
    assert "0.00 CFM" in detail_html


# =====================================================================
# 4. CRUD, Prefills & tenant=None Guard (M3)
# =====================================================================


def test_spacefacility_crud_prefills_create_edit_delete_across_all_entities(
    client_a,
    tenant_a,
    sfa_space_floor_a,
):
    # Prefills on child create GETs (?facility_space=)
    for create_url in (
        "assets:asset_building_system_create",
        "assets:asset_furniture_fixture_create",
        "assets:asset_space_chargeback_create",
    ):
        resp_prefill = client_a.get(
            reverse(create_url), {"facility_space": str(sfa_space_floor_a.pk)}
        )
        assert resp_prefill.status_code == 200
        assert resp_prefill.context["form"].initial["facility_space"] == sfa_space_floor_a.pk

    # 1. FacilitySpace CRUD
    resp_sp_create = client_a.post(
        reverse("assets:asset_facility_space_create"),
        data=_spacefacility_space_payload(),
    )
    assert resp_sp_create.status_code == 302
    space = AssetFacilitySpace.objects.get(tenant=tenant_a, code="SFA-RM-301")
    assert resp_sp_create["Location"] == reverse("assets:asset_facility_space_detail", args=[space.pk])
    assert _spacefacility_latest_audit(tenant_a, space, "create") is not None

    resp_sp_edit = client_a.post(
        reverse("assets:asset_facility_space_edit", args=[space.pk]),
        data=_spacefacility_space_payload(name="Engineering Bay 301 Updated"),
    )
    assert resp_sp_edit.status_code == 302
    space.refresh_from_db()
    assert space.name == "Engineering Bay 301 Updated"
    assert _spacefacility_latest_audit(tenant_a, space, "update") is not None

    # 2. BuildingSystem CRUD
    resp_sys_create = client_a.post(
        reverse("assets:asset_building_system_create"),
        data=_spacefacility_system_payload(space),
    )
    assert resp_sys_create.status_code == 302
    system = AssetBuildingSystem.objects.get(tenant=tenant_a, name="Chiller CH-03")
    assert _spacefacility_latest_audit(tenant_a, system, "create") is not None

    resp_sys_edit = client_a.post(
        reverse("assets:asset_building_system_edit", args=[system.pk]),
        data=_spacefacility_system_payload(space, name="Chiller CH-03R"),
    )
    assert resp_sys_edit.status_code == 302
    system.refresh_from_db()
    assert system.name == "Chiller CH-03R"

    resp_sys_del = client_a.post(
        reverse("assets:asset_building_system_delete", args=[system.pk])
    )
    assert resp_sys_del.status_code == 302
    assert not AssetBuildingSystem.objects.filter(pk=system.pk).exists()

    # 3. FurnitureFixture CRUD
    resp_ffe_create = client_a.post(
        reverse("assets:asset_furniture_fixture_create"),
        data=_spacefacility_furniture_payload(space),
    )
    assert resp_ffe_create.status_code == 302
    fixture = AssetFurnitureFixture.objects.get(
        tenant=tenant_a, name="Collaborative Bench Cluster 10"
    )
    assert _spacefacility_latest_audit(tenant_a, fixture, "create") is not None

    resp_ffe_edit = client_a.post(
        reverse("assets:asset_furniture_fixture_edit", args=[fixture.pk]),
        data=_spacefacility_furniture_payload(space, quantity="10"),
    )
    assert resp_ffe_edit.status_code == 302
    fixture.refresh_from_db()
    assert fixture.quantity == 10

    resp_ffe_del = client_a.post(
        reverse("assets:asset_furniture_fixture_delete", args=[fixture.pk])
    )
    assert resp_ffe_del.status_code == 302
    assert not AssetFurnitureFixture.objects.filter(pk=fixture.pk).exists()

    # 4. SpaceChargeback CRUD
    resp_cb_create = client_a.post(
        reverse("assets:asset_space_chargeback_create"),
        data=_spacefacility_chargeback_payload(space),
    )
    assert resp_cb_create.status_code == 302
    chargeback = AssetSpaceChargeback.objects.get(
        tenant=tenant_a, title="Q4 Engineering Wing Allocation"
    )
    assert chargeback.net_chargeback_amount == Decimal("5200.00")
    assert _spacefacility_latest_audit(tenant_a, chargeback, "create") is not None

    resp_cb_edit = client_a.post(
        reverse("assets:asset_space_chargeback_edit", args=[chargeback.pk]),
        data=_spacefacility_chargeback_payload(space, base_cost_amount="4500.00"),
    )
    assert resp_cb_edit.status_code == 302
    chargeback.refresh_from_db()
    assert chargeback.net_chargeback_amount == Decimal("5700.00")

    resp_cb_del = client_a.post(
        reverse("assets:asset_space_chargeback_delete", args=[chargeback.pk])
    )
    assert resp_cb_del.status_code == 302
    assert not AssetSpaceChargeback.objects.filter(pk=chargeback.pk).exists()

    # Delete unlinked space now that children are removed
    resp_sp_del = client_a.post(
        reverse("assets:asset_facility_space_delete", args=[space.pk])
    )
    assert resp_sp_del.status_code == 302
    assert not AssetFacilitySpace.objects.filter(pk=space.pk).exists()


def test_spacefacility_superuser_tenant_none_create_redirects_cleanly(sfa_space_floor_a):
    """M3 regression: tenant=None superuser create GET & POST redirect cleanly without 500."""
    su_client = _spacefacility_superuser_no_tenant_client()
    cases = [
        (
            "assets:asset_facility_space_create",
            "assets:asset_facility_space_list",
            _spacefacility_space_payload(code="SU-NONE-01"),
            AssetFacilitySpace,
        ),
        (
            "assets:asset_building_system_create",
            "assets:asset_building_system_list",
            _spacefacility_system_payload(sfa_space_floor_a),
            AssetBuildingSystem,
        ),
        (
            "assets:asset_furniture_fixture_create",
            "assets:asset_furniture_fixture_list",
            _spacefacility_furniture_payload(sfa_space_floor_a),
            AssetFurnitureFixture,
        ),
        (
            "assets:asset_space_chargeback_create",
            "assets:asset_space_chargeback_list",
            _spacefacility_chargeback_payload(sfa_space_floor_a),
            AssetSpaceChargeback,
        ),
    ]
    for create_url, list_url, payload, model_cls in cases:
        before = model_cls.objects.count()
        get_resp = su_client.get(reverse(create_url))
        assert get_resp.status_code == 302
        assert get_resp["Location"] == reverse(list_url)
        assert "active tenant workspace" in " ".join(_spacefacility_messages(get_resp)).lower()

        post_resp = su_client.post(reverse(create_url), data=payload)
        assert post_resp.status_code == 302
        assert post_resp["Location"] == reverse(list_url)
        assert model_cls.objects.count() == before


# =====================================================================
# 5. Floor Plan Upload, Protected Download & Filename Preservation (M5)
# =====================================================================


def test_spacefacility_floor_plan_upload_download_and_edit_preservation(
    client_a,
    tenant_a,
    settings,
    tmp_path,
):
    settings.MEDIA_ROOT = str(tmp_path)
    png_upload = SimpleUploadedFile(
        "north_tower_level2.png",
        _SPACEFACILITY_SAMPLE_PNG,
        content_type="image/png",
    )
    resp_create = client_a.post(
        reverse("assets:asset_facility_space_create"),
        data=_spacefacility_space_payload(
            code="SFA-FP-01",
            name="Floor Plan Suite",
            floor_plan_image=png_upload,
        ),
    )
    assert resp_create.status_code == 302
    space = AssetFacilitySpace.objects.get(tenant=tenant_a, code="SFA-FP-01")
    assert space.original_floor_plan_name == "north_tower_level2.png"

    dl_resp = client_a.get(
        reverse("assets:asset_facility_space_floor_plan_download", args=[space.pk])
    )
    assert dl_resp.status_code == 200
    assert "attachment" in dl_resp["Content-Disposition"]
    assert "north_tower_level2.png" in dl_resp["Content-Disposition"]
    assert dl_resp["X-Content-Type-Options"] == "nosniff"
    assert b"".join(dl_resp.streaming_content) == _SPACEFACILITY_SAMPLE_PNG

    # Subsequent non-upload edit must preserve original_floor_plan_name (M5)
    resp_edit = client_a.post(
        reverse("assets:asset_facility_space_edit", args=[space.pk]),
        data=_spacefacility_space_payload(
            code="SFA-FP-01",
            name="Floor Plan Suite Revised",
        ),
    )
    assert resp_edit.status_code == 302
    space.refresh_from_db()
    assert space.name == "Floor Plan Suite Revised"
    assert space.original_floor_plan_name == "north_tower_level2.png"

    dl_after = client_a.get(
        reverse("assets:asset_facility_space_floor_plan_download", args=[space.pk])
    )
    assert dl_after.status_code == 200
    assert b"".join(dl_after.streaming_content) == _SPACEFACILITY_SAMPLE_PNG


# =====================================================================
# 6. CSV Exports & Formula-Injection Neutralization
# =====================================================================


def test_spacefacility_csv_exports_and_infra_board_scoping(
    client_a,
    tenant_a,
    sfa_space_building_a,
    sfa_space_floor_a,
    sfa_building_system_hvac_a,
    sfa_building_system_infra_a,
    sfa_furniture_a,
    sfa_chargeback_draft_a,
):
    # Inject a formula-prefixed space name to verify csv_safe neutralization
    formula_space = _spacefacility_make_space(
        tenant_a, code="CSV-SP-01", name="=SUM(A1:A2)"
    )

    export_cases = [
        (
            "assets:asset_facility_space_export_csv",
            {},
            "facility_spaces.csv",
            lambda rows: any(r[2] == "'=SUM(A1:A2)" for r in rows[1:]),
        ),
        (
            "assets:asset_building_system_export_csv",
            {},
            "building_systems.csv",
            lambda rows: {r[0] for r in rows[1:]}
            >= {sfa_building_system_hvac_a.number, sfa_building_system_infra_a.number},
        ),
        (
            "assets:asset_furniture_fixture_export_csv",
            {},
            "asset_furniture_fixtures.csv",
            lambda rows: any(r[0] == sfa_furniture_a.number for r in rows[1:]),
        ),
        (
            "assets:asset_space_chargeback_export_csv",
            {},
            "asset_space_chargebacks.csv",
            lambda rows: any(r[0] == sfa_chargeback_draft_a.number for r in rows[1:]),
        ),
    ]
    for url_name, params, expected_filename, check_fn in export_cases:
        resp = client_a.get(reverse(url_name), params)
        assert resp.status_code == 200
        assert resp["Content-Type"].startswith("text/csv")
        assert f'attachment; filename="{expected_filename}"' == resp["Content-Disposition"]
        assert resp["X-Content-Type-Options"] == "nosniff"
        rows = list(csv.reader(io.StringIO(resp.content.decode("utf-8"))))
        assert len(rows) >= 2
        assert check_fn(rows)

    # Infrastructure Board CSV export: infra_only=1 + criticality_tier + q=load_or_voltage_rating
    extra_infra = _spacefacility_make_system(
        tenant_a,
        formula_space,
        name="Tier 3 Panelboard",
        system_domain="electrical_power",
        subsystem_type="switchgear_panel",
        criticality_tier="tier_3_operational",
        load_or_voltage_rating="208V / 400A",
    )
    board_csv = client_a.get(
        reverse("assets:asset_building_system_export_csv"),
        {
            "infra_only": "1",
            "criticality_tier": "tier_1_life_safety",
            "q": "480Y/277V 4000A",
        },
    )
    assert board_csv.status_code == 200
    assert board_csv["Content-Disposition"] == 'attachment; filename="infrastructure_assets.csv"'
    assert board_csv["X-Content-Type-Options"] == "nosniff"
    board_rows = list(csv.reader(io.StringIO(board_csv.content.decode("utf-8"))))
    exported_numbers = [r[0] for r in board_rows[1:]]
    assert exported_numbers == [sfa_building_system_infra_a.number]
    assert sfa_building_system_hvac_a.number not in exported_numbers
    assert extra_infra.number not in exported_numbers


# =====================================================================
# 7. Lifecycle Workflows & Cross-Module Integrations
# =====================================================================


def test_spacefacility_space_lifecycle_and_locked_guards(
    client_a,
    sfa_member_client_a,
    tenant_a,
    sfa_space_floor_a,
):
    # Recalculate utilization: 10 / 60 = 16.67% -> underutilized
    sfa_space_floor_a.current_headcount = 10
    sfa_space_floor_a.save(update_fields=["current_headcount", "updated_at"])
    resp_recalc = client_a.post(
        reverse(
            "assets:asset_facility_space_recalculate_utilization",
            args=[sfa_space_floor_a.pk],
        )
    )
    assert resp_recalc.status_code == 302
    sfa_space_floor_a.refresh_from_db()
    assert sfa_space_floor_a.occupancy_status == "underutilized"
    assert _spacefacility_latest_audit(tenant_a, sfa_space_floor_a, "recalc") is not None

    # Mark under renovation
    resp_reno = client_a.post(
        reverse(
            "assets:asset_facility_space_mark_under_renovation",
            args=[sfa_space_floor_a.pk],
        )
    )
    assert resp_reno.status_code == 302
    sfa_space_floor_a.refresh_from_db()
    assert sfa_space_floor_a.status == "under_renovation"
    assert sfa_space_floor_a.occupancy_status == "offline"
    assert _spacefacility_latest_audit(tenant_a, sfa_space_floor_a, "renovate") is not None

    # Activate back to active
    resp_act = client_a.post(
        reverse("assets:asset_facility_space_activate", args=[sfa_space_floor_a.pk])
    )
    assert resp_act.status_code == 302
    sfa_space_floor_a.refresh_from_db()
    assert sfa_space_floor_a.status == "active"
    assert _spacefacility_latest_audit(tenant_a, sfa_space_floor_a, "activate") is not None

    # Decommission (admin) -> locks record
    resp_dec = client_a.post(
        reverse(
            "assets:asset_facility_space_decommission",
            args=[sfa_space_floor_a.pk],
        )
    )
    assert resp_dec.status_code == 302
    sfa_space_floor_a.refresh_from_db()
    assert sfa_space_floor_a.status == "decommissioned"
    assert sfa_space_floor_a.is_locked is True
    assert _spacefacility_latest_audit(tenant_a, sfa_space_floor_a, "decomm") is not None

    # Locked space blocks edit GET/POST & recalculate-utilization
    resp_edit_get = client_a.get(
        reverse("assets:asset_facility_space_edit", args=[sfa_space_floor_a.pk])
    )
    assert resp_edit_get.status_code == 302
    resp_edit_post = client_a.post(
        reverse("assets:asset_facility_space_edit", args=[sfa_space_floor_a.pk]),
        data=_spacefacility_space_payload(code=sfa_space_floor_a.code, name="Blocked Edit"),
    )
    assert resp_edit_post.status_code == 302
    sfa_space_floor_a.refresh_from_db()
    assert sfa_space_floor_a.name != "Blocked Edit"

    sfa_space_floor_a.current_headcount = 55
    AssetFacilitySpace.objects.filter(pk=sfa_space_floor_a.pk).update(current_headcount=55)
    resp_recalc_locked = client_a.post(
        reverse(
            "assets:asset_facility_space_recalculate_utilization",
            args=[sfa_space_floor_a.pk],
        )
    )
    assert resp_recalc_locked.status_code == 302
    sfa_space_floor_a.refresh_from_db()
    assert sfa_space_floor_a.occupancy_status == "offline"

    # Non-admin cannot reactivate decommissioned space
    resp_non_admin_act = sfa_member_client_a.post(
        reverse("assets:asset_facility_space_activate", args=[sfa_space_floor_a.pk])
    )
    assert resp_non_admin_act.status_code == 302
    sfa_space_floor_a.refresh_from_db()
    assert sfa_space_floor_a.status == "decommissioned"


def test_spacefacility_building_system_lifecycle_and_locked_guards(
    client_a,
    tenant_a,
    sfa_building_system_hvac_a,
):
    # Evaluate comfort: force out_of_band via query update so evaluate-comfort recomputes it
    AssetBuildingSystem.objects.filter(pk=sfa_building_system_hvac_a.pk).update(
        measured_temp_c=Decimal("26.00")
    )
    resp_comfort = client_a.post(
        reverse(
            "assets:asset_building_system_evaluate_comfort",
            args=[sfa_building_system_hvac_a.pk],
        )
    )
    assert resp_comfort.status_code == 302
    sfa_building_system_hvac_a.refresh_from_db()
    assert sfa_building_system_hvac_a.comfort_status == "out_of_band"
    assert _spacefacility_latest_audit(tenant_a, sfa_building_system_hvac_a, "comfort") is not None

    # Record statutory inspection
    today = timezone.now().date()
    resp_insp = client_a.post(
        reverse(
            "assets:asset_building_system_record_inspection",
            args=[sfa_building_system_hvac_a.pk],
        )
    )
    assert resp_insp.status_code == 302
    sfa_building_system_hvac_a.refresh_from_db()
    assert sfa_building_system_hvac_a.last_statutory_inspection_date == today
    assert sfa_building_system_hvac_a.next_inspection_due_date == today + timedelta(days=365)
    assert _spacefacility_latest_audit(tenant_a, sfa_building_system_hvac_a, "inspect") is not None

    # Flag maintenance -> offline comfort
    resp_maint = client_a.post(
        reverse(
            "assets:asset_building_system_flag_maintenance",
            args=[sfa_building_system_hvac_a.pk],
        )
    )
    assert resp_maint.status_code == 302
    sfa_building_system_hvac_a.refresh_from_db()
    assert sfa_building_system_hvac_a.status == "under_maintenance"
    assert sfa_building_system_hvac_a.comfort_status == "offline"
    assert _spacefacility_latest_audit(tenant_a, sfa_building_system_hvac_a, "maint") is not None

    # Restore operational
    resp_restore = client_a.post(
        reverse(
            "assets:asset_building_system_restore_operational",
            args=[sfa_building_system_hvac_a.pk],
        )
    )
    assert resp_restore.status_code == 302
    sfa_building_system_hvac_a.refresh_from_db()
    assert sfa_building_system_hvac_a.status == "operational"
    assert _spacefacility_latest_audit(tenant_a, sfa_building_system_hvac_a, "restore") is not None

    # Decommission -> locks record
    resp_decomm = client_a.post(
        reverse(
            "assets:asset_building_system_decommission",
            args=[sfa_building_system_hvac_a.pk],
        )
    )
    assert resp_decomm.status_code == 302
    sfa_building_system_hvac_a.refresh_from_db()
    assert sfa_building_system_hvac_a.status == "decommissioned"
    assert sfa_building_system_hvac_a.is_locked is True
    assert _spacefacility_latest_audit(tenant_a, sfa_building_system_hvac_a, "decomm") is not None

    # Locked system rejects edit & evaluate-comfort
    resp_edit_post = client_a.post(
        reverse(
            "assets:asset_building_system_edit",
            args=[sfa_building_system_hvac_a.pk],
        ),
        data=_spacefacility_system_payload(
            sfa_building_system_hvac_a.facility_space, name="Blocked System Edit"
        ),
    )
    assert resp_edit_post.status_code == 302
    sfa_building_system_hvac_a.refresh_from_db()
    assert sfa_building_system_hvac_a.name != "Blocked System Edit"

    AssetBuildingSystem.objects.filter(pk=sfa_building_system_hvac_a.pk).update(
        setpoint_temp_c=Decimal("22.00"), measured_temp_c=Decimal("22.00")
    )
    resp_comfort_locked = client_a.post(
        reverse(
            "assets:asset_building_system_evaluate_comfort",
            args=[sfa_building_system_hvac_a.pk],
        )
    )
    assert resp_comfort_locked.status_code == 302
    sfa_building_system_hvac_a.refresh_from_db()
    assert sfa_building_system_hvac_a.comfort_status == "offline"


def test_spacefacility_furniture_imac_workflow_and_movement_log(
    client_a,
    tenant_a,
    vendor_party_a,
    sfa_space_building_a,
    sfa_space_floor_a,
    sfa_furniture_a,
):
    origin_code = sfa_space_floor_a.code
    dest_code = sfa_space_building_a.code

    sfa_furniture_a.target_space = sfa_space_building_a
    sfa_furniture_a.reconfiguration_batch_ref = "IMAC-2026-Q4-01"
    sfa_furniture_a.save(
        update_fields=["target_space", "reconfiguration_batch_ref", "updated_at"]
    )

    # 1. Request Move
    resp_req = client_a.post(
        reverse(
            "assets:asset_furniture_fixture_request_move",
            args=[sfa_furniture_a.pk],
        )
    )
    assert resp_req.status_code == 302
    sfa_furniture_a.refresh_from_db()
    assert sfa_furniture_a.move_status == "move_requested"
    assert _spacefacility_latest_audit(tenant_a, sfa_furniture_a, "req_move") is not None

    # 2. Schedule Reconfig -> AuditLog.action == "sched_mv" (M4)
    resp_sched = client_a.post(
        reverse(
            "assets:asset_furniture_fixture_schedule_reconfig",
            args=[sfa_furniture_a.pk],
        )
    )
    assert resp_sched.status_code == 302
    sfa_furniture_a.refresh_from_db()
    assert sfa_furniture_a.move_status == "scheduled_reconfig"
    assert _spacefacility_latest_audit(tenant_a, sfa_furniture_a, "sched_mv") is not None

    # 3. Complete Move -> relocates facility_space, clears target_space, creates AssetMovementLog, comp_move
    movement_before = AssetMovementLog.objects.count()
    resp_comp = client_a.post(
        reverse(
            "assets:asset_furniture_fixture_complete_move",
            args=[sfa_furniture_a.pk],
        )
    )
    assert resp_comp.status_code == 302
    sfa_furniture_a.refresh_from_db()
    assert sfa_furniture_a.facility_space_id == sfa_space_building_a.pk
    assert sfa_furniture_a.target_space_id is None
    assert sfa_furniture_a.move_status == "relocated"
    assert sfa_furniture_a.move_completed_at is not None
    assert sfa_furniture_a.custodian_party_id == vendor_party_a.pk
    assert AssetMovementLog.objects.count() == movement_before + 1

    movement = sfa_furniture_a.movement_log
    assert movement is not None
    assert movement.tenant_id == tenant_a.pk
    assert movement.asset_id == sfa_furniture_a.operational_asset_id
    assert movement.movement_type == "room_reassignment"
    assert movement.status == "received"
    assert origin_code in movement.from_room_bin
    assert dest_code in movement.to_room_bin
    assert movement.from_custodian_id == vendor_party_a.pk
    assert movement.to_custodian_id == vendor_party_a.pk
    assert _spacefacility_latest_audit(tenant_a, sfa_furniture_a, "comp_move") is not None

    # 4. Retire -> locks item
    resp_retire = client_a.post(
        reverse("assets:asset_furniture_fixture_retire", args=[sfa_furniture_a.pk])
    )
    assert resp_retire.status_code == 302
    sfa_furniture_a.refresh_from_db()
    assert sfa_furniture_a.move_status == "retired"
    assert sfa_furniture_a.is_locked is True
    assert _spacefacility_latest_audit(tenant_a, sfa_furniture_a, "retire") is not None

    # Retired item blocks edit & delete
    resp_locked_edit = client_a.post(
        reverse("assets:asset_furniture_fixture_edit", args=[sfa_furniture_a.pk]),
        data=_spacefacility_furniture_payload(sfa_space_building_a, name="Blocked FF&E Edit"),
    )
    assert resp_locked_edit.status_code == 302
    sfa_furniture_a.refresh_from_db()
    assert sfa_furniture_a.name != "Blocked FF&E Edit"


def test_spacefacility_chargeback_gl_posting_dispute_and_close_workflows(
    client_a,
    sfa_member_client_a,
    tenant_a,
    admin_user,
    vendor_party_a,
    org_unit_a,
    currency_usd,
    expense_account_a,
    accum_account_a,
    sfa_chargeback_draft_a,
    sfa_chargeback_approved_a,
    integration_closed_fiscal_period_a,
):
    # 1. draft -> submit-approval -> approve -> post-gl
    resp_sub = client_a.post(
        reverse(
            "assets:asset_space_chargeback_submit_approval",
            args=[sfa_chargeback_draft_a.pk],
        )
    )
    assert resp_sub.status_code == 302
    sfa_chargeback_draft_a.refresh_from_db()
    assert sfa_chargeback_draft_a.status == "pending_approval"
    assert _spacefacility_latest_audit(tenant_a, sfa_chargeback_draft_a, "submit") is not None

    resp_app = client_a.post(
        reverse(
            "assets:asset_space_chargeback_approve",
            args=[sfa_chargeback_draft_a.pk],
        )
    )
    assert resp_app.status_code == 302
    sfa_chargeback_draft_a.refresh_from_db()
    assert sfa_chargeback_draft_a.status == "approved"
    assert sfa_chargeback_draft_a.approved_by_id == admin_user.pk
    assert sfa_chargeback_draft_a.approved_at is not None
    assert _spacefacility_latest_audit(tenant_a, sfa_chargeback_draft_a, "approve") is not None

    je_before = JournalEntry.objects.count()
    resp_post = client_a.post(
        reverse(
            "assets:asset_space_chargeback_post_gl",
            args=[sfa_chargeback_draft_a.pk],
        )
    )
    assert resp_post.status_code == 302
    sfa_chargeback_draft_a.refresh_from_db()
    assert sfa_chargeback_draft_a.status == "posted_to_gl"
    assert sfa_chargeback_draft_a.journal_entry is not None
    assert JournalEntry.objects.count() == je_before + 1

    je = sfa_chargeback_draft_a.journal_entry
    assert je.status == "posted"
    assert je.tenant_id == tenant_a.pk
    lines = list(JournalLine.objects.filter(entry=je).order_by("pk"))
    assert len(lines) == 2
    expected_amt = sfa_chargeback_draft_a.net_chargeback_amount
    assert expected_amt == Decimal("6750.00")
    dr_line = next(l for l in lines if l.debit > Decimal("0.00"))
    cr_line = next(l for l in lines if l.credit > Decimal("0.00"))
    assert dr_line.gl_account_id == expense_account_a.pk
    assert dr_line.debit == expected_amt
    assert dr_line.credit == Decimal("0.00")
    assert dr_line.party_id == vendor_party_a.pk
    assert dr_line.org_unit_id == org_unit_a.pk
    assert dr_line.currency_id == currency_usd.pk
    assert cr_line.gl_account_id == accum_account_a.pk
    assert cr_line.credit == expected_amt
    assert cr_line.debit == Decimal("0.00")
    assert _spacefacility_latest_audit(tenant_a, sfa_chargeback_draft_a, "post_gl") is not None

    # Double-post is blocked
    resp_double = client_a.post(
        reverse(
            "assets:asset_space_chargeback_post_gl",
            args=[sfa_chargeback_draft_a.pk],
        )
    )
    assert resp_double.status_code == 302
    assert JournalEntry.objects.count() == je_before + 1
    assert "already posted" in " ".join(_spacefacility_messages(resp_double)).lower()

    # 2. Closed FiscalPeriod blocks GL posting
    sfa_chargeback_approved_a.fiscal_period = integration_closed_fiscal_period_a
    sfa_chargeback_approved_a.save(update_fields=["fiscal_period", "updated_at"])
    resp_closed_fp = client_a.post(
        reverse(
            "assets:asset_space_chargeback_post_gl",
            args=[sfa_chargeback_approved_a.pk],
        )
    )
    assert resp_closed_fp.status_code == 302
    sfa_chargeback_approved_a.refresh_from_db()
    assert sfa_chargeback_approved_a.status == "approved"
    assert sfa_chargeback_approved_a.journal_entry_id is None
    assert JournalEntry.objects.count() == je_before + 1
    assert "must be open" in " ".join(_spacefacility_messages(resp_closed_fp)).lower()

    # 3. Non-admin dispute on approved chargeback -> 403; Admin dispute clears approved_by/approved_at
    resp_member_dispute = sfa_member_client_a.post(
        reverse(
            "assets:asset_space_chargeback_dispute",
            args=[sfa_chargeback_approved_a.pk],
        )
    )
    assert resp_member_dispute.status_code == 403

    resp_admin_dispute = client_a.post(
        reverse(
            "assets:asset_space_chargeback_dispute",
            args=[sfa_chargeback_approved_a.pk],
        )
    )
    assert resp_admin_dispute.status_code == 302
    sfa_chargeback_approved_a.refresh_from_db()
    assert sfa_chargeback_approved_a.status == "disputed"
    assert sfa_chargeback_approved_a.approved_by_id is None
    assert sfa_chargeback_approved_a.approved_at is None
    assert _spacefacility_latest_audit(tenant_a, sfa_chargeback_approved_a, "dispute") is not None

    # Disputed chargeback can be re-submitted for approval
    resp_resubmit = sfa_member_client_a.post(
        reverse(
            "assets:asset_space_chargeback_submit_approval",
            args=[sfa_chargeback_approved_a.pk],
        )
    )
    assert resp_resubmit.status_code == 302
    sfa_chargeback_approved_a.refresh_from_db()
    assert sfa_chargeback_approved_a.status == "pending_approval"

    # 4. Close posted chargeback -> closed & locked
    resp_close = client_a.post(
        reverse(
            "assets:asset_space_chargeback_close",
            args=[sfa_chargeback_draft_a.pk],
        )
    )
    assert resp_close.status_code == 302
    sfa_chargeback_draft_a.refresh_from_db()
    assert sfa_chargeback_draft_a.status == "closed"
    assert sfa_chargeback_draft_a.is_locked is True
    assert _spacefacility_latest_audit(tenant_a, sfa_chargeback_draft_a, "close") is not None

    # Idempotent close & locked edit check
    resp_close_again = client_a.post(
        reverse(
            "assets:asset_space_chargeback_close",
            args=[sfa_chargeback_draft_a.pk],
        )
    )
    assert resp_close_again.status_code == 302
    resp_edit_closed = client_a.get(
        reverse(
            "assets:asset_space_chargeback_edit",
            args=[sfa_chargeback_draft_a.pk],
        )
    )
    assert resp_edit_closed.status_code == 302
