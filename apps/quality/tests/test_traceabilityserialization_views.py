"""View tests for Submodule 12.18 Traceability & Serialization."""
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.quality.models import (
    BatchRecord,
    DeviceIdentifier,
    SerializedItem,
    ProductRecall,
    CustomerComplaint,
    CapaInvestigation,
)


@pytest.mark.django_db
def test_traceabilityserialization_dashboard_view(client, tenant_a, admin_user, batch_record_a, serialized_item_a, product_recall_a):
    client.force_login(admin_user)
    url = reverse("quality:traceability_dashboard")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "total_batches" in resp.context
    assert resp.context["total_batches"] >= 1
    assert "total_serialized" in resp.context
    assert resp.context["total_serialized"] >= 1
    assert "active_recalls" in resp.context


@pytest.mark.django_db
def test_traceabilityserialization_export_csv(client, tenant_a, admin_user, serialized_item_a):
    client.force_login(admin_user)
    url = reverse("quality:traceability_export_csv")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert "attachment; filename=" in resp["Content-Disposition"]
    content = resp.content.decode("utf-8")
    assert "Serial Number,GTIN / DI,Item Code,Item Name,Lot Number" in content
    assert serialized_item_a.serial_number in content


@pytest.mark.django_db
def test_traceabilityserialization_batch_record_views(client, tenant_a, admin_user, batch_record_a):
    client.force_login(admin_user)

    # 1. List
    list_url = reverse("quality:batch_record_list")
    resp = client.get(list_url)
    assert resp.status_code == 200
    assert batch_record_a.batch_number in resp.content.decode("utf-8")

    # Filter by status
    resp = client.get(list_url, {"status": "draft"})
    assert resp.status_code == 200

    # 2. Detail
    detail_url = reverse("quality:batch_record_detail", kwargs={"pk": batch_record_a.pk})
    resp = client.get(detail_url)
    assert resp.status_code == 200
    assert batch_record_a.number in resp.content.decode("utf-8")

    # 3. Create
    create_url = reverse("quality:batch_record_create")
    resp = client.post(
        create_url,
        {
            "title": "Created Batch Run",
            "batch_number": "BATCH-NEW-99",
            "product_code": "PRD-99",
            "product_name": "New Product",
            "status": "draft",
            "planned_quantity": "250.00",
            "actual_quantity": "0.00",
            "unit_of_measure": "EA",
            "supervisor": admin_user.pk,
        },
    )
    assert resp.status_code == 302
    assert BatchRecord.objects.filter(tenant=tenant_a, batch_number="BATCH-NEW-99").exists()

    # 4. Edit
    edit_url = reverse("quality:batch_record_edit", kwargs={"pk": batch_record_a.pk})
    resp = client.post(
        edit_url,
        {
            "title": "Updated Title Batch",
            "batch_number": batch_record_a.batch_number,
            "product_code": batch_record_a.product_code,
            "product_name": batch_record_a.product_name,
            "status": "in_production",
            "planned_quantity": str(batch_record_a.planned_quantity),
            "actual_quantity": "50.00",
            "unit_of_measure": batch_record_a.unit_of_measure,
            "supervisor": admin_user.pk,
        },
    )
    assert resp.status_code == 302
    batch_record_a.refresh_from_db()
    assert batch_record_a.status == "in_production"

    # 5. Release Workflow Action
    release_url = reverse("quality:batch_record_release", kwargs={"pk": batch_record_a.pk})
    # Cannot release because checklist_passed is False
    resp = client.post(release_url)
    assert resp.status_code == 302
    batch_record_a.refresh_from_db()
    assert batch_record_a.status != "released"

    # Now make it releasable
    batch_record_a.checklist_passed = True
    batch_record_a.is_quarantined = False
    batch_record_a.save()
    resp = client.post(release_url)
    assert resp.status_code == 302
    batch_record_a.refresh_from_db()
    assert batch_record_a.status == "released"
    assert batch_record_a.release_status == "approved_full"

    # 6. Delete guard (cannot delete released record)
    delete_url = reverse("quality:batch_record_delete", kwargs={"pk": batch_record_a.pk})
    resp = client.post(delete_url)
    assert resp.status_code == 302
    assert BatchRecord.objects.filter(pk=batch_record_a.pk).exists()  # Kept alive!


@pytest.mark.django_db
def test_traceabilityserialization_device_identifier_views(client, tenant_a, admin_user, device_identifier_a):
    client.force_login(admin_user)

    # 1. List
    list_url = reverse("quality:device_identifier_list")
    resp = client.get(list_url)
    assert resp.status_code == 200
    assert device_identifier_a.primary_di in resp.content.decode("utf-8")

    # 2. Detail
    detail_url = reverse("quality:device_identifier_detail", kwargs={"pk": device_identifier_a.pk})
    resp = client.get(detail_url)
    assert resp.status_code == 200

    # 3. Create
    create_url = reverse("quality:device_identifier_create")
    resp = client.post(
        create_url,
        {
            "device_name": "Infusion Tubing Set",
            "primary_di": "00850077778888",
            "issuing_agency": "gs1",
            "device_class": "class_iia",
            "gudid_status": "draft",
            "eudamed_status": "draft",
            "mri_safety_status": "mr_safe",
            "brand_name": "InfuseLine",
            "commercial_distribution_status": "in_commercial_distribution",
            "barcode_format": "gs1_datamatrix",
            "regulatory_contact": admin_user.pk,
        },
    )
    assert resp.status_code == 302
    assert DeviceIdentifier.objects.filter(tenant=tenant_a, primary_di="00850077778888").exists()


@pytest.mark.django_db
def test_traceabilityserialization_serialized_item_views(client, tenant_a, admin_user, serialized_item_a, batch_record_a, device_identifier_a):
    client.force_login(admin_user)

    # 1. List
    list_url = reverse("quality:serialized_item_list")
    resp = client.get(list_url)
    assert resp.status_code == 200

    # 2. Detail
    detail_url = reverse("quality:serialized_item_detail", kwargs={"pk": serialized_item_a.pk})
    resp = client.get(detail_url)
    assert resp.status_code == 200
    assert serialized_item_a.serial_number in resp.content.decode("utf-8")

    # 3. Create with commissioning status transitions
    create_url = reverse("quality:serialized_item_create")
    resp = client.post(
        create_url,
        {
            "serial_number": "SN-NEW-9001",
            "gtin_or_di": "00850012349999",
            "item_code": "SYR-100",
            "item_name": "Disposable Syringe 10ml",
            "lot_number": "LOT-SYR-100",
            "packaging_level": "unit",
            "commissioning_status": "commissioned",  # Triggers commissioned_at stamp
            "epcis_state": "active",
            "batch_record": batch_record_a.pk,
            "device_identifier": device_identifier_a.pk,
        },
    )
    assert resp.status_code == 302
    new_ser = SerializedItem.objects.get(tenant=tenant_a, serial_number="SN-NEW-9001")
    assert new_ser.commissioned_at is not None


@pytest.mark.django_db
def test_traceabilityserialization_product_recall_detail_with_linked_records(
    client, tenant_a, admin_user, product_recall_a, customer_complaint_a, capa_investigation_a
):
    client.force_login(admin_user)

    # Link CustomerComplaint and CapaInvestigation to test C1 and C2 fixes
    product_recall_a.customer_complaint = customer_complaint_a
    product_recall_a.capa_investigation = capa_investigation_a
    product_recall_a.save()

    url = reverse("quality:product_recall_detail", kwargs={"pk": product_recall_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    content = resp.content.decode("utf-8")
    assert customer_complaint_a.number in content
    assert capa_investigation_a.number in content
