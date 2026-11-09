"""Unit and invariant tests for Module 11.5 Maintenance & Repair models."""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.assets.models import (
    AssetMaintenanceRequest,
    AssetMaintenanceSchedule,
    AssetServiceContract,
    AssetMaintenanceLog,
)


@pytest.mark.django_db
def test_asset_maintenance_request_creation_and_numbering(maintenance_request_a):
    assert maintenance_request_a.number.startswith("AMRQ-")
    assert maintenance_request_a.status == "submitted"
    assert maintenance_request_a.status_css == "badge-info"
    assert maintenance_request_a.urgency_css == "badge-amber"
    assert maintenance_request_a.request_type_css == "badge-red"
    assert "AMRQ-" in str(maintenance_request_a)


@pytest.mark.django_db
def test_asset_maintenance_request_triage_transition(maintenance_request_a):
    maintenance_request_a.triage(urgency="critical", triage_notes="Immediate isolation required")
    maintenance_request_a.refresh_from_db()
    assert maintenance_request_a.status == "triaged"
    assert maintenance_request_a.urgency == "critical"
    assert maintenance_request_a.triage_notes == "Immediate isolation required"


@pytest.mark.django_db
def test_asset_maintenance_request_dispatch_transition(maintenance_request_a, admin_user, vendor_party_a, service_contract_a):
    maintenance_request_a.dispatch(
        technician=admin_user,
        vendor=vendor_party_a,
        service_contract=service_contract_a,
    )
    maintenance_request_a.refresh_from_db()
    assert maintenance_request_a.status == "assigned"
    assert maintenance_request_a.assigned_technician == admin_user
    assert maintenance_request_a.assigned_vendor == vendor_party_a
    assert maintenance_request_a.service_contract == service_contract_a


@pytest.mark.django_db
def test_asset_maintenance_request_start_work(maintenance_request_a):
    maintenance_request_a.status = "assigned"
    maintenance_request_a.start_work()
    maintenance_request_a.refresh_from_db()
    assert maintenance_request_a.status == "in_progress"


@pytest.mark.django_db
def test_asset_maintenance_request_resolve_and_close(maintenance_request_a, admin_user):
    maintenance_request_a.status = "in_progress"
    maintenance_request_a.resolve(summary="Replaced drive belt and aligned motor pulleys.", user=admin_user)
    maintenance_request_a.refresh_from_db()
    assert maintenance_request_a.status == "resolved"
    assert maintenance_request_a.resolved_by == admin_user
    assert maintenance_request_a.resolved_at is not None
    assert "Replaced drive belt" in maintenance_request_a.resolution_summary

    maintenance_request_a.close()
    maintenance_request_a.refresh_from_db()
    assert maintenance_request_a.status == "closed"


@pytest.mark.django_db
def test_asset_maintenance_request_reject(maintenance_request_a):
    maintenance_request_a.reject(reason="Duplicate ticket reported by shift operator.")
    maintenance_request_a.refresh_from_db()
    assert maintenance_request_a.status == "rejected"
    assert "Duplicate ticket" in maintenance_request_a.resolution_summary


@pytest.mark.django_db
def test_asset_maintenance_schedule_creation_and_numbering(maintenance_schedule_a):
    assert maintenance_schedule_a.number.startswith("AMSC-")
    assert maintenance_schedule_a.status == "active"
    assert maintenance_schedule_a.is_active is True
    assert maintenance_schedule_a.schedule_type_css == "badge-info"
    assert "AMSC-" in str(maintenance_schedule_a)


@pytest.mark.django_db
def test_asset_maintenance_schedule_recalculate_due_date_time_based(maintenance_schedule_a):
    today = timezone.now().date()
    maintenance_schedule_a.frequency_interval = 2
    maintenance_schedule_a.frequency_unit = "weeks"
    maintenance_schedule_a.recalculate_next_due(from_date=today)
    assert maintenance_schedule_a.next_due_date == today + timedelta(weeks=2)


@pytest.mark.django_db
def test_asset_maintenance_schedule_recalculate_due_date_meter_based(maintenance_schedule_a):
    maintenance_schedule_a.frequency_unit = "runtime_hours"
    maintenance_schedule_a.meter_trigger_threshold = Decimal("250.00")
    maintenance_schedule_a.recalculate_next_due(from_meter=Decimal("1000.00"))
    assert maintenance_schedule_a.next_due_meter == Decimal("1250.00")
    assert maintenance_schedule_a.next_due_date is None


