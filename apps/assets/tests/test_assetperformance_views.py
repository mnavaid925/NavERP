"""Functional view and workflow action tests for Module 11.6 Asset Performance & Utilization."""
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import (
    AssetDowntimeLog,
    AssetOeeRecord,
    AssetEnergyReading,
    AssetPerformanceScorecard,
)


# ---------------------------------------------------------------------------
# 1. AssetDowntimeLog View Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_assetperformance_downtime_log_list_view(client, admin_user, downtime_log_a):
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_downtime_log_list"))
    assert resp.status_code == 200
    assert "page_obj" in resp.context
    assert downtime_log_a.number in resp.content.decode()

    # Filter with status and junk parameter
    resp_filter = client.get(reverse("assets:asset_downtime_log_list"), {"status": "active", "q": "bearing"})
    assert resp_filter.status_code == 200
    assert downtime_log_a.number in resp_filter.content.decode()


@pytest.mark.django_db
def test_assetperformance_downtime_log_detail_view(client, admin_user, downtime_log_a):
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_downtime_log_detail", args=[downtime_log_a.pk]))
    assert resp.status_code == 200
    assert resp.context["log"] == downtime_log_a
    assert downtime_log_a.number in resp.content.decode()

    # Verify None-safety when logged_by is None
    downtime_log_a.logged_by = None
    downtime_log_a.save()
    resp_none = client.get(reverse("assets:asset_downtime_log_detail", args=[downtime_log_a.pk]))
    assert resp_none.status_code == 200
    assert "System" in resp_none.content.decode()


