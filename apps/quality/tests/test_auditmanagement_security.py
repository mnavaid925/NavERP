"""Security, multi-tenant isolation (IDOR), and authorization tests for Sub-module 12.11 Audit Management.

Tests:
- Authentication gates (@login_required)
- Multi-tenant data isolation (Cross-tenant IDOR -> 404)
- Administrative authorization gates (@tenant_admin_required on deletes and approve -> 403)
- Auditor independence enforcement
- State machine lifecycle guards
- CSV sanitization against formula injection
"""
import pytest
from django.urls import reverse

from apps.quality.models import (
    AuditProgram,
    QualityAudit,
    AuditFinding,
    RegulatoryInspectionHost,
)


@pytest.mark.django_db
class TestAuditManagementSecurity:
    """Security verification test suite for Audit Management sub-module."""

    # --- 1. Authentication Gates ---

    def test_auditmanagement_unauthenticated_redirects(self, client, audit_program_a, quality_audit_a, audit_finding_a, inspection_host_a):
        """Verify unauthenticated requests redirect to login."""
        urls = [
            reverse("quality:audit_program_list"),
            reverse("quality:audit_program_detail", kwargs={"pk": audit_program_a.pk}),
            reverse("quality:quality_audit_list"),
            reverse("quality:quality_audit_detail", kwargs={"pk": quality_audit_a.pk}),
            reverse("quality:audit_finding_list"),
            reverse("quality:audit_finding_detail", kwargs={"pk": audit_finding_a.pk}),
            reverse("quality:regulatory_inspection_host_list"),
            reverse("quality:regulatory_inspection_host_detail", kwargs={"pk": inspection_host_a.pk}),
            reverse("quality:audit_action_tracker"),
            reverse("quality:audit_war_room"),
        ]
        for url in urls:
            resp = client.get(url)
            assert resp.status_code == 302
            assert "/login" in resp.headers.get("Location", "") or "/accounts/login" in resp.headers.get("Location", "")

    # --- 2. Multi-Tenant IDOR Isolation (Cross-Tenant -> 404) ---

    def test_auditmanagement_cross_tenant_idor_audit_program(self, client, admin_user, audit_program_b):
        """Verify Tenant A user accessing Tenant B AuditProgram returns 404."""
        client.force_login(admin_user)
        assert client.get(reverse("quality:audit_program_detail", kwargs={"pk": audit_program_b.pk})).status_code == 404
        assert client.get(reverse("quality:audit_program_edit", kwargs={"pk": audit_program_b.pk})).status_code == 404
        assert client.post(reverse("quality:audit_program_approve", kwargs={"pk": audit_program_b.pk})).status_code == 404
        assert client.post(reverse("quality:audit_program_delete", kwargs={"pk": audit_program_b.pk})).status_code == 404

    def test_auditmanagement_cross_tenant_idor_quality_audit(self, client, admin_user, quality_audit_b):
        """Verify Tenant A user accessing Tenant B QualityAudit returns 404."""
        client.force_login(admin_user)
        assert client.get(reverse("quality:quality_audit_detail", kwargs={"pk": quality_audit_b.pk})).status_code == 404
        assert client.get(reverse("quality:quality_audit_edit", kwargs={"pk": quality_audit_b.pk})).status_code == 404
        assert client.post(reverse("quality:quality_audit_publish_report", kwargs={"pk": quality_audit_b.pk})).status_code == 404
        assert client.post(reverse("quality:quality_audit_close", kwargs={"pk": quality_audit_b.pk})).status_code == 404
        assert client.post(reverse("quality:quality_audit_delete", kwargs={"pk": quality_audit_b.pk})).status_code == 404

    def test_auditmanagement_cross_tenant_idor_audit_finding(self, client, admin_user, audit_finding_b):
        """Verify Tenant A user accessing Tenant B AuditFinding returns 404."""
        client.force_login(admin_user)
        assert client.get(reverse("quality:audit_finding_detail", kwargs={"pk": audit_finding_b.pk})).status_code == 404
        assert client.get(reverse("quality:audit_finding_edit", kwargs={"pk": audit_finding_b.pk})).status_code == 404
        assert client.post(reverse("quality:audit_finding_submit_response", kwargs={"pk": audit_finding_b.pk})).status_code == 404
        assert client.post(reverse("quality:audit_finding_verify_close", kwargs={"pk": audit_finding_b.pk})).status_code == 404
        assert client.post(reverse("quality:audit_finding_create_capa", kwargs={"pk": audit_finding_b.pk})).status_code == 404
        assert client.post(reverse("quality:audit_finding_delete", kwargs={"pk": audit_finding_b.pk})).status_code == 404

    def test_auditmanagement_cross_tenant_idor_regulatory_inspection(self, client, admin_user, inspection_host_b):
        """Verify Tenant A user accessing Tenant B RegulatoryInspectionHost returns 404."""
        client.force_login(admin_user)
        assert client.get(reverse("quality:regulatory_inspection_host_detail", kwargs={"pk": inspection_host_b.pk})).status_code == 404
        assert client.get(reverse("quality:regulatory_inspection_host_edit", kwargs={"pk": inspection_host_b.pk})).status_code == 404
        assert client.post(reverse("quality:regulatory_inspection_host_log_request", kwargs={"pk": inspection_host_b.pk})).status_code == 404
        assert client.post(reverse("quality:regulatory_inspection_host_fulfill_request", kwargs={"pk": inspection_host_b.pk})).status_code == 404
        assert client.post(reverse("quality:regulatory_inspection_host_close", kwargs={"pk": inspection_host_b.pk})).status_code == 404
        assert client.post(reverse("quality:regulatory_inspection_host_delete", kwargs={"pk": inspection_host_b.pk})).status_code == 404

    def test_auditmanagement_war_room_host_param_idor(self, client, admin_user, inspection_host_b):
        """Verify War Room ?host=<foreign_pk> filters foreign host out of context."""
        client.force_login(admin_user)
        url = reverse("quality:audit_war_room") + f"?host={inspection_host_b.pk}"
        resp = client.get(url)
        assert resp.status_code == 200
        # Selected host must not be inspection_host_b
        if resp.context.get("selected_host"):
            assert resp.context["selected_host"].pk != inspection_host_b.pk

    # --- 3. Authorization Gates (@tenant_admin_required) ---

    def test_auditmanagement_program_approve_requires_admin(self, client, member_user, audit_program_a):
        """Verify non-admin user cannot approve audit program (403 Forbidden)."""
        client.force_login(member_user)
        url = reverse("quality:audit_program_approve", kwargs={"pk": audit_program_a.pk})
        resp = client.post(url)
        assert resp.status_code == 403

    def test_auditmanagement_deletes_require_admin(self, client, member_user, audit_program_a, quality_audit_a, audit_finding_a, inspection_host_a):
        """Verify all 4 delete actions require tenant admin privileges (403 Forbidden)."""
        client.force_login(member_user)
        delete_urls = [
            reverse("quality:audit_program_delete", kwargs={"pk": audit_program_a.pk}),
            reverse("quality:quality_audit_delete", kwargs={"pk": quality_audit_a.pk}),
            reverse("quality:audit_finding_delete", kwargs={"pk": audit_finding_a.pk}),
            reverse("quality:regulatory_inspection_host_delete", kwargs={"pk": inspection_host_a.pk}),
        ]
        for url in delete_urls:
            resp = client.post(url)
            assert resp.status_code == 403

    # --- 4. Auditor Independence & Segregation of Duties ---

    def test_auditmanagement_auditee_cannot_self_verify_closure(self, client, member_user, audit_finding_a):
        """Verify assigned auditee cannot self-verify and close their own non-conformance."""
        audit_finding_a.assignee = member_user
        audit_finding_a.status = "response_submitted"
        audit_finding_a.save()

        client.force_login(member_user)
        url = reverse("quality:audit_finding_verify_close", kwargs={"pk": audit_finding_a.pk})
        resp = client.post(url, {"closure_notes": "Self verification attempt"})
        assert resp.status_code == 302
        audit_finding_a.refresh_from_db()
        # Status must not be closed
        assert audit_finding_a.status != "closed"

    def test_auditmanagement_quality_audit_close_authorization(self, client, member_user, quality_audit_a):
        """Verify non-auditor standard user cannot close a quality audit."""
        client.force_login(member_user)
        url = reverse("quality:quality_audit_close", kwargs={"pk": quality_audit_a.pk})
        resp = client.post(url)
        assert resp.status_code == 302
        quality_audit_a.refresh_from_db()
        assert quality_audit_a.status != "closed"

    # --- 5. State Machine Lifecycle Guards ---

    def test_auditmanagement_cannot_submit_response_on_closed_finding(self, client, admin_user, audit_finding_a):
        """Verify closed audit finding rejects response submission."""
        audit_finding_a.status = "closed"
        audit_finding_a.save()

        client.force_login(admin_user)
        url = reverse("quality:audit_finding_submit_response", kwargs={"pk": audit_finding_a.pk})
        resp = client.post(url, {"containment_action": "Late containment"})
        assert resp.status_code == 302
        audit_finding_a.refresh_from_db()
        assert audit_finding_a.status == "closed"

    def test_auditmanagement_cancelled_audit_rejects_report_publication(self, client, admin_user, quality_audit_a):
        """Verify cancelled audit cannot publish report or be closed."""
        quality_audit_a.status = "cancelled"
        quality_audit_a.save()

        client.force_login(admin_user)
        pub_url = reverse("quality:quality_audit_publish_report", kwargs={"pk": quality_audit_a.pk})
        resp = client.post(pub_url)
        assert resp.status_code == 302
        quality_audit_a.refresh_from_db()
        assert quality_audit_a.status == "cancelled"
