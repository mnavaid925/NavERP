"""Unit and invariant tests for Module 11.6 Asset Performance & Utilization models."""
from decimal import Decimal
import pytest
from django.utils import timezone
from django.db import IntegrityError

from apps.assets.models import (
    AssetDowntimeLog,
    AssetOeeRecord,
    AssetEnergyReading,
    AssetPerformanceScorecard,
)


# ---------------------------------------------------------------------------
# 1. AssetDowntimeLog Model Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_assetperformance_downtime_log_numbering_and_str(downtime_log_a):
    assert downtime_log_a.number.startswith("ADWN-")
    assert downtime_log_a.status == "active"
    assert downtime_log_a.status_css == "badge-red"
    assert downtime_log_a.category_css == "badge-red"
    assert downtime_log_a.impact_css == "badge-red"
    assert "ADWN-" in str(downtime_log_a)


@pytest.mark.django_db
def test_assetperformance_downtime_log_calculation_and_resolve(downtime_log_a, admin_user):
    now = timezone.now()
    start = now - timezone.timedelta(hours=2)
    downtime_log_a.started_at = start
    downtime_log_a.ended_at = now
    downtime_log_a.hourly_cost_rate = Decimal("200.00")
    downtime_log_a.calculate_duration_and_cost()
    downtime_log_a.save()
    downtime_log_a.refresh_from_db()

    assert downtime_log_a.duration_minutes == Decimal("120.00")
    assert downtime_log_a.total_downtime_cost == Decimal("400.00")

    # Resolve action
    downtime_log_a.status = "resolved"
    downtime_log_a.resolution_notes = "Replaced damaged seal and recalibrated"
    downtime_log_a.save()
    downtime_log_a.refresh_from_db()

    assert downtime_log_a.status == "resolved"
    assert downtime_log_a.status_css == "badge-green"
    assert downtime_log_a.resolution_notes == "Replaced damaged seal and recalibrated"


@pytest.mark.django_db
def test_assetperformance_downtime_log_cancel(downtime_log_a):
    downtime_log_a.status = "cancelled"
    downtime_log_a.save()
    downtime_log_a.refresh_from_db()
    assert downtime_log_a.status == "cancelled"
    assert downtime_log_a.status_css == "badge-muted"


@pytest.mark.django_db
def test_assetperformance_downtime_log_unique_number(tenant_a, downtime_log_a):
    with pytest.raises(IntegrityError):
        AssetDowntimeLog.objects.create(
            tenant=tenant_a,
            number=downtime_log_a.number,
            downtime_category="unplanned_breakdown",
            impact_level="full_shutdown",
            started_at=timezone.now(),
        )


# ---------------------------------------------------------------------------
# 2. AssetOeeRecord Model Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_assetperformance_oee_record_numbering_and_str(oee_record_a):
    assert oee_record_a.number.startswith("AOEE-")
    assert oee_record_a.status == "draft"
    assert oee_record_a.status_css == "badge-slate"
    assert "AOEE-" in str(oee_record_a)


@pytest.mark.django_db
def test_assetperformance_oee_record_calculations_world_class(oee_record_a):
    # Setup values for world-class tier (>85%)
    oee_record_a.planned_production_time_minutes = Decimal("480.00")
    oee_record_a.operating_time_minutes = Decimal("456.00")  # Availability = 95.0%
    oee_record_a.ideal_cycle_time_seconds = Decimal("20.00")
    oee_record_a.total_units_produced = 1300                 # Performance = (1300*20)/(456*60) = 26000/27360 = 95.03%
    oee_record_a.good_units_produced = 1280                  # Quality = 1280/1300 = 98.46%
    oee_record_a.defect_units_count = 20
    oee_record_a.calculate_oee()
    oee_record_a.save()
    oee_record_a.refresh_from_db()

    assert oee_record_a.availability_percentage == Decimal("95.00")
    assert oee_record_a.performance_percentage == Decimal("95.03")
    assert oee_record_a.quality_percentage == Decimal("98.46")
    assert oee_record_a.oee_percentage >= Decimal("85.00")
    assert oee_record_a.benchmark_tier == "world_class"
    assert oee_record_a.tier_css == "badge-green"


@pytest.mark.django_db
def test_assetperformance_oee_record_finalize_and_cancel(oee_record_a):
    oee_record_a.status = "finalized"
    oee_record_a.save()
    oee_record_a.refresh_from_db()
    assert oee_record_a.status == "finalized"
    assert oee_record_a.status_css == "badge-green"

    oee_record_a.status = "cancelled"
    oee_record_a.save()
    oee_record_a.refresh_from_db()
    assert oee_record_a.status == "cancelled"