@pytest.mark.django_db
def test_assetperformance_downtime_log_create_view(client, admin_user, tenant_a, fixed_asset_a):
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_downtime_log_create"))
    assert resp.status_code == 200

    now = timezone.now()
    data = {
        "fixed_asset": str(fixed_asset_a.pk),
        "downtime_category": "unplanned_breakdown",
        "impact_level": "full_shutdown",
        "failure_description": "Hydraulic seal rupture on main cylinder",
        "started_at": (now - timezone.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
        "hourly_cost_rate": "120.00",
        "status": "active",
    }
    post_resp = client.post(reverse("assets:asset_downtime_log_create"), data=data)
    assert post_resp.status_code == 302
    created = AssetDowntimeLog.objects.filter(tenant=tenant_a, failure_description=data["failure_description"]).first()
    assert created is not None
    assert created.tenant == tenant_a


@pytest.mark.django_db
def test_assetperformance_downtime_log_edit_view(client, admin_user, downtime_log_a):
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_downtime_log_edit", args=[downtime_log_a.pk]))
    assert resp.status_code == 200

    data = {
        "fixed_asset": str(downtime_log_a.fixed_asset.pk),
        "downtime_category": downtime_log_a.downtime_category,
        "impact_level": downtime_log_a.impact_level,
        "failure_description": "Updated failure root cause diagnosis",
        "started_at": downtime_log_a.started_at.strftime("%Y-%m-%dT%H:%M"),
        "hourly_cost_rate": "180.00",
        "status": "active",
    }
    post_resp = client.post(reverse("assets:asset_downtime_log_edit", args=[downtime_log_a.pk]), data=data)
    assert post_resp.status_code == 302
    downtime_log_a.refresh_from_db()
    assert downtime_log_a.failure_description == "Updated failure root cause diagnosis"


@pytest.mark.django_db
def test_assetperformance_downtime_log_resolve_workflow(client, admin_user, downtime_log_a):
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_downtime_log_resolve", args=[downtime_log_a.pk]))
    assert resp.status_code == 200

    now = timezone.now()
    data = {
        "ended_at": now.strftime("%Y-%m-%dT%H:%M"),
        "hourly_cost_rate": "150.00",
        "resolution_notes": "Installed new coupling and verified balance.",
    }
    post_resp = client.post(reverse("assets:asset_downtime_log_resolve", args=[downtime_log_a.pk]), data=data)
    assert post_resp.status_code == 302
    downtime_log_a.refresh_from_db()
    assert downtime_log_a.status == "resolved"
    assert "Installed new coupling" in downtime_log_a.resolution_notes

    # Attempting to resolve a non-active log rejects
    post_retry = client.post(reverse("assets:asset_downtime_log_resolve", args=[downtime_log_a.pk]), data=data)
    assert post_retry.status_code == 302


@pytest.mark.django_db
def test_assetperformance_downtime_log_delete_view(client, admin_user, downtime_log_a):
    client.force_login(admin_user)
    # GET must be rejected with 405 (require_POST)
    get_resp = client.get(reverse("assets:asset_downtime_log_delete", args=[downtime_log_a.pk]))
    assert get_resp.status_code == 405

    # POST deletes
    post_resp = client.post(reverse("assets:asset_downtime_log_delete", args=[downtime_log_a.pk]))
    assert post_resp.status_code == 302
    assert not AssetDowntimeLog.objects.filter(pk=downtime_log_a.pk).exists()


# ---------------------------------------------------------------------------
# 2. AssetOeeRecord View Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_assetperformance_oee_record_list_view(client, admin_user, oee_record_a):
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_oee_record_list"))
    assert resp.status_code == 200
    assert "page_obj" in resp.context
    assert oee_record_a.number in resp.content.decode()


@pytest.mark.django_db
def test_assetperformance_oee_record_detail_view(client, admin_user, oee_record_a):
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_oee_record_detail", args=[oee_record_a.pk]))
    assert resp.status_code == 200
    assert resp.context["record"] == oee_record_a

    # Verify None-safety when recorded_by is None
    oee_record_a.recorded_by = None
    oee_record_a.save()
    resp_none = client.get(reverse("assets:asset_oee_record_detail", args=[oee_record_a.pk]))
    assert resp_none.status_code == 200
    assert "System" in resp_none.content.decode()


@pytest.mark.django_db
def test_assetperformance_oee_record_create_and_edit_views(client, admin_user, tenant_a, fixed_asset_a, oee_record_a):
    client.force_login(admin_user)
    # Create
    create_data = {
        "fixed_asset": str(fixed_asset_a.pk),
        "record_date": timezone.now().date().strftime("%Y-%m-%d"),
        "shift_name": "Shift 1",
        "planned_production_time_minutes": "480.00",
        "operating_time_minutes": "440.00",
        "ideal_cycle_time_seconds": "25.00",
        "total_units_produced": "900",
        "good_units_produced": "880",
        "defect_units_count": "20",
        "rework_units_count": "0",
        "breakdown_loss_minutes": "20.00",
        "setup_loss_minutes": "20.00",
        "small_stops_loss_minutes": "0.00",
        "reduced_speed_loss_minutes": "0.00",
        "defect_loss_minutes": "0.00",
        "startup_loss_minutes": "0.00",
        "status": "draft",
    }
    create_resp = client.post(reverse("assets:asset_oee_record_create"), data=create_data)
    assert create_resp.status_code == 302

    # Edit
    edit_data = dict(create_data)
    edit_data["notes"] = "Updated shift observation"
    edit_resp = client.post(reverse("assets:asset_oee_record_edit", args=[oee_record_a.pk]), data=edit_data)
    assert edit_resp.status_code == 302
    oee_record_a.refresh_from_db()
    assert oee_record_a.notes == "Updated shift observation"


@pytest.mark.django_db
def test_assetperformance_oee_record_finalize_action(client, admin_user, oee_record_a):
    client.force_login(admin_user)
    # Finalize draft
    resp = client.post(reverse("assets:asset_oee_record_finalize", args=[oee_record_a.pk]))
    assert resp.status_code == 302
    oee_record_a.refresh_from_db()
    assert oee_record_a.status == "finalized"

    # Secondary finalize should reject
    resp_again = client.post(reverse("assets:asset_oee_record_finalize", args=[oee_record_a.pk]))
    assert resp_again.status_code == 302


@pytest.mark.django_db
def test_assetperformance_oee_record_delete_view(client, admin_user, oee_record_a):
    client.force_login(admin_user)
    assert client.get(reverse("assets:asset_oee_record_delete", args=[oee_record_a.pk])).status_code == 405
    post_resp = client.post(reverse("assets:asset_oee_record_delete", args=[oee_record_a.pk]))
    assert post_resp.status_code == 302
    assert not AssetOeeRecord.objects.filter(pk=oee_record_a.pk).exists()


# ---------------------------------------------------------------------------
# 3. AssetEnergyReading View Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_assetperformance_energy_reading_list_view(client, admin_user, energy_reading_a):
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_energy_reading_list"))
    assert resp.status_code == 200
    assert "page_obj" in resp.context
    assert energy_reading_a.number in resp.content.decode()


@pytest.mark.django_db
def test_assetperformance_energy_reading_detail_view(client, admin_user, energy_reading_a):
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_energy_reading_detail", args=[energy_reading_a.pk]))
    assert resp.status_code == 200
    assert resp.context["reading"] == energy_reading_a

    # Verify None-safety when recorded_by is None
    energy_reading_a.recorded_by = None
    energy_reading_a.save()
    resp_none = client.get(reverse("assets:asset_energy_reading_detail", args=[energy_reading_a.pk]))
    assert resp_none.status_code == 200
    assert "System Ingestion" in resp_none.content.decode()


@pytest.mark.django_db
def test_assetperformance_energy_reading_create_and_validate(client, admin_user, tenant_a, fixed_asset_a, energy_reading_a):
    client.force_login(admin_user)
    # Create
    create_data = {
        "fixed_asset": str(fixed_asset_a.pk),
        "reading_timestamp": timezone.now().strftime("%Y-%m-%dT%H:%M"),
        "utility_type": "electricity",
        "consumption_value": "450.0000",
        "unit_of_measure": "kWh",
        "peak_demand_kw": "60.00",
        "power_factor": "0.960",
        "operating_hours": "8.00",
        "units_produced": "120",
        "cost_per_unit": "0.1500",
        "emission_factor": "0.3850",
        "ghg_scope": "scope_2",
        "status": "pending",
    }
    create_resp = client.post(reverse("assets:asset_energy_reading_create"), data=create_data)
    assert create_resp.status_code == 302

    # Validate action
    val_resp = client.post(reverse("assets:asset_energy_reading_validate", args=[energy_reading_a.pk]))
    assert val_resp.status_code == 302
    energy_reading_a.refresh_from_db()
    assert energy_reading_a.status == "validated"


@pytest.mark.django_db
def test_assetperformance_energy_reading_delete_view(client, admin_user, energy_reading_a):
    client.force_login(admin_user)
    assert client.get(reverse("assets:asset_energy_reading_delete", args=[energy_reading_a.pk])).status_code == 405
    post_resp = client.post(reverse("assets:asset_energy_reading_delete", args=[energy_reading_a.pk]))
    assert post_resp.status_code == 302
    assert not AssetEnergyReading.objects.filter(pk=energy_reading_a.pk).exists()


# ---------------------------------------------------------------------------
# 4. AssetPerformanceScorecard View Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_assetperformance_scorecard_list_view(client, admin_user, performance_scorecard_a):
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_performance_scorecard_list"))
    assert resp.status_code == 200
    assert "page_obj" in resp.context
    assert performance_scorecard_a.number in resp.content.decode()


@pytest.mark.django_db
def test_assetperformance_scorecard_detail_view(client, admin_user, performance_scorecard_a):
    client.force_login(admin_user)
    resp = client.get(reverse("assets:asset_performance_scorecard_detail", args=[performance_scorecard_a.pk]))
    assert resp.status_code == 200
    assert resp.context["scorecard"] == performance_scorecard_a

    # Verify None-safety when evaluated_by is None
    performance_scorecard_a.evaluated_by = None
    performance_scorecard_a.save()
    resp_none = client.get(reverse("assets:asset_performance_scorecard_detail", args=[performance_scorecard_a.pk]))
    assert resp_none.status_code == 200
    assert "System Evaluator" in resp_none.content.decode()


@pytest.mark.django_db
def test_assetperformance_scorecard_create_and_publish(client, admin_user, tenant_a, fixed_asset_a, performance_scorecard_a):
    client.force_login(admin_user)
    today = timezone.now().date()
    create_data = {
        "fixed_asset": str(fixed_asset_a.pk),
        "period_type": "monthly",
        "period_start": today.replace(day=1).strftime("%Y-%m-%d"),
        "period_end": today.strftime("%Y-%m-%d"),
        "total_calendar_hours": "720.00",
        "planned_operating_hours": "550.00",
        "actual_operating_hours": "500.00",
        "unplanned_downtime_hours": "30.00",
        "planned_downtime_hours": "20.00",
        "failure_event_count": "1",
        "average_oee_percentage": "85.00",
        "total_energy_consumption_kwh": "11000.00",
        "total_carbon_emissions_kg": "4235.00",
        "total_downtime_cost": "2500.00",
        "status": "draft",
    }
    create_resp = client.post(reverse("assets:asset_performance_scorecard_create"), data=create_data)
    assert create_resp.status_code == 302

    # Publish action
    pub_resp = client.post(reverse("assets:asset_performance_scorecard_publish", args=[performance_scorecard_a.pk]))
    assert pub_resp.status_code == 302
    performance_scorecard_a.refresh_from_db()
    assert performance_scorecard_a.status == "published"


@pytest.mark.django_db
def test_assetperformance_scorecard_delete_view(client, admin_user, performance_scorecard_a):
    client.force_login(admin_user)
    assert client.get(reverse("assets:asset_performance_scorecard_delete", args=[performance_scorecard_a.pk])).status_code == 405
    post_resp = client.post(reverse("assets:asset_performance_scorecard_delete", args=[performance_scorecard_a.pk]))
    assert post_resp.status_code == 302
    assert not AssetPerformanceScorecard.objects.filter(pk=performance_scorecard_a.pk).exists()
