"""Security, IDOR isolation, and authorization tests for Sub-module 13.10 (Audit Trail & Reporting)."""
import pytest
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from apps.documents.models.AuditReporting.DocumentAuditTrails import DocumentAuditTrail
from apps.documents.models.AuditReporting.AuditReportDefinitions import AuditReportDefinition
from apps.documents.models.AuditReporting.DocumentSecurityAlerts import DocumentSecurityAlert
from apps.documents.models.AuditReporting.ChainOfCustodyExports import ChainOfCustodyExport
from apps.documents.forms.AuditReporting.ChainOfCustodyExports import ChainOfCustodyExportForm
from apps.documents.forms.AuditReporting.DocumentSecurityAlerts import DocumentSecurityAlertTriageForm
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder

pytestmark = pytest.mark.django_db


# ==============================================================================
# 1. Multi-Tenant IDOR Isolation Tests
# ==============================================================================

class TestAuditReportingTenantIdor:
    """Ensure strict cross-tenant data isolation and 404 protection."""

    def test_audit_reporting_audit_trail_detail_idor_rejected(self, client_b, document_audit_trail):
        """Tenant B user requesting Tenant A audit trail detail receives 404."""
        url = reverse("documents:audit_trail_detail", args=[document_audit_trail.pk])
        res = client_b.get(url)
        assert res.status_code == 404

    def test_audit_reporting_audit_report_detail_idor_rejected(self, client_b, audit_report_definition):
        """Tenant B user requesting Tenant A report definition detail receives 404."""
        url = reverse("documents:audit_report_detail", args=[audit_report_definition.pk])
        res = client_b.get(url)
        assert res.status_code == 404

    def test_audit_reporting_audit_report_edit_idor_rejected(self, client_b, audit_report_definition):
        """Tenant B user attempting to edit Tenant A report definition receives 404."""
        url = reverse("documents:audit_report_edit", args=[audit_report_definition.pk])
        res = client_b.get(url)
        assert res.status_code == 404

    def test_audit_reporting_audit_report_delete_idor_rejected(self, client_b, audit_report_definition):
        """Tenant B user attempting to delete Tenant A report definition receives 404."""
        url = reverse("documents:audit_report_delete", args=[audit_report_definition.pk])
        res = client_b.post(url)
        assert res.status_code == 404

    def test_audit_reporting_security_alert_detail_idor_rejected(self, client_b, document_security_alert):
        """Tenant B user requesting Tenant A security alert detail receives 404."""
        url = reverse("documents:security_alert_detail", args=[document_security_alert.pk])
        res = client_b.get(url)
        assert res.status_code == 404

    def test_audit_reporting_security_alert_triage_idor_rejected(self, client_b, document_security_alert):
        """Tenant B user attempting to triage Tenant A security alert receives 404."""
        url = reverse("documents:security_alert_triage", args=[document_security_alert.pk])
        res = client_b.post(url, data={"status": "resolved", "action_taken": "logged_only"})
        assert res.status_code == 404

    def test_audit_reporting_custody_export_detail_idor_rejected(self, client_b, custody_export):
        """Tenant B user requesting Tenant A custody export detail receives 404."""
        url = reverse("documents:custody_export_detail", args=[custody_export.pk])
        res = client_b.get(url)
        assert res.status_code == 404

    def test_audit_reporting_custody_export_certificate_idor_rejected(self, client_b, custody_export):
        """Tenant B user requesting Tenant A certificate of authenticity receives 404."""
        url = reverse("documents:custody_export_certificate", args=[custody_export.pk])
        res = client_b.get(url)
        assert res.status_code == 404

    def test_audit_reporting_custody_export_revoke_idor_rejected(self, client_b, custody_export):
        """Tenant B user attempting to revoke Tenant A custody export receives 404."""
        url = reverse("documents:custody_export_revoke", args=[custody_export.pk])
        res = client_b.post(url)
        assert res.status_code == 404


# ==============================================================================
# 2. Cross-Tenant FK Injection Prevention in Forms
# ==============================================================================

