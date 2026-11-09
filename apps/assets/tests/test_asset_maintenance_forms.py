"""Unit tests for Module 11.5 Maintenance & Repair forms."""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.assets.forms import (
    AssetMaintenanceRequestForm,
    AssetMaintenanceRequestTriageForm,
    AssetMaintenanceRequestDispatchForm,
    AssetMaintenanceRequestResolveForm,
    AssetMaintenanceRequestRejectForm,
    AssetMaintenanceScheduleForm,
    AssetMaintenanceScheduleCompletionForm,
    AssetServiceContractForm,
    AssetServiceContractRenewForm,
    AssetMaintenanceLogForm,
)


@pytest.mark.django_db
def test_asset_maintenance_request_form_valid(tenant_a, fixed_asset_a, operational_asset_a, admin_user, org_unit_a):
    data = {
        "title": "CNC Coolant Circulation Pressure Low",
        "fixed_asset": str(fixed_asset_a.pk),
        "operational_asset": str(operational_asset_a.pk),
        "requester": str(admin_user.pk),
        "department": str(org_unit_a.pk),
        "request_type": "breakdown_repair",
        "urgency": "medium",
        "is_breakdown": True,
        "downtime_started_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
        "symptom_description": "Coolant pump motor humming without flow.",
    }
    form = AssetMaintenanceRequestForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_asset_maintenance_request_form_rejects_foreign_user(tenant_a, fixed_asset_a, admin_b):
    data = {
        "title": "Unauthorized cross-tenant requester test",
        "fixed_asset": str(fixed_asset_a.pk),
        "requester": str(admin_b.pk),
        "request_type": "facility_upkeep",
        "urgency": "low",
    }
    form = AssetMaintenanceRequestForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "requester" in form.errors


