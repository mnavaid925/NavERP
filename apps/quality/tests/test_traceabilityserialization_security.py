"""Security and tenant isolation tests for Submodule 12.18 Traceability & Serialization."""
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.core.models import AuditLog

User = get_user_model()


@pytest.mark.django_db
def test_traceabilityserialization_unauthenticated_redirect(client, batch_record_a, device_identifier_a, serialized_item_a, product_recall_a):
    urls = [
        reverse("quality:traceability_dashboard"),
        reverse("quality:batch_record_list"),
        reverse("quality:batch_record_detail", kwargs={"pk": batch_record_a.pk}),
        reverse("quality:device_identifier_list"),
        reverse("quality:device_identifier_detail", kwargs={"pk": device_identifier_a.pk}),
        reverse("quality:serialized_item_list"),
        reverse("quality:serialized_item_detail", kwargs={"pk": serialized_item_a.pk}),
        reverse("quality:product_recall_list"),
        reverse("quality:product_recall_detail", kwargs={"pk": product_recall_a.pk}),
        reverse("quality:traceability_export_csv"),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/login/" in resp["Location"]


@pytest.mark.django_db
def test_traceabilityserialization_idor_cross_tenant_isolation(
    client, tenant_a, tenant_b, admin_user, admin_b, batch_record_a, device_identifier_a, serialized_item_a, product_recall_a
):
    # Log in as user of tenant_b and attempt to access tenant_a's objects
    client.force_login(admin_b)

    # 1. BatchRecord
    assert client.get(reverse("quality:batch_record_detail", kwargs={"pk": batch_record_a.pk})).status_code == 404
    assert client.get(reverse("quality:batch_record_edit", kwargs={"pk": batch_record_a.pk})).status_code == 404
    assert client.post(reverse("quality:batch_record_delete", kwargs={"pk": batch_record_a.pk})).status_code == 404
    assert client.post(reverse("quality:batch_record_release", kwargs={"pk": batch_record_a.pk})).status_code == 404

    # 2. DeviceIdentifier
    assert client.get(reverse("quality:device_identifier_detail", kwargs={"pk": device_identifier_a.pk})).status_code == 404
    assert client.get(reverse("quality:device_identifier_edit", kwargs={"pk": device_identifier_a.pk})).status_code == 404
    assert client.post(reverse("quality:device_identifier_delete", kwargs={"pk": device_identifier_a.pk})).status_code == 404

    # 3. SerializedItem
    assert client.get(reverse("quality:serialized_item_detail", kwargs={"pk": serialized_item_a.pk})).status_code == 404
    assert client.get(reverse("quality:serialized_item_edit", kwargs={"pk": serialized_item_a.pk})).status_code == 404
    assert client.post(reverse("quality:serialized_item_delete", kwargs={"pk": serialized_item_a.pk})).status_code == 404

    # 4. ProductRecall
    assert client.get(reverse("quality:product_recall_detail", kwargs={"pk": product_recall_a.pk})).status_code == 404
    assert client.get(reverse("quality:product_recall_edit", kwargs={"pk": product_recall_a.pk})).status_code == 404
    assert client.post(reverse("quality:product_recall_delete", kwargs={"pk": product_recall_a.pk})).status_code == 404


@pytest.mark.django_db
def test_traceabilityserialization_tenant_admin_gate_enforcement(client, tenant_a, batch_record_a, device_identifier_a):
    # Create standard staff user (non-admin)
    staff_user = User.objects.create_user(
        username="standard_staff",
        email="staff@acme.com",
        password="password",
        tenant=tenant_a,
        is_staff=True,
    )
    client.force_login(staff_user)

    # Attempting delete or release actions must return 403 Forbidden
    assert client.post(reverse("quality:batch_record_delete", kwargs={"pk": batch_record_a.pk})).status_code == 403
    assert client.post(reverse("quality:batch_record_release", kwargs={"pk": batch_record_a.pk})).status_code == 403
    assert client.post(reverse("quality:device_identifier_delete", kwargs={"pk": device_identifier_a.pk})).status_code == 403


@pytest.mark.django_db
def test_traceabilityserialization_require_post_on_mutating_actions(client, tenant_a, admin_user, batch_record_a, device_identifier_a):
    client.force_login(admin_user)

    # GET requests on POST-only endpoints must return 405 Method Not Allowed
    assert client.get(reverse("quality:batch_record_delete", kwargs={"pk": batch_record_a.pk})).status_code == 405
    assert client.get(reverse("quality:batch_record_release", kwargs={"pk": batch_record_a.pk})).status_code == 405
    assert client.get(reverse("quality:device_identifier_delete", kwargs={"pk": device_identifier_a.pk})).status_code == 405


@pytest.mark.django_db
def test_traceabilityserialization_audit_logging(client, tenant_a, admin_user, batch_record_a):
    client.force_login(admin_user)

    initial_count = AuditLog.objects.filter(tenant=tenant_a).count()

    # Trigger update
    client.post(
        reverse("quality:batch_record_edit", kwargs={"pk": batch_record_a.pk}),
        {
            "title": "Batch Record for Audit Log Check",
            "batch_number": batch_record_a.batch_number,
            "product_code": batch_record_a.product_code,
            "product_name": batch_record_a.product_name,
            "status": "in_production",
            "planned_quantity": "500.00",
            "actual_quantity": "10.00",
            "unit_of_measure": "EA",
            "supervisor": admin_user.pk,
        },
    )

    new_count = AuditLog.objects.filter(tenant=tenant_a).count()
    assert new_count > initial_count