class TestAuditReportingFkInjection:
    """Ensure forms strictly validate foreign keys and reject cross-tenant injection."""

    def test_audit_reporting_custody_export_rejects_foreign_document(self, tenant_a, tenant_b, admin_b):
        """Submitting a document belonging to Tenant B in Tenant A form raises validation error."""
        doc_b = Document.objects.create(
            tenant=tenant_b,
            title="Foreign Document B",
            document_type="sop",
            owner=admin_b,
        )
        form = ChainOfCustodyExportForm(
            data={
                "title": "Malicious Package",
                "regulatory_framework": "fda_21cfr11",
                "scope": "single_document",
                "document": doc_b.pk,
                "auditor_name": "Auditor Name",
                "auditor_email": "auditor@example.com",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "document" in form.errors

    def test_audit_reporting_custody_export_rejects_foreign_folder(self, tenant_a, tenant_b, admin_b):
        """Submitting a folder belonging to Tenant B in Tenant A form raises validation error."""
        folder_b = DocumentFolder.objects.create(
            tenant=tenant_b,
            name="Foreign Folder B",
            slug="foreign-folder-b",
            owner=admin_b,
        )
        form = ChainOfCustodyExportForm(
            data={
                "title": "Malicious Folder Package",
                "regulatory_framework": "iso_27001",
                "scope": "folder_tree",
                "folder": folder_b.pk,
                "auditor_name": "Auditor Name",
                "auditor_email": "auditor@example.com",
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "folder" in form.errors

    def test_audit_reporting_alert_triage_rejects_foreign_user(self, tenant_a, admin_b):
        """Assigning a user belonging to Tenant B in Tenant A triage form raises validation error."""
        form = DocumentSecurityAlertTriageForm(
            data={
                "status": "in_progress",
                "severity": "high",
                "action_taken": "user_warned",
                "assigned_to": admin_b.pk,
            },
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "assigned_to" in form.errors


# ==============================================================================
# 3. Authentication & Authorization Gates
# ==============================================================================

class TestAuditReportingAuthGates:
    """Ensure non-admin and unauthenticated users cannot access or mutate sensitive state."""

    def test_audit_reporting_unauthenticated_redirects_login(self, client, document_audit_trail):
        """Unauthenticated requests redirect to login with ?next= parameter."""
        urls = [
            reverse("documents:audit_trail_list"),
            reverse("documents:audit_trail_detail", args=[document_audit_trail.pk]),
            reverse("documents:audit_report_list"),
            reverse("documents:security_alert_list"),
            reverse("documents:custody_export_list"),
            reverse("documents:audit_dashboard"),
        ]
        for url in urls:
            res = client.get(url)
            assert res.status_code == 302
            assert "/login/" in res.url

    def test_audit_reporting_verify_chain_requires_tenant_admin(self, member_client):
        """Standard member receives 403 on audit_trail_verify_chain."""
        url = reverse("documents:audit_trail_verify_chain")
        res = member_client.post(url)
        assert res.status_code == 403

    def test_audit_reporting_security_alert_triage_requires_tenant_admin(self, member_client, document_security_alert):
        """Standard member receives 403 on security_alert_triage."""
        url = reverse("documents:security_alert_triage", args=[document_security_alert.pk])
        res = member_client.post(url, data={"status": "resolved", "action_taken": "logged_only"})
        assert res.status_code == 403

    def test_audit_reporting_security_alert_scan_requires_tenant_admin(self, member_client):
        """Standard member receives 403 on security_alert_scan."""
        url = reverse("documents:security_alert_scan")
        res = member_client.post(url)
        assert res.status_code == 403

    def test_audit_reporting_custody_export_revoke_requires_tenant_admin(self, member_client, custody_export):
        """Standard member receives 403 on custody_export_revoke."""
        url = reverse("documents:custody_export_revoke", args=[custody_export.pk])
        res = member_client.post(url)
        assert res.status_code == 403

    def test_audit_reporting_audit_report_delete_restricted(self, member_client, audit_report_definition):
        """Standard non-admin, non-creator user receives 403 on audit_report_delete."""
        url = reverse("documents:audit_report_delete", args=[audit_report_definition.pk])
        res = member_client.post(url)
        assert res.status_code == 403


# ==============================================================================
# 4. HTTP Method Enforcement
# ==============================================================================

class TestAuditReportingMethodEnforcement:
    """Ensure mutating POST endpoints reject GET requests with 405 Method Not Allowed."""

    def test_audit_reporting_post_only_endpoints_reject_get(self, client_a, document_security_alert, custody_export, audit_report_definition):
        post_endpoints = [
            reverse("documents:audit_trail_verify_chain"),
            reverse("documents:security_alert_triage", args=[document_security_alert.pk]),
            reverse("documents:security_alert_scan"),
            reverse("documents:custody_export_revoke", args=[custody_export.pk]),
            reverse("documents:audit_report_delete", args=[audit_report_definition.pk]),
            reverse("documents:auditor_portal_verify", args=[custody_export.access_token]),
        ]
        for url in post_endpoints:
            res = client_a.get(url)
            assert res.status_code == 405, f"Expected 405 for GET on {url}, got {res.status_code}"


# ==============================================================================
# 5. Public Auditor Portal Security Tests
# ==============================================================================

class TestAuditReportingAuditorPortalSecurity:
    """Verify security controls on the public external auditor portal."""

    def test_audit_reporting_portal_invalid_token_returns_404(self, client):
        """Non-existent token returns 404."""
        url = reverse("documents:auditor_portal_view", args=["non-existent-token-12345"])
        res = client.get(url)
        assert res.status_code == 404

    def test_audit_reporting_portal_revoked_package_returns_403(self, client, custody_export, admin_user):
        """Revoked package returns 403 Forbidden."""
        custody_export.revoke(user=admin_user)
        url = reverse("documents:auditor_portal_view", args=[custody_export.access_token])
        res = client.get(url)
        assert res.status_code == 403

    def test_audit_reporting_portal_expired_package_returns_410(self, client, custody_export):
        """Expired package returns 410 Gone."""
        custody_export.expires_at = timezone.now() - timedelta(days=1)
        custody_export.save(update_fields=["expires_at"])
        url = reverse("documents:auditor_portal_view", args=[custody_export.access_token])
        res = client.get(url)
        assert res.status_code == 410

    def test_audit_reporting_portal_passcode_lockout_and_audit_log(self, client, custody_export):
        """After 5 consecutive failed passcode attempts, lockout triggers and failed attempts are logged."""
        verify_url = reverse("documents:auditor_portal_verify", args=[custody_export.access_token])
        portal_url = reverse("documents:auditor_portal_view", args=[custody_export.access_token])

        # Submit 5 incorrect passcodes
        for _ in range(5):
            res = client.post(verify_url, data={"passcode": "WrongPassword!"}, follow=True)
            assert res.status_code == 200

        # Verify failed audit entries logged
        failed_logs = DocumentAuditTrail.objects.filter(
            tenant=custody_export.tenant,
            action_type="auditor_portal_accessed",
            is_success=False,
        )
        assert failed_logs.count() >= 5

        # 6th attempt is blocked by lockout
        res = client.post(verify_url, data={"passcode": "AuditPass2026!"}, follow=True)
        assert "Too many failed passcode attempts" in res.content.decode()


# ==============================================================================
# 6. Cryptographic Chain Tamper Detection
# ==============================================================================

class TestAuditReportingTamperDetection:
    """Verify cryptographic chain tamper detection flags database modifications."""

    def test_audit_reporting_tamper_detection_in_verify_chain(self, client_a, tenant_a, document, admin_user):
        """Direct database modification of an audit record breaks the chain and is detected."""
        # Create two valid chained entries
        entry1 = DocumentAuditTrail.objects.create(
            tenant=tenant_a,
            document=document,
            actor=admin_user,
            action_type="viewed",
            is_success=True,
        )
        entry2 = DocumentAuditTrail.objects.create(
            tenant=tenant_a,
            document=document,
            actor=admin_user,
            action_type="downloaded",
            is_success=True,
        )

        # Chain initially valid
        verify_url = reverse("documents:audit_trail_verify_chain")
        res = client_a.post(verify_url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        assert res.status_code == 200
        assert res.json()["is_valid"] is True

        # Tamper entry1 directly in DB bypassing model save validation
        DocumentAuditTrail.objects.filter(pk=entry1.pk).update(action_type="deleted")

        # Re-verify: tampering detected
        res = client_a.post(verify_url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        assert res.status_code == 200
        assert res.json()["is_valid"] is False
        assert res.json()["tampered_id"] == entry1.pk


# ==============================================================================
# 7. CSV Formula Injection Defense
# ==============================================================================

class TestAuditReportingCsvInjection:
    """Verify CSV exports neutralize formula injection payloads."""

    def test_audit_reporting_csv_sanitizes_formula_prefixes(self, client_a, tenant_a, document, admin_user):
        """Cells starting with =, +, -, @ have a single quote prepended."""
        malicious_title = "=cmd|' /C calc'!A0"
        DocumentAuditTrail.objects.create(
            tenant=tenant_a,
            document=document,
            actor=admin_user,
            action_type="viewed",
            document_title_snapshot=malicious_title,
            is_success=True,
        )
        url = reverse("documents:audit_trail_export_csv")
        res = client_a.get(url)
        assert res.status_code == 200
        content = res.content.decode("utf-8")
        assert f"'{malicious_title}" in content
