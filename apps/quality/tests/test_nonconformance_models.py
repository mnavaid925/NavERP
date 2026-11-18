"""Unit tests for Sub-module 12.5 Non-Conformance & Deviation Management models."""
from decimal import Decimal
import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.quality.models import (
    NonConformanceReport,
    QuarantineContainment,
    MrbDisposition,
    ProcessDeviation,
)


@pytest.mark.django_db
def test_nonconformance_ncr_model_creation_and_str(ncr_a):
    assert ncr_a.number.startswith("QNCR-")
    assert str(ncr_a) == f"{ncr_a.number} - {ncr_a.title}"
    assert ncr_a.is_closed is False
    assert ncr_a.severity_badge == "badge-amber"
    assert ncr_a.category_badge == "badge-info"
    assert ncr_a.source_type_badge == "badge-info"
    assert ncr_a.status_badge == "badge-info"


@pytest.mark.django_db
def test_nonconformance_ncr_is_closed_states(ncr_a):
    ncr_a.status = "closed"
    ncr_a.save()
    assert ncr_a.is_closed is True

    ncr_a.status = "voided"
    ncr_a.save()
    assert ncr_a.is_closed is True

    ncr_a.status = "under_investigation"
    ncr_a.save()
    assert ncr_a.is_closed is False


@pytest.mark.django_db
def test_nonconformance_ncr_unique_number_per_tenant(tenant_a, ncr_a, admin_user):
    with pytest.raises(IntegrityError):
        NonConformanceReport.objects.create(
            tenant=tenant_a,
            number=ncr_a.number,
            title="Duplicate Number NCR",
            description="Testing duplicate number constraint.",
            source_type="incoming_inspection",
            category="documentation",
            severity="minor",
            status="draft",
            initiator=admin_user,
            owner=admin_user,
            affected_item_code="TEST-DUP",
            quantity_inspected=10,
            quantity_nonconforming=1,
            immediate_containment_required=False,
        )


@pytest.mark.django_db
def test_nonconformance_quarantine_model_creation_and_properties(quarantine_a, ncr_a):
    assert quarantine_a.number.startswith("QCNT-")
    assert str(quarantine_a) == f"{quarantine_a.number} - {quarantine_a.hold_type} ({ncr_a.number})"
    assert quarantine_a.is_active is True
    assert quarantine_a.status_badge == "badge-red"
    assert quarantine_a.hold_type_badge == "badge-red"

    quarantine_a.status = "released"
    quarantine_a.save()
    assert quarantine_a.is_active is False
    assert quarantine_a.status_badge == "badge-green"


@pytest.mark.django_db
def test_nonconformance_mrb_model_creation_and_cost_calculation(mrb_a, ncr_a):
    assert mrb_a.number.startswith("QMRB-")
    assert str(mrb_a) == f"{mrb_a.number} - {mrb_a.disposition_decision} ({ncr_a.number})"
    assert mrb_a.status_badge == "badge-amber"
    assert mrb_a.disposition_decision_badge == "badge-amber"
    assert mrb_a.is_approved is False

    # Cost calculation: 0 scrap + 450 rework + 450 vendor chargeback = 900
    assert mrb_a.total_cost_impact == Decimal("900.00")

    # Update scrap cost and save, verify total recalculates automatically
    mrb_a.scrap_cost = Decimal("250.00")
    mrb_a.save()
    mrb_a.refresh_from_db()
    assert mrb_a.total_cost_impact == Decimal("1150.00")

    # Verify is_approved property
    mrb_a.status = "approved"
    mrb_a.save()
    assert mrb_a.is_approved is True


@pytest.mark.django_db
def test_nonconformance_process_deviation_model_creation_and_status(process_deviation_a, ncr_a):
    assert process_deviation_a.number.startswith("QDEV-")
    assert str(process_deviation_a) == f"{process_deviation_a.number} - {process_deviation_a.title}"
    assert process_deviation_a.status_badge == "badge-slate"
    assert process_deviation_a.deviation_type_badge == "badge-amber"
    assert process_deviation_a.risk_impact_badge == "badge-green"
    assert process_deviation_a.is_active is False

    process_deviation_a.status = "active"
    process_deviation_a.save()
    assert process_deviation_a.is_active is True
    assert process_deviation_a.status_badge == "badge-green"
