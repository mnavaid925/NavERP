"""Unit and validation tests for Module 11.6 Asset Performance & Utilization forms."""
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.assets.forms import (
    AssetDowntimeLogForm,
    AssetDowntimeLogResolveForm,
    AssetOeeRecordForm,
    AssetEnergyReadingForm,
    AssetPerformanceScorecardForm,
)


# ---------------------------------------------------------------------------
# 1. AssetDowntimeLogForm Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_assetperformance_downtime_log_form_valid(tenant_a, fixed_asset_a, operational_asset_a, org_unit_a, admin_user):
    now = timezone.now()
    data = {
        "fixed_asset": str(fixed_asset_a.pk),
        "operational_asset": str(operational_asset_a.pk),
        "department": str(org_unit_a.pk),
        "logged_by": str(admin_user.pk),
        "downtime_category": "unplanned_breakdown",
        "impact_level": "full_shutdown",
        "root_cause_code": "bearing_wear",
        "failure_description": "Spindle overheated and halted under load",
        "started_at": (now - timezone.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
        "ended_at": now.strftime("%Y-%m-%dT%H:%M"),
        "hourly_cost_rate": "150.00",
        "is_mtbf_failure": True,
        "status": "active",
    }
    form = AssetDowntimeLogForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_assetperformance_downtime_log_form_invalid_times(tenant_a, fixed_asset_a, admin_user):
    now = timezone.now()
    data = {
        "fixed_asset": str(fixed_asset_a.pk),
        "logged_by": str(admin_user.pk),
        "downtime_category": "unplanned_breakdown",
        "impact_level": "full_shutdown",
        "failure_description": "Reversed timestamps test",
        "started_at": now.strftime("%Y-%m-%dT%H:%M"),
        "ended_at": (now - timezone.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
    }
    form = AssetDowntimeLogForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "ended_at" in form.errors
    assert "cannot be earlier than start time" in str(form.errors["ended_at"])


@pytest.mark.django_db
def test_assetperformance_downtime_log_form_rejects_foreign_user(tenant_a, fixed_asset_a, admin_b):
    now = timezone.now()
    data = {
        "fixed_asset": str(fixed_asset_a.pk),
        "logged_by": str(admin_b.pk),
        "downtime_category": "unplanned_breakdown",
        "impact_level": "full_shutdown",
        "failure_description": "Cross tenant user injection",
        "started_at": now.strftime("%Y-%m-%dT%H:%M"),
    }
    form = AssetDowntimeLogForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "logged_by" in form.errors


@pytest.mark.django_db
def test_assetperformance_downtime_log_resolve_form_valid():
    now = timezone.now()
    form = AssetDowntimeLogResolveForm(
        data={
            "ended_at": now.strftime("%Y-%m-%dT%H:%M"),
            "hourly_cost_rate": "150.00",
            "resolution_notes": "Flushed lube line, replaced thermal overload breaker, machine restarted.",
        }
    )
    assert form.is_valid(), form.errors


# ---------------------------------------------------------------------------
# 2. AssetOeeRecordForm Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_assetperformance_oee_record_form_valid(tenant_a, fixed_asset_a, operational_asset_a, admin_user):
    data = {
        "fixed_asset": str(fixed_asset_a.pk),
        "operational_asset": str(operational_asset_a.pk),
        "recorded_by": str(admin_user.pk),
        "record_date": timezone.now().date().strftime("%Y-%m-%d"),
        "shift_name": "Day Shift A",
        "planned_production_time_minutes": "480.00",
        "operating_time_minutes": "420.00",
        "ideal_cycle_time_seconds": "30.00",
        "total_units_produced": "800",
        "good_units_produced": "780",
        "defect_units_count": "20",
        "rework_units_count": "5",
        "breakdown_loss_minutes": "30.00",
        "setup_loss_minutes": "30.00",
        "small_stops_loss_minutes": "10.00",
        "reduced_speed_loss_minutes": "10.00",
        "defect_loss_minutes": "10.00",
        "startup_loss_minutes": "5.00",
        "status": "draft",
        "notes": "Optimal shift run with minor tooling adjustment at 11:00",
    }
    form = AssetOeeRecordForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_assetperformance_oee_record_form_operating_exceeds_planned(tenant_a, fixed_asset_a, admin_user):
    data = {
        "fixed_asset": str(fixed_asset_a.pk),
        "recorded_by": str(admin_user.pk),
        "record_date": timezone.now().date().strftime("%Y-%m-%d"),
        "shift_name": "Shift 1",
        "planned_production_time_minutes": "400.00",
        "operating_time_minutes": "500.00",
        "ideal_cycle_time_seconds": "10.00",
        "total_units_produced": "100",
        "good_units_produced": "100",
    }
    form = AssetOeeRecordForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "operating_time_minutes" in form.errors
    assert "cannot exceed planned" in str(form.errors["operating_time_minutes"])


@pytest.mark.django_db
def test_assetperformance_oee_record_form_good_units_exceeds_total(tenant_a, fixed_asset_a, admin_user):
    data = {
        "fixed_asset": str(fixed_asset_a.pk),
        "recorded_by": str(admin_user.pk),
        "record_date": timezone.now().date().strftime("%Y-%m-%d"),
        "shift_name": "Shift 1",
        "planned_production_time_minutes": "480.00",
        "operating_time_minutes": "400.00",
        "ideal_cycle_time_seconds": "10.00",
        "total_units_produced": "100",
        "good_units_produced": "120",
    }
    form = AssetOeeRecordForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "good_units_produced" in form.errors


@pytest.mark.django_db
def test_assetperformance_oee_record_form_rejects_foreign_asset(tenant_a, fixed_asset_b, admin_user):
    data = {
        "fixed_asset": str(fixed_asset_b.pk),
        "recorded_by": str(admin_user.pk),
        "record_date": timezone.now().date().strftime("%Y-%m-%d"),
        "shift_name": "Shift 1",
        "planned_production_time_minutes": "480.00",
        "operating_time_minutes": "400.00",
        "total_units_produced": "100",
        "good_units_produced": "100",
    }
    form = AssetOeeRecordForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "fixed_asset" in form.errors


# ---------------------------------------------------------------------------
# 3. AssetEnergyReadingForm Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_assetperformance_energy_reading_form_valid(tenant_a, fixed_asset_a, operational_asset_a, vendor_party_a, admin_user):
    now = timezone.now()
    data = {
        "fixed_asset": str(fixed_asset_a.pk),
        "operational_asset": str(operational_asset_a.pk),
        "utility_provider": str(vendor_party_a.pk),
        "recorded_by": str(admin_user.pk),
        "reading_timestamp": now.strftime("%Y-%m-%dT%H:%M"),
        "utility_type": "electricity",
        "meter_serial_number": "EM-ACME-0091",
        "consumption_value": "345.5000",
        "unit_of_measure": "kWh",
        "peak_demand_kw": "52.00",
        "power_factor": "0.940",
        "operating_hours": "8.00",
        "units_produced": "120",
        "emission_factor": "0.3850",
        "ghg_scope": "scope_2",
        "cost_per_unit": "0.1500",
        "status": "pending",
    }
    form = AssetEnergyReadingForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_assetperformance_energy_reading_form_invalid_power_factor(tenant_a, fixed_asset_a, admin_user):
    now = timezone.now()
    data = {
        "fixed_asset": str(fixed_asset_a.pk),
        "recorded_by": str(admin_user.pk),
        "reading_timestamp": now.strftime("%Y-%m-%dT%H:%M"),
        "utility_type": "electricity",
        "consumption_value": "100.0000",
        "power_factor": "1.250",  # Invalid > 1.000
    }
    form = AssetEnergyReadingForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "power_factor" in form.errors
    assert "between 0.000 and 1.000" in str(form.errors["power_factor"])


@pytest.mark.django_db
def test_assetperformance_energy_reading_form_rejects_foreign_provider(tenant_a, fixed_asset_a, vendor_party_b, admin_user):
    now = timezone.now()
    data = {
        "fixed_asset": str(fixed_asset_a.pk),
        "utility_provider": str(vendor_party_b.pk),
        "recorded_by": str(admin_user.pk),
        "reading_timestamp": now.strftime("%Y-%m-%dT%H:%M"),
        "utility_type": "natural_gas",
        "consumption_value": "50.0000",
    }
    form = AssetEnergyReadingForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "utility_provider" in form.errors


# ---------------------------------------------------------------------------
# 4. AssetPerformanceScorecardForm Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_assetperformance_scorecard_form_valid(tenant_a, fixed_asset_a, operational_asset_a, org_unit_a, admin_user):
    today = timezone.now().date()
    data = {
        "fixed_asset": str(fixed_asset_a.pk),
        "operational_asset": str(operational_asset_a.pk),
        "department": str(org_unit_a.pk),
        "evaluated_by": str(admin_user.pk),
        "period_type": "monthly",
        "period_start": today.replace(day=1).strftime("%Y-%m-%d"),
        "period_end": today.strftime("%Y-%m-%d"),
        "total_calendar_hours": "720.00",
        "planned_operating_hours": "600.00",
        "actual_operating_hours": "540.00",
        "unplanned_downtime_hours": "40.00",
        "planned_downtime_hours": "20.00",
        "failure_event_count": "2",
        "average_oee_percentage": "88.00",
        "total_energy_consumption_kwh": "12500.00",
        "total_carbon_emissions_kg": "4812.50",
        "total_downtime_cost": "3200.00",
        "status": "draft",
        "executive_summary": "Strong production run exceeding target utilization KPI",
    }
    form = AssetPerformanceScorecardForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    # Verify peer_category_ranking was excluded from form
    assert "peer_category_ranking" not in form.fields


@pytest.mark.django_db
def test_assetperformance_scorecard_form_invalid_dates(tenant_a, fixed_asset_a, admin_user):
    today = timezone.now().date()
    data = {
        "fixed_asset": str(fixed_asset_a.pk),
        "evaluated_by": str(admin_user.pk),
        "period_type": "monthly",
        "period_start": today.strftime("%Y-%m-%d"),
        "period_end": (today - timezone.timedelta(days=10)).strftime("%Y-%m-%d"),
        "total_calendar_hours": "720.00",
    }
    form = AssetPerformanceScorecardForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "period_end" in form.errors
    assert "cannot be earlier than start date" in str(form.errors["period_end"])


@pytest.mark.django_db
def test_assetperformance_scorecard_form_rejects_foreign_department(tenant_a, fixed_asset_a, org_unit_b, admin_user):
    today = timezone.now().date()
    data = {
        "fixed_asset": str(fixed_asset_a.pk),
        "department": str(org_unit_b.pk),
        "evaluated_by": str(admin_user.pk),
        "period_type": "monthly",
        "period_start": today.replace(day=1).strftime("%Y-%m-%d"),
        "period_end": today.strftime("%Y-%m-%d"),
    }
    form = AssetPerformanceScorecardForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "department" in form.errors
