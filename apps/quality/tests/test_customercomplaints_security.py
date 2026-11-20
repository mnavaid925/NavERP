"""Security, multi-tenant isolation (IDOR), and authorization tests for Sub-module 12.13: Customer Complaint Handling.

Tests:
- Authentication gates (@login_required)
- Multi-tenant data isolation (Cross-tenant IDOR -> 404)
- Foreign key cross-tenant injection rejection
- Administrative authorization gates (@tenant_admin_required on delete views -> 403)
- HTTP method restrictions (@require_POST -> 405)
- Workflow and tamper guards (preventing edits/deletions on locked/filed records)
"""
from datetime import timedelta
import pytest
from django.urls import reverse
from django.utils import timezone


@pytest.mark.django_db
def test_customercomplaints_unauthenticated_redirects(client, customer_complaint_a, complaint_investigation_a, regulatory_report_a, field_action_a):
    """Verify unauthenticated requests redirect to login."""
    urls = [
        reverse("quality:customer_complaint_list"),
        reverse("quality:customer_complaint_create"),
        reverse("quality:customer_complaint_detail", kwargs={"pk": customer_complaint_a.pk}),
        reverse("quality:customer_complaint_edit", kwargs={"pk": customer_complaint_a.pk}),
        reverse("quality:complaint_investigation_list"),
        reverse("quality:complaint_investigation_detail", kwargs={"pk": complaint_investigation_a.pk}),
        reverse("quality:regulatory_report_list"),
        reverse("quality:regulatory_report_detail", kwargs={"pk": regulatory_report_a.pk}),
        reverse("quality:field_action_list"),
        reverse("quality:field_action_detail", kwargs={"pk": field_action_a.pk}),
        reverse("quality:complaint_trending_dashboard"),
        reverse("quality:customer_complaint_export_csv"),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/login" in resp.headers.get("Location", "") or "/accounts/login" in resp.headers.get("Location", "")


@pytest.mark.django_db
def test_customercomplaints_cross_tenant_idor_complaint(client, admin_user, customer_complaint_b):
    """Verify Tenant A user accessing Tenant B CustomerComplaint returns 404."""
    client.force_login(admin_user)
    assert client.get(reverse("quality:customer_complaint_detail", kwargs={"pk": customer_complaint_b.pk})).status_code == 404
    assert client.get(reverse("quality:customer_complaint_edit", kwargs={"pk": customer_complaint_b.pk})).status_code == 404
    assert client.post(reverse("quality:customer_complaint_delete", kwargs={"pk": customer_complaint_b.pk})).status_code == 404
    assert client.post(reverse("quality:customer_complaint_triage", kwargs={"pk": customer_complaint_b.pk})).status_code == 404
    assert client.post(reverse("quality:customer_complaint_close", kwargs={"pk": customer_complaint_b.pk})).status_code == 404


@pytest.mark.django_db
def test_customercomplaints_cross_tenant_idor_investigation(client, admin_user, complaint_investigation_b):
    """Verify Tenant A user accessing Tenant B ComplaintInvestigation returns 404."""
    client.force_login(admin_user)
    assert client.get(reverse("quality:complaint_investigation_detail", kwargs={"pk": complaint_investigation_b.pk})).status_code == 404
    assert client.get(reverse("quality:complaint_investigation_edit", kwargs={"pk": complaint_investigation_b.pk})).status_code == 404
    assert client.post(reverse("quality:complaint_investigation_delete", kwargs={"pk": complaint_investigation_b.pk})).status_code == 404
    assert client.post(reverse("quality:complaint_investigation_complete", kwargs={"pk": complaint_investigation_b.pk})).status_code == 404


@pytest.mark.django_db
def test_customercomplaints_cross_tenant_idor_regulatory_report(client, admin_user, regulatory_report_b):
    """Verify Tenant A user accessing Tenant B RegulatoryReport returns 404."""
    client.force_login(admin_user)
    assert client.get(reverse("quality:regulatory_report_detail", kwargs={"pk": regulatory_report_b.pk})).status_code == 404
    assert client.get(reverse("quality:regulatory_report_edit", kwargs={"pk": regulatory_report_b.pk})).status_code == 404
    assert client.post(reverse("quality:regulatory_report_delete", kwargs={"pk": regulatory_report_b.pk})).status_code == 404
    assert client.post(reverse("quality:regulatory_report_submit", kwargs={"pk": regulatory_report_b.pk})).status_code == 404
    assert client.post(reverse("quality:regulatory_report_acknowledge", kwargs={"pk": regulatory_report_b.pk})).status_code == 404


@pytest.mark.django_db
def test_customercomplaints_cross_tenant_idor_field_action(client, admin_user, field_action_b):
    """Verify Tenant A user accessing Tenant B FieldAction returns 404."""
    client.force_login(admin_user)
    assert client.get(reverse("quality:field_action_detail", kwargs={"pk": field_action_b.pk})).status_code == 404
    assert client.get(reverse("quality:field_action_edit", kwargs={"pk": field_action_b.pk})).status_code == 404
    assert client.post(reverse("quality:field_action_delete", kwargs={"pk": field_action_b.pk})).status_code == 404
    assert client.post(reverse("quality:field_action_close", kwargs={"pk": field_action_b.pk})).status_code == 404


@pytest.mark.django_db
def test_customercomplaints_cross_tenant_fk_rejection(client, admin_user, tenant_a, customer_party_b, customer_complaint_b):
    """Verify cross-tenant foreign key assignment is blocked during entity creation."""
    client.force_login(admin_user)
    today = timezone.now().date()

    # Attempt to link Tenant B's customer party to a Tenant A complaint
    data = {
        "title": "Cross-Tenant Injection Complaint",
        "intake_channel": "email",
        "customer": customer_party_b.pk,
        "complainant_name": "Injected Contact",
        "item_code": "PUMP-4000",
        "item_name": "Infusion Pro",
        "date_received": today,
        "problem_description": "IDOR test payload",
        "severity": "minor_cosmetic",
        "validity": "valid_complaint",
        "reportability": "exempt",
        "sample_return_status": "not_requested",
        "investigation_required": True,
        "assigned_to": admin_user.pk,
    }
    resp = client.post(reverse("quality:customer_complaint_create"), data)
    assert resp.status_code == 200
    assert "customer" in resp.context["form"].errors

    # Attempt to link Tenant B's complaint to a Tenant A investigation
    inv_data = {
        "complaint": customer_complaint_b.pk,
        "lead_investigator": admin_user.pk,
        "target_completion_date": today + timedelta(days=7),
        "analytical_method": "electrical_functional",
        "dhr_quantity_produced": 100,
        "root_cause_category": "component_defect",
    }
    resp_inv = client.post(reverse("quality:complaint_investigation_create"), inv_data)
    assert resp_inv.status_code == 200
    assert "complaint" in resp_inv.context["form"].errors


@pytest.mark.django_db
def test_customercomplaints_delete_requires_admin(client, member_user, customer_complaint_a, complaint_investigation_a, regulatory_report_a, field_action_a):
    """Verify non-admin member cannot delete complaint handling records (403 Forbidden)."""
    client.force_login(member_user)
    delete_urls = [
        reverse("quality:customer_complaint_delete", kwargs={"pk": customer_complaint_a.pk}),
        reverse("quality:complaint_investigation_delete", kwargs={"pk": complaint_investigation_a.pk}),
        reverse("quality:regulatory_report_delete", kwargs={"pk": regulatory_report_a.pk}),
        reverse("quality:field_action_delete", kwargs={"pk": field_action_a.pk}),
    ]
    for url in delete_urls:
        resp = client.post(url)
        assert resp.status_code == 403


@pytest.mark.django_db
def test_customercomplaints_methods_require_post(client, admin_user, customer_complaint_a, complaint_investigation_a, regulatory_report_a, field_action_a):
    """Verify action and delete endpoints reject GET with 405 Method Not Allowed."""
    client.force_login(admin_user)
    post_only_urls = [
        reverse("quality:customer_complaint_delete", kwargs={"pk": customer_complaint_a.pk}),
        reverse("quality:customer_complaint_triage", kwargs={"pk": customer_complaint_a.pk}),
        reverse("quality:customer_complaint_close", kwargs={"pk": customer_complaint_a.pk}),
        reverse("quality:complaint_investigation_delete", kwargs={"pk": complaint_investigation_a.pk}),
        reverse("quality:complaint_investigation_complete", kwargs={"pk": complaint_investigation_a.pk}),
        reverse("quality:regulatory_report_delete", kwargs={"pk": regulatory_report_a.pk}),
        reverse("quality:regulatory_report_submit", kwargs={"pk": regulatory_report_a.pk}),
        reverse("quality:regulatory_report_acknowledge", kwargs={"pk": regulatory_report_a.pk}),
        reverse("quality:field_action_delete", kwargs={"pk": field_action_a.pk}),
        reverse("quality:field_action_close", kwargs={"pk": field_action_a.pk}),
    ]
    for url in post_only_urls:
        resp = client.get(url)
        assert resp.status_code == 405


@pytest.mark.django_db
def test_customercomplaints_workflow_tampering_guards(client, admin_user, customer_complaint_a, complaint_investigation_a, regulatory_report_a):
    """Verify edits/deletions on closed or submitted records are prevented."""
    client.force_login(admin_user)

    # 1. Closed complaint cannot be edited
    customer_complaint_a.status = "closed"
    customer_complaint_a.save()
    resp = client.get(reverse("quality:customer_complaint_edit", kwargs={"pk": customer_complaint_a.pk}))
    assert resp.status_code == 302
    assert resp.url == reverse("quality:customer_complaint_detail", kwargs={"pk": customer_complaint_a.pk})

    # 2. Approved investigation cannot be edited
    complaint_investigation_a.status = "approved"
    complaint_investigation_a.save()
    resp = client.get(reverse("quality:complaint_investigation_edit", kwargs={"pk": complaint_investigation_a.pk}))
    assert resp.status_code == 302
    assert resp.url == reverse("quality:complaint_investigation_detail", kwargs={"pk": complaint_investigation_a.pk})

    # 3. Submitted regulatory report cannot be edited
    regulatory_report_a.submission_status = "submitted"
    regulatory_report_a.save()
    resp = client.get(reverse("quality:regulatory_report_edit", kwargs={"pk": regulatory_report_a.pk}))
    assert resp.status_code == 302
    assert resp.url == reverse("quality:regulatory_report_detail", kwargs={"pk": regulatory_report_a.pk})

    # 4. Complaint with active filed regulatory report cannot be deleted
    resp = client.post(reverse("quality:customer_complaint_delete", kwargs={"pk": customer_complaint_a.pk}))
    assert resp.status_code == 302
    assert resp.url == reverse("quality:customer_complaint_detail", kwargs={"pk": customer_complaint_a.pk})