@pytest.mark.django_db
def test_asset_maintenance_request_dispatch_form_valid(tenant_a, admin_user, vendor_party_a, service_contract_a):
    form = AssetMaintenanceRequestDispatchForm(
        tenant_a,
        data={
            "assigned_technician": str(admin_user.pk),
            "assigned_vendor": str(vendor_party_a.pk),
            "service_contract": str(service_contract_a.pk),
        },
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_asset_maintenance_request_triage_form_valid():
    form = AssetMaintenanceRequestTriageForm(
        data={"urgency": "critical", "triage_notes": "Electrical safety hazard - isolate main power."}
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_asset_maintenance_request_resolve_form_valid():
    form = AssetMaintenanceRequestResolveForm(
        data={"resolution_summary": "Replaced fuse #F-102 and recalibrated thermal trip."}
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_asset_maintenance_request_reject_form_valid():
    form = AssetMaintenanceRequestRejectForm(
        data={"rejection_reason": "Not an equipment defect; operator training completed."}
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_asset_maintenance_schedule_form_valid(tenant_a, fixed_asset_a, admin_user, vendor_party_a, service_contract_a):
    data = {
        "name": "Bi-Weekly Air Filter Blowout",
        "schedule_type": "time_based",
        "fixed_asset": str(fixed_asset_a.pk),
        "frequency_interval": 2,
        "frequency_unit": "weeks",
        "start_date": timezone.now().date().strftime("%Y-%m-%d"),
        "lead_time_days": 2,
        "is_mandatory": True,
        "is_active": True,
        "preferred_vendor": str(vendor_party_a.pk),
        "assigned_technician": str(admin_user.pk),
        "service_contract": str(service_contract_a.pk),
        "service_checklist": "1. Power down compressor\n2. Blow out intake filter\n3. Verify differential gauge",
    }
    form = AssetMaintenanceScheduleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_asset_maintenance_schedule_form_rejects_foreign_technician(tenant_a, fixed_asset_a, admin_b):
    data = {
        "name": "Invalid Tech Test",
        "schedule_type": "time_based",
        "fixed_asset": str(fixed_asset_a.pk),
        "frequency_interval": 1,
        "frequency_unit": "months",
        "start_date": timezone.now().date().strftime("%Y-%m-%d"),
        "lead_time_days": 1,
        "assigned_technician": str(admin_b.pk),
    }
    form = AssetMaintenanceScheduleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "assigned_technician" in form.errors


@pytest.mark.django_db
def test_asset_maintenance_schedule_completion_form_valid():
    form = AssetMaintenanceScheduleCompletionForm(
        data={
            "completion_date": timezone.now().date().strftime("%Y-%m-%d"),
            "completion_meter": "1250.50",
            "notes": "PM finished per standard SOP without exceptions.",
        }
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_asset_service_contract_form_valid(tenant_a, vendor_party_a, fixed_asset_a, currency_usd):
    today = timezone.now().date()
    data = {
        "contract_number": "SLA-ACME-2026-X1",
        "title": "Spindle Support SLA",
        "contract_type": "comprehensive_amc",
        "vendor": str(vendor_party_a.pk),
        "fixed_asset": str(fixed_asset_a.pk),
        "start_date": today.strftime("%Y-%m-%d"),
        "end_date": (today + timedelta(days=365)).strftime("%Y-%m-%d"),
        "contract_value": "15000.00",
        "currency": str(currency_usd.pk),
        "billing_frequency": "annual",
        "sla_response_hours": 4,
        "sla_resolution_hours": 24,
        "pm_visits_included": 4,
        "auto_renew": True,
    }
    form = AssetServiceContractForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_asset_service_contract_form_end_date_validation(tenant_a, vendor_party_a, fixed_asset_a, currency_usd):
    today = timezone.now().date()
    data = {
        "contract_number": "SLA-INVALID-DATE",
        "title": "Invalid Date Contract",
        "contract_type": "labor_only",
        "vendor": str(vendor_party_a.pk),
        "fixed_asset": str(fixed_asset_a.pk),
        "start_date": today.strftime("%Y-%m-%d"),
        "end_date": (today - timedelta(days=10)).strftime("%Y-%m-%d"),
        "contract_value": "5000.00",
        "currency": str(currency_usd.pk),
        "billing_frequency": "annual",
        "sla_response_hours": 4,
        "sla_resolution_hours": 24,
        "pm_visits_included": 1,
    }
    form = AssetServiceContractForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "end_date" in form.errors


@pytest.mark.django_db
def test_asset_service_contract_renew_form_valid():
    future_date = (timezone.now().date() + timedelta(days=365)).strftime("%Y-%m-%d")
    form = AssetServiceContractRenewForm(
        data={
            "new_end_date": future_date,
            "new_contract_value": "18000.00",
            "notes": "Annual price escalation applied.",
        }
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_asset_maintenance_log_form_valid(tenant_a, fixed_asset_a, admin_user, vendor_party_a, expense_account_a):
    now = timezone.now()
    data = {
        "maintenance_type": "corrective_repair",
        "service_date": now.date().strftime("%Y-%m-%d"),
        "completion_date": now.strftime("%Y-%m-%dT%H:%M"),
        "fixed_asset": str(fixed_asset_a.pk),
        "lead_technician": str(admin_user.pk),
        "service_vendor": str(vendor_party_a.pk),
        "failure_code": "mechanical_wear",
        "downtime_hours": "3.50",
        "labor_hours": "4.00",
        "labor_cost": "320.00",
        "hourly_labor_rate": "80.00",
        "parts_cost": "150.00",
        "vendor_invoice_cost": "0.00",
        "expense_account": str(expense_account_a.pk),
        "action_taken": "Replaced worn coupler and verified shaft alignment.",
    }
    form = AssetMaintenanceLogForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_asset_maintenance_log_form_rejects_foreign_lead_technician(tenant_a, fixed_asset_a, admin_b):
    now = timezone.now()
    data = {
        "maintenance_type": "inspection",
        "service_date": now.date().strftime("%Y-%m-%d"),
        "fixed_asset": str(fixed_asset_a.pk),
        "lead_technician": str(admin_b.pk),
        "failure_code": "normal_wear",
        "action_taken": "Daily visual inspection completed.",
    }
    form = AssetMaintenanceLogForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "lead_technician" in form.errors