@pytest.mark.django_db
def test_asset_maintenance_schedule_record_completion_advances_date(maintenance_schedule_a):
    today = timezone.now().date()
    maintenance_schedule_a.record_completion(
        completion_date=today,
        completion_meter=Decimal("1200.00"),
        notes="All 3 checklist SOP checks passed cleanly.",
    )
    maintenance_schedule_a.refresh_from_db()
    assert maintenance_schedule_a.last_service_date == today
    assert maintenance_schedule_a.last_service_meter == Decimal("1200.00")
    assert "All 3 checklist SOP checks passed" in maintenance_schedule_a.notes
    assert maintenance_schedule_a.next_due_date > today


@pytest.mark.django_db
def test_asset_maintenance_schedule_checklist_parsing(maintenance_schedule_a):
    items = maintenance_schedule_a.checklist_items()
    assert len(items) == 3
    assert "Clean air filter" in items[0]


@pytest.mark.django_db
def test_asset_maintenance_schedule_activate_and_pause(maintenance_schedule_a):
    maintenance_schedule_a.pause()
    maintenance_schedule_a.refresh_from_db()
    assert maintenance_schedule_a.is_active is False
    assert maintenance_schedule_a.status == "paused"

    maintenance_schedule_a.activate()
    maintenance_schedule_a.refresh_from_db()
    assert maintenance_schedule_a.is_active is True
    assert maintenance_schedule_a.status == "active"


@pytest.mark.django_db
def test_asset_service_contract_creation_and_numbering(service_contract_a):
    assert service_contract_a.number.startswith("ASVC-")
    assert service_contract_a.status == "active"
    assert service_contract_a.contract_type_css == "badge-green"
    assert service_contract_a.remaining_visits == 4
    assert "ASVC-" in str(service_contract_a)


@pytest.mark.django_db
def test_asset_service_contract_status_css_and_expiration(service_contract_a):
    today = timezone.now().date()
    service_contract_a.end_date = today - timedelta(days=1)
    assert service_contract_a.status_css == "badge-red"

    service_contract_a.end_date = today + timedelta(days=15)
    assert service_contract_a.status_css == "badge-amber"


@pytest.mark.django_db
def test_asset_service_contract_record_visit_quota(service_contract_a):
    service_contract_a.record_visit()
    service_contract_a.refresh_from_db()
    assert service_contract_a.pm_visits_completed == 1
    assert service_contract_a.remaining_visits == 3


@pytest.mark.django_db
def test_asset_service_contract_renew_extends_date_and_resets_visits(service_contract_a):
    service_contract_a.pm_visits_completed = 4
    today = timezone.now().date()
    new_expiration = today + timedelta(days=730)
    service_contract_a.renew(
        new_end_date=new_expiration,
        new_contract_value=Decimal("15000.00"),
        notes="Renewed with 5% early renewal discount.",
    )
    service_contract_a.refresh_from_db()
    assert service_contract_a.end_date == new_expiration
    assert service_contract_a.contract_value == Decimal("15000.00")
    assert service_contract_a.pm_visits_completed == 0
    assert "Renewed with 5%" in service_contract_a.notes


@pytest.mark.django_db
def test_asset_service_contract_terminate(service_contract_a):
    service_contract_a.terminate()
    service_contract_a.refresh_from_db()
    assert service_contract_a.status == "terminated"


@pytest.mark.django_db
def test_asset_maintenance_log_creation_and_numbering(maintenance_log_a):
    assert maintenance_log_a.number.startswith("AMLG-")
    assert maintenance_log_a.status == "draft"
    assert maintenance_log_a.maintenance_type_css == "badge-amber"
    assert maintenance_log_a.failure_code_css == "badge-amber"
    assert "AMLG-" in str(maintenance_log_a)


@pytest.mark.django_db
def test_asset_maintenance_log_cost_calculation(maintenance_log_a):
    calculated = maintenance_log_a.calculate_total_cost()
    assert calculated == Decimal("800.00")
    assert maintenance_log_a.total_cost == Decimal("800.00")


@pytest.mark.django_db
def test_asset_maintenance_log_review_approval_flow(maintenance_log_a, admin_user):
    maintenance_log_a.submit_for_review()
    maintenance_log_a.refresh_from_db()
    assert maintenance_log_a.status == "in_review"

    maintenance_log_a.approve(user=admin_user)
    maintenance_log_a.refresh_from_db()
    assert maintenance_log_a.status == "approved"
    assert maintenance_log_a.approved_by == admin_user
    assert maintenance_log_a.approved_at is not None


@pytest.mark.django_db
def test_asset_maintenance_log_post_to_gl_flow(maintenance_log_a, admin_user):
    maintenance_log_a.status = "approved"
    maintenance_log_a.approved_by = admin_user
    maintenance_log_a.post_to_gl(user=admin_user)
    maintenance_log_a.refresh_from_db()
    assert maintenance_log_a.status == "posted"
