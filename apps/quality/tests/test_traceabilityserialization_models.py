"""Model tests for Submodule 12.18 Traceability & Serialization."""
from decimal import Decimal
import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.quality.models import (
    BatchRecord,
    DeviceIdentifier,
    SerializedItem,
    ProductRecall,
    NonConformanceReport,
)


@pytest.mark.django_db
def test_traceabilityserialization_batch_record_creation_and_numbering(tenant_a, admin_user):
    br = BatchRecord.objects.create(
        tenant=tenant_a,
        title="Syringe Assembly Lot 100",
        batch_number="LOT-SYR-100",
        product_code="SYR-100",
        product_name="Disposable Syringe 10ml",
        supervisor=admin_user,
        qa_reviewer=admin_user,
    )
    assert br.number.startswith("QBMR-")
    assert str(br) == f"{br.number} - LOT-SYR-100 (Disposable Syringe 10ml)"


@pytest.mark.django_db
def test_traceabilityserialization_batch_record_can_release_logic(batch_record_a, tenant_a, admin_user):
    # Initial state: checklist_passed is False -> can_release False
    assert not batch_record_a.can_release

    # Pass checklist, no quarantine hold, no open NCR -> can_release True
    batch_record_a.checklist_passed = True
    batch_record_a.is_quarantined = False
    batch_record_a.save()
    assert batch_record_a.can_release

    # If quarantined -> can_release False
    batch_record_a.is_quarantined = True
    batch_record_a.save()
    assert not batch_record_a.can_release
    batch_record_a.is_quarantined = False
    batch_record_a.save()

    # If linked to open NCR -> can_release False
    ncr = NonConformanceReport.objects.create(
        tenant=tenant_a,
        title="Seal defect",
        description="Seal integrity test failed",
        status="under_investigation",
        severity="minor",
        initiator=admin_user,
        owner=admin_user,
    )
    batch_record_a.linked_ncr = ncr
    batch_record_a.save()
    assert not batch_record_a.can_release

    # Once NCR closed -> can_release True
    ncr.status = "closed"
    ncr.save()
    assert batch_record_a.can_release


@pytest.mark.django_db
def test_traceabilityserialization_batch_record_yield_clamping(tenant_a, admin_user):
    br = BatchRecord.objects.create(
        tenant=tenant_a,
        title="High Yield Test",
        batch_number="LOT-YIELD-01",
        product_code="PRD-01",
        product_name="Product",
        planned_quantity=Decimal("10.00"),
        actual_quantity=Decimal("1000.00"),  # 10,000% yield
        supervisor=admin_user,
    )
    assert br.yield_percentage <= Decimal("999.99")


@pytest.mark.django_db
def test_traceabilityserialization_device_identifier_creation(tenant_a, admin_user):
    udi = DeviceIdentifier.objects.create(
        tenant=tenant_a,
        device_name="Digital Sphygmomanometer",
        primary_di="00850012349999",
        issuing_agency="gs1",
        device_class="class_ii",
        brand_name="ApexPressure",
        regulatory_contact=admin_user,
    )
    assert udi.number.startswith("QUDI-")
    assert str(udi) == f"{udi.number} - 00850012349999 (Digital Sphygmomanometer)"


@pytest.mark.django_db
def test_traceabilityserialization_serialized_item_aggregation(tenant_a, batch_record_a, device_identifier_a):
    case = SerializedItem.objects.create(
        tenant=tenant_a,
        serial_number="CASE-SYR-001",
        gtin_or_di="00850012349999",
        item_code="SYR-100",
        item_name="Syringes Master Case",
        lot_number="LOT-SYR-100",
        packaging_level="carton",
        sscc_code="008500123400000099",
        batch_record=batch_record_a,
        device_identifier=device_identifier_a,
    )
    unit = SerializedItem.objects.create(
        tenant=tenant_a,
        serial_number="SN-SYR-1001",
        gtin_or_di="00850012349999",
        item_code="SYR-100",
        item_name="Syringe Unit",
        lot_number="LOT-SYR-100",
        packaging_level="unit",
        parent_container=case,
        batch_record=batch_record_a,
        device_identifier=device_identifier_a,
    )
    assert unit.number.startswith("QSER-")
    assert unit.parent_container == case
    assert case.child_units.count() == 1
    assert case.child_units.first() == unit


@pytest.mark.django_db
def test_traceabilityserialization_product_recall_calculation(tenant_a, admin_user):
    recall = ProductRecall.objects.create(
        tenant=tenant_a,
        title="Defective Battery Recall",
        recall_class="class_i",
        status="initiated",
        item_code="BAT-01",
        item_name="Lithium Battery Pack",
        affected_lot_numbers="LOT-BAT-2026",
        hazard_summary="Overheating hazard",
        total_distributed_qty=1000,
        total_recovered_qty=250,
        coordinator=admin_user,
    )
    assert recall.number.startswith("QRCL-")
    assert recall.recovery_rate_pct == Decimal("25.00")
    assert str(recall) == f"{recall.number} - Defective Battery Recall (Class I — Serious Threat / Death Risk)"


@pytest.mark.django_db
def test_traceabilityserialization_unique_number_per_tenant(tenant_a, tenant_b, admin_user, admin_b):
    br_a = BatchRecord.objects.create(
        tenant=tenant_a,
        title="Batch A",
        batch_number="B-001",
        product_code="P-1",
        product_name="Product 1",
        supervisor=admin_user,
    )
    # Duplicate within same tenant should fail
    with pytest.raises(IntegrityError):
        BatchRecord.objects.create(
            tenant=tenant_a,
            number=br_a.number,
            title="Batch Duplicate",
            batch_number="B-002",
            product_code="P-1",
            product_name="Product 1",
            supervisor=admin_user,
        )
