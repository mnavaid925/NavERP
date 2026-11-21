import pytest
from django.urls import reverse
from apps.core.models import AuditLog
from apps.quality.models import RegulatorySubmission


@pytest.mark.django_db
def test_regulatorycompliance_unauthenticated_redirects(client, regulatory_submission_a, product_registration_a, regulatory_commitment_a, post_market_surveillance_report_a):
    endpoints = [
        reverse("quality:regulatory_dashboard"),
        reverse("quality:regulatory_submission_list"),
        reverse("quality:regulatory_submission_create"),
        reverse("quality:regulatory_submission_detail", kwargs={"pk": regulatory_submission_a.pk}),
        reverse("quality:regulatory_submission_edit", kwargs={"pk": regulatory_submission_a.pk}),
        reverse("quality:regulatory_submission_export"),
        reverse("quality:product_registration_list"),
        reverse("quality:product_registration_create"),
        reverse("quality:product_registration_detail", kwargs={"pk": product_registration_a.pk}),
        reverse("quality:product_registration_edit", kwargs={"pk": product_registration_a.pk}),
        reverse("quality:product_registration_export"),
        reverse("quality:regulatory_commitment_list"),
        reverse("quality:regulatory_commitment_create"),
        reverse("quality:regulatory_commitment_detail", kwargs={"pk": regulatory_commitment_a.pk}),
        reverse("quality:regulatory_commitment_edit", kwargs={"pk": regulatory_commitment_a.pk}),
        reverse("quality:regulatory_commitment_export"),
        reverse("quality:post_market_surveillance_report_list"),
        reverse("quality:post_market_surveillance_report_create"),
        reverse("quality:post_market_surveillance_report_detail", kwargs={"pk": post_market_surveillance_report_a.pk}),
        reverse("quality:post_market_surveillance_report_edit", kwargs={"pk": post_market_surveillance_report_a.pk}),
        reverse("quality:post_market_surveillance_report_export"),
    ]
    for url in endpoints:
        res = client.get(url)
        assert res.status_code == 302
        assert "/accounts/login/" in res.url or "/login/" in res.url


@pytest.mark.django_db
def test_regulatorycompliance_idor_cross_tenant_isolation(client, admin_user, regulatory_submission_b, product_registration_b, regulatory_commitment_b, post_market_surveillance_report_b):
    # Logged in as admin_user (tenant_a), attempting to view/edit tenant_b records
    client.force_login(admin_user)

    res = client.get(reverse("quality:regulatory_submission_detail", kwargs={"pk": regulatory_submission_b.pk}))
    assert res.status_code == 404

    res = client.get(reverse("quality:regulatory_submission_edit", kwargs={"pk": regulatory_submission_b.pk}))
    assert res.status_code == 404

    res = client.post(reverse("quality:regulatory_submission_delete", kwargs={"pk": regulatory_submission_b.pk}))
    assert res.status_code == 404

    res = client.get(reverse("quality:product_registration_detail", kwargs={"pk": product_registration_b.pk}))
    assert res.status_code == 404

    res = client.get(reverse("quality:product_registration_edit", kwargs={"pk": product_registration_b.pk}))
    assert res.status_code == 404

    res = client.post(reverse("quality:product_registration_delete", kwargs={"pk": product_registration_b.pk}))
    assert res.status_code == 404

    res = client.get(reverse("quality:regulatory_commitment_detail", kwargs={"pk": regulatory_commitment_b.pk}))
    assert res.status_code == 404

    res = client.get(reverse("quality:regulatory_commitment_edit", kwargs={"pk": regulatory_commitment_b.pk}))
    assert res.status_code == 404

    res = client.post(reverse("quality:regulatory_commitment_delete", kwargs={"pk": regulatory_commitment_b.pk}))
    assert res.status_code == 404

    res = client.get(reverse("quality:post_market_surveillance_report_detail", kwargs={"pk": post_market_surveillance_report_b.pk}))
    assert res.status_code == 404

    res = client.get(reverse("quality:post_market_surveillance_report_edit", kwargs={"pk": post_market_surveillance_report_b.pk}))
    assert res.status_code == 404

    res = client.post(reverse("quality:post_market_surveillance_report_delete", kwargs={"pk": post_market_surveillance_report_b.pk}))
    assert res.status_code == 404


@pytest.mark.django_db
def test_regulatorycompliance_post_only_deletions(client, admin_user, regulatory_submission_a, product_registration_a, regulatory_commitment_a, post_market_surveillance_report_a):
    client.force_login(admin_user)

    res = client.get(reverse("quality:regulatory_submission_delete", kwargs={"pk": regulatory_submission_a.pk}))
    assert res.status_code == 405

    res = client.get(reverse("quality:product_registration_delete", kwargs={"pk": product_registration_a.pk}))
    assert res.status_code == 405

    res = client.get(reverse("quality:regulatory_commitment_delete", kwargs={"pk": regulatory_commitment_a.pk}))
    assert res.status_code == 405

    res = client.get(reverse("quality:post_market_surveillance_report_delete", kwargs={"pk": post_market_surveillance_report_a.pk}))
    assert res.status_code == 405


@pytest.mark.django_db
def test_regulatorycompliance_csv_formula_injection_defense(client, admin_user, tenant_a):
    client.force_login(admin_user)

    # Create submission with formula payload
    from apps.quality.models import RegulatorySubmission
    sub = RegulatorySubmission.objects.create(
        tenant=tenant_a,
        title="=SUM(A1:A10)",
        product_name="@CMD|'/C calc'!A0",
        submission_type="510k",
    )

    res = client.get(reverse("quality:regulatory_submission_export"))
    assert res.status_code == 200
    content = res.content.decode()
    # The formula payload must be sanitized with a single-quote prefix
    assert "'=SUM(A1:A10)" in content
    assert "'@CMD|'/C calc'!A0" in content


@pytest.mark.django_db
def test_regulatorycompliance_audit_logging(client, admin_user, tenant_a, regulatory_submission_a):
    client.force_login(admin_user)

    initial_audit_count = AuditLog.objects.filter(tenant=tenant_a).count()

    # Create action
    res = client.post(reverse("quality:regulatory_submission_create"), data={
        "title": "Audit Test Submission",
        "product_name": "Audit Device",
        "submission_type": "510k",
        "device_class": "class_iib",
        "status": "draft",
    })
    assert res.status_code == 302
    assert AuditLog.objects.filter(tenant=tenant_a, action="create").count() > 0

    # Export action
    res = client.get(reverse("quality:regulatory_submission_export"))
    assert res.status_code == 200
    assert AuditLog.objects.filter(tenant=tenant_a, action="export").count() > 0

    # Delete action
    sub_to_delete = RegulatorySubmission.objects.filter(tenant=tenant_a, title="Audit Test Submission").first()
    res = client.post(reverse("quality:regulatory_submission_delete", kwargs={"pk": sub_to_delete.pk}))
    assert res.status_code == 302
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete").count() > 0
