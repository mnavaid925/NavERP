"""Unit tests for Sub-module 12.5 Non-Conformance & Deviation Management forms."""
from decimal import Decimal
import pytest

from apps.quality.forms import (
    NonConformanceReportForm,
    QuarantineContainmentForm,
    MrbDispositionForm,
    ProcessDeviationForm,
)


@pytest.mark.django_db
def test_nonconformance_ncr_form_valid(tenant_a, admin_user, quality_department, supplier_party_a):
    data = {
        "title": "Out of Spec Packaging Heat Seal",
        "description": "Heat seal temperature dropped below critical 180C threshold.",
        "source_type": "in_process",
        "category": "process",
        "severity": "minor",
        "status": "draft",
        "department": quality_department.pk,
        "initiator": admin_user.pk,
        "owner": admin_user.pk,
        "affected_item_code": "PKG-POUCH-01",
        "quantity_inspected": "100.00",
        "quantity_nonconforming": "5.00",
        "unit_of_measure": "EA",
        "estimated_financial_loss": "120.00",
        "immediate_containment_required": True,
        "supplier_party": supplier_party_a.pk,
    }
    form = NonConformanceReportForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    obj.tenant = tenant_a
    obj.save()
    assert obj.pk is not None
    assert obj.number.startswith("QNCR-")


@pytest.mark.django_db
def test_nonconformance_ncr_form_negative_and_quantity_checks(tenant_a, admin_user):
    data = {
        "title": "Invalid Quantities NCR",
        "description": "Testing quantity bounds.",
        "source_type": "in_process",
        "category": "material",
        "severity": "minor",
        "status": "draft",
        "initiator": admin_user.pk,
        "owner": admin_user.pk,
        "quantity_inspected": "50.00",
        "quantity_nonconforming": "100.00",  # exceeds inspected
        "estimated_financial_loss": "-50.00",  # negative loss
    }
    form = NonConformanceReportForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "quantity_nonconforming" in form.errors
    assert "estimated_financial_loss" in form.errors


@pytest.mark.django_db
def test_nonconformance_quarantine_form_valid(tenant_a, ncr_a, admin_user):
    data = {
        "ncr": ncr_a.pk,
        "title": "Quarantine Cannula Batch Q1",
        "hold_type": "physical_quarantine",
        "quarantine_location": "Secured Cage A",
        "quantity_on_hold": "50.00",
        "unit_of_measure": "EA",
        "hold_date": "2026-11-18",
        "hold_applied_by": admin_user.pk,
        "status": "active",
        "release_criteria": "Engineering re-test pass.",
        "released_quantity": "0.00",
    }
    form = QuarantineContainmentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_nonconformance_quarantine_form_quantity_validation(tenant_a, ncr_a, admin_user):
    data = {
        "ncr": ncr_a.pk,
        "title": "Invalid Quarantine Quantities",
        "hold_type": "physical_quarantine",
        "quarantine_location": "Cage B",
        "quantity_on_hold": "20.00",
        "released_quantity": "30.00",  # exceeds quantity on hold
        "hold_date": "2026-11-18",
        "hold_applied_by": admin_user.pk,
        "status": "active",
    }
    form = QuarantineContainmentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "released_quantity" in form.errors


@pytest.mark.django_db
def test_nonconformance_mrb_form_total_cost_excluded(tenant_a):
    form = MrbDispositionForm(tenant=tenant_a)
    # I6: total_cost_impact must be excluded from form fields
    assert "total_cost_impact" not in form.fields


@pytest.mark.django_db
def test_nonconformance_mrb_form_tripartite_approval_validation(tenant_a, ncr_a, admin_user):
    # I7: approving without all 3 sign-offs must fail
    data = {
        "ncr": ncr_a.pk,
        "title": "Prematurely Approved MRB",
        "disposition_decision": "rework",
        "technical_justification": "Rework feasible.",
        "mrb_chair": admin_user.pk,
        "status": "approved",  # set to approved without QA/Eng/Ops
        "scrap_cost": "0.00",
        "rework_labor_cost": "100.00",
        "vendor_chargeback_cost": "0.00",
    }
    form = MrbDispositionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "quality_approved_by" in form.errors
    assert "engineering_approved_by" in form.errors
    assert "operations_approved_by" in form.errors

    # Now provide all 3 sign-offs
    data["quality_approved_by"] = admin_user.pk
    data["engineering_approved_by"] = admin_user.pk
    data["operations_approved_by"] = admin_user.pk
    form2 = MrbDispositionForm(data=data, tenant=tenant_a)
    assert form2.is_valid(), form2.errors


@pytest.mark.django_db
def test_nonconformance_process_deviation_form_valid(tenant_a, ncr_a, admin_user):
    data = {
        "ncr": ncr_a.pk,
        "title": "Oven Temperature Calibration Offset",
        "deviation_type": "planned",
        "category": "process_parameter",
        "status": "draft",
        "risk_impact_level": "negligible",
        "quality_impact_assessment": "Thermal profile verification confirmed tolerance compliance.",
        "requested_by": admin_user.pk,
        "customer_notification_required": False,
        "max_batches_permitted": 2,
        "batches_produced_count": 0,
    }
    form = ProcessDeviationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
