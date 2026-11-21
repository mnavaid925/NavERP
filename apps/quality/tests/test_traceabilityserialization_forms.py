"""Form tests for Submodule 12.18 Traceability & Serialization."""
from decimal import Decimal
import pytest
from apps.quality.forms.TraceabilitySerialization.BatchRecords import BatchRecordForm
from apps.quality.forms.TraceabilitySerialization.DeviceIdentifiers import DeviceIdentifierForm
from apps.quality.forms.TraceabilitySerialization.SerializedItems import SerializedItemForm
from apps.quality.forms.TraceabilitySerialization.ProductRecalls import ProductRecallForm


@pytest.mark.django_db
def test_traceabilityserialization_batch_record_form_valid(tenant_a, admin_user):
    data = {
        "title": "New Production Run",
        "batch_number": "BATCH-2026-X1",
        "product_code": "PRD-X1",
        "product_name": "Diagnostic Device",
        "status": "draft",
        "planned_quantity": Decimal("100.00"),
        "actual_quantity": Decimal("0.00"),
        "unit_of_measure": "EA",
        "supervisor": admin_user.pk,
    }
    form = BatchRecordForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_traceabilityserialization_batch_record_form_rejects_released_status(tenant_a, admin_user):
    data = {
        "title": "Unauthorized Release Attempt",
        "batch_number": "BATCH-2026-X2",
        "product_code": "PRD-X1",
        "product_name": "Diagnostic Device",
        "status": "released",  # Should be rejected via regular form
        "planned_quantity": Decimal("100.00"),
        "actual_quantity": Decimal("100.00"),
        "unit_of_measure": "EA",
        "supervisor": admin_user.pk,
    }
    form = BatchRecordForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "status" in form.errors
    assert "Batch record cannot be transitioned to 'released' via edit form" in form.errors["status"][0]


@pytest.mark.django_db
def test_traceabilityserialization_batch_record_form_reject_foreign(tenant_a, tenant_b, admin_user, admin_b):
    data = {
        "title": "Cross Tenant Supervisor Test",
        "batch_number": "BATCH-2026-X3",
        "product_code": "PRD-X1",
        "product_name": "Diagnostic Device",
        "status": "draft",
        "planned_quantity": Decimal("100.00"),
        "actual_quantity": Decimal("0.00"),
        "unit_of_measure": "EA",
        "supervisor": admin_b.pk,  # User belonging to tenant_b
    }
    form = BatchRecordForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "supervisor" in form.errors


@pytest.mark.django_db
def test_traceabilityserialization_device_identifier_form_valid(tenant_a, admin_user):
    data = {
        "device_name": "Patient Monitor 2000",
        "primary_di": "00850099887766",
        "issuing_agency": "gs1",
        "device_class": "class_iia",
        "gudid_status": "draft",
        "eudamed_status": "draft",
        "mri_safety_status": "mr_conditional",
        "brand_name": "MonitorPro",
        "commercial_distribution_status": "in_commercial_distribution",
        "barcode_format": "gs1_datamatrix",
        "regulatory_contact": admin_user.pk,
    }
    form = DeviceIdentifierForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_traceabilityserialization_serialized_item_form_reject_self_parent(tenant_a, serialized_item_a):
    data = {
        "serial_number": serialized_item_a.serial_number,
        "gtin_or_di": serialized_item_a.gtin_or_di,
        "item_code": serialized_item_a.item_code,
        "item_name": serialized_item_a.item_name,
        "lot_number": serialized_item_a.lot_number,
        "packaging_level": "unit",
        "commissioning_status": "allocated",
        "epcis_state": "active",
        "parent_container": serialized_item_a.pk,  # Self-parenting
    }
    form = SerializedItemForm(data=data, instance=serialized_item_a, tenant=tenant_a)
    assert not form.is_valid()
    assert "parent_container" in form.errors


@pytest.mark.django_db
def test_traceabilityserialization_product_recall_form_reject_foreign_coordinator(tenant_a, tenant_b, admin_user, admin_b):
    data = {
        "title": "Recall Foreign Coordinator",
        "recall_class": "class_ii",
        "status": "initiated",
        "item_code": "PRD-01",
        "item_name": "Test Device",
        "affected_lot_numbers": "LOT-01",
        "hazard_summary": "Test hazard summary",
        "total_distributed_qty": 100,
        "total_quarantined_qty": 0,
        "total_recovered_qty": 10,
        "total_destroyed_qty": 0,
        "coordinator": admin_b.pk,  # Belongs to tenant_b
    }
    form = ProductRecallForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "coordinator" in form.errors
