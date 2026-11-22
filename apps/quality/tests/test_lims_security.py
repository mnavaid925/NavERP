"""Security, tenant isolation (IDOR), and authorization tests for Submodule 12.19 LIMS."""
import pytest
from django.urls import reverse

from apps.core.models import AuditLog


@pytest.mark.django_db
def test_lims_unauthenticated_redirect(
    client, lab_sample_a, lab_specification_a, lab_test_worksheet_a, oos_investigation_a
):
    urls = [
        reverse("quality:lims_dashboard"),
        reverse("quality:lims_export_csv"),
        reverse("quality:lab_sample_list"),
        reverse("quality:lab_sample_create"),
        reverse("quality:lab_sample_detail", kwargs={"pk": lab_sample_a.pk}),
        reverse("quality:lab_sample_edit", kwargs={"pk": lab_sample_a.pk}),
        reverse("quality:lab_specification_list"),
        reverse("quality:lab_specification_create"),
        reverse("quality:lab_specification_detail", kwargs={"pk": lab_specification_a.pk}),
        reverse("quality:lab_specification_edit", kwargs={"pk": lab_specification_a.pk}),
        reverse("quality:lab_test_worksheet_list"),
        reverse("quality:lab_test_worksheet_create"),
        reverse("quality:lab_test_worksheet_detail", kwargs={"pk": lab_test_worksheet_a.pk}),
        reverse("quality:lab_test_worksheet_edit", kwargs={"pk": lab_test_worksheet_a.pk}),
        reverse("quality:oos_investigation_list"),
        reverse("quality:oos_investigation_create"),
        reverse("quality:oos_investigation_detail", kwargs={"pk": oos_investigation_a.pk}),
        reverse("quality:oos_investigation_edit", kwargs={"pk": oos_investigation_a.pk}),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/login/" in resp["Location"]


@pytest.mark.django_db
def test_lims_cross_tenant_idor_protection(
    client, admin_b, lab_sample_a, lab_specification_a, lab_test_worksheet_a, oos_investigation_a
):
    # Log in as user from tenant_b (admin_b) and attempt to touch tenant_a's data
    client.force_login(admin_b)

    # 1. LabSample IDOR -> 404
    assert client.get(reverse("quality:lab_sample_detail", kwargs={"pk": lab_sample_a.pk})).status_code == 404
    assert client.get(reverse("quality:lab_sample_edit", kwargs={"pk": lab_sample_a.pk})).status_code == 404
    assert client.post(reverse("quality:lab_sample_receive", kwargs={"pk": lab_sample_a.pk})).status_code == 404
    assert client.post(reverse("quality:lab_sample_delete", kwargs={"pk": lab_sample_a.pk})).status_code == 404

    # 2. LabSpecification IDOR -> 404
    assert client.get(reverse("quality:lab_specification_detail", kwargs={"pk": lab_specification_a.pk})).status_code == 404
    assert client.get(reverse("quality:lab_specification_edit", kwargs={"pk": lab_specification_a.pk})).status_code == 404
    assert client.post(reverse("quality:lab_specification_delete", kwargs={"pk": lab_specification_a.pk})).status_code == 404

    # 3. LabTestWorksheet IDOR -> 404
    assert client.get(reverse("quality:lab_test_worksheet_detail", kwargs={"pk": lab_test_worksheet_a.pk})).status_code == 404
    assert client.get(reverse("quality:lab_test_worksheet_edit", kwargs={"pk": lab_test_worksheet_a.pk})).status_code == 404
    assert client.post(reverse("quality:lab_test_worksheet_complete", kwargs={"pk": lab_test_worksheet_a.pk})).status_code == 404
    assert client.post(reverse("quality:lab_test_worksheet_delete", kwargs={"pk": lab_test_worksheet_a.pk})).status_code == 404

    # 4. OosInvestigation IDOR -> 404
    assert client.get(reverse("quality:oos_investigation_detail", kwargs={"pk": oos_investigation_a.pk})).status_code == 404
    assert client.get(reverse("quality:oos_investigation_edit", kwargs={"pk": oos_investigation_a.pk})).status_code == 404
    assert client.post(reverse("quality:oos_investigation_close", kwargs={"pk": oos_investigation_a.pk})).status_code == 404
    assert client.post(reverse("quality:oos_investigation_delete", kwargs={"pk": oos_investigation_a.pk})).status_code == 404


@pytest.mark.django_db
def test_lims_oos_close_tenant_admin_gate_i1(client, tenant_a, member_user, oos_investigation_a):
    # Non-admin member user in tenant_a
    client.force_login(member_user)
    close_url = reverse("quality:oos_investigation_close", kwargs={"pk": oos_investigation_a.pk})
    resp = client.post(close_url)
    # Blocked by @tenant_admin_required (403 Forbidden or redirect to dashboard/login depending on decorator)
    assert resp.status_code in [403, 302]
    oos_investigation_a.refresh_from_db()
    assert oos_investigation_a.status == "open"  # NOT closed!


@pytest.mark.django_db
def test_lims_audit_logging_on_delete(client_a, tenant_a, lab_specification_a):
    initial_count = AuditLog.objects.filter(tenant=tenant_a, action="delete").count()
    delete_url = reverse("quality:lab_specification_delete", kwargs={"pk": lab_specification_a.pk})
    resp = client_a.post(delete_url)
    assert resp.status_code == 302
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete").count() > initial_count