# ---------------------------------------------------------------------------
# 3. AssetEnergyReading Model Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_assetperformance_energy_reading_numbering_and_str(energy_reading_a):
    assert energy_reading_a.number.startswith("AENG-")
    assert energy_reading_a.status == "pending"
    assert energy_reading_a.status_css == "badge-slate"
    assert energy_reading_a.utility_css == "badge-info"
    assert energy_reading_a.scope_css == "badge-info"
    assert "AENG-" in str(energy_reading_a)


@pytest.mark.django_db
def test_assetperformance_energy_reading_calculations(energy_reading_a):
    energy_reading_a.consumption_value = Decimal("500.0000")
    energy_reading_a.cost_per_unit = Decimal("0.2000")
    energy_reading_a.emission_factor = Decimal("0.4000")
    energy_reading_a.operating_hours = Decimal("10.00")
    energy_reading_a.units_produced = 250
    energy_reading_a.calculate_energy_metrics()
    energy_reading_a.save()
    energy_reading_a.refresh_from_db()

    assert energy_reading_a.total_energy_cost == Decimal("100.00")
    assert energy_reading_a.carbon_emissions_kg_co2e == Decimal("200.00")
    assert energy_reading_a.energy_intensity_per_hour == Decimal("50.0000")
    assert energy_reading_a.energy_intensity_per_unit == Decimal("2.0000")


@pytest.mark.django_db
def test_assetperformance_energy_reading_lifecycle_transitions(energy_reading_a):
    energy_reading_a.status = "flagged_anomaly"
    energy_reading_a.save()
    energy_reading_a.refresh_from_db()
    assert energy_reading_a.status == "flagged_anomaly"
    assert energy_reading_a.status_css == "badge-red"

    energy_reading_a.status = "validated"
    energy_reading_a.save()
    energy_reading_a.refresh_from_db()
    assert energy_reading_a.status == "validated"
    assert energy_reading_a.status_css == "badge-green"

    energy_reading_a.status = "cancelled"
    energy_reading_a.save()
    energy_reading_a.refresh_from_db()
    assert energy_reading_a.status == "cancelled"


# ---------------------------------------------------------------------------
# 4. AssetPerformanceScorecard Model Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_assetperformance_scorecard_numbering_and_str(performance_scorecard_a):
    assert performance_scorecard_a.number.startswith("APSC-")
    assert performance_scorecard_a.status == "draft"
    assert performance_scorecard_a.status_css == "badge-slate"
    assert performance_scorecard_a.period_css == "badge-info"
    assert performance_scorecard_a.grade_css == "badge-green"
    assert "APSC-" in str(performance_scorecard_a)


@pytest.mark.django_db
def test_assetperformance_scorecard_calculation(performance_scorecard_a):
    performance_scorecard_a.total_calendar_hours = Decimal("720.00")
    performance_scorecard_a.planned_operating_hours = Decimal("600.00")
    performance_scorecard_a.actual_operating_hours = Decimal("540.00")
    performance_scorecard_a.unplanned_downtime_hours = Decimal("40.00")
    performance_scorecard_a.planned_downtime_hours = Decimal("20.00")
    performance_scorecard_a.failure_event_count = 2
    performance_scorecard_a.average_oee_percentage = Decimal("88.00")
    performance_scorecard_a.calculate_scorecard()
    performance_scorecard_a.save()
    performance_scorecard_a.refresh_from_db()

    # Utilization = (540 / 600) * 100 = 90.00%
    assert performance_scorecard_a.capacity_utilization_rate == Decimal("90.00")
    # Availability = (540 / (540 + 40)) * 100 = 93.10%
    assert performance_scorecard_a.availability_rate == Decimal("93.10")
    # MTBF = 540 / 2 = 270.00 hours
    assert performance_scorecard_a.mtbf_hours == Decimal("270.00")
    # MTTR = 40 / 2 = 20.00 hours
    assert performance_scorecard_a.mttr_hours == Decimal("20.00")
    assert performance_scorecard_a.benchmark_grade in ("grade_a", "grade_b", "grade_c", "grade_d")


@pytest.mark.django_db
def test_assetperformance_scorecard_publish_and_archive(performance_scorecard_a):
    performance_scorecard_a.status = "published"
    performance_scorecard_a.save()
    performance_scorecard_a.refresh_from_db()
    assert performance_scorecard_a.status == "published"
    assert performance_scorecard_a.status_css == "badge-green"

    performance_scorecard_a.status = "archived"
    performance_scorecard_a.save()
    performance_scorecard_a.refresh_from_db()
    assert performance_scorecard_a.status == "archived"
    assert performance_scorecard_a.status_css == "badge-muted"
