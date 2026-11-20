"""Unit and functional view tests for Quality Management Sub-module 12.11 Audit Management.

Tests all views, workflows, filters, command centers, and exports.
"""
from datetime import date, timedelta
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.quality.models import (
    AuditProgram,
    QualityAudit,
    AuditFinding,
    RegulatoryInspectionHost,
    CapaInvestigation,
)


@pytest.mark.django_db
class TestAuditManagementViews:
    """Test all function-based views in AuditManagement package."""

    # --- 1. AuditProgram Views ---

    def test_auditmanagement_audit_program_list_view(self, client, admin_user, audit_program_a):
        """Verify audit_program_list returns 200 with filters and annotated counts."""
        client.force_login(admin_user)
        url = reverse("quality:audit_program_list")
        resp = client.get(url)
        assert resp.status_code == 200
        assert "audit_programs" in resp.context
        assert "total_count" in resp.context
        assert audit_program_a.title.encode() in resp.content

        # Test search filter
        resp_filtered = client.get(url, {"q": "Enterprise", "year": audit_program_a.program_year})
        assert resp_filtered.status_code == 200

    def test_auditmanagement_audit_program_detail_view(self, client, admin_user, audit_program_a):
        """Verify audit_program_detail passes dual-bound context variables."""
        client.force_login(admin_user)
        url = reverse("quality:audit_program_detail", kwargs={"pk": audit_program_a.pk})
        resp = client.get(url)
        assert resp.status_code == 200
        assert resp.context["audit_program"] == audit_program_a
        assert resp.context["obj"] == audit_program_a
        assert "audits" in resp.context
        assert "completion_rate" in resp.context

    def test_auditmanagement_audit_program_create_and_edit_views(self, client, admin_user, tenant_a):
        """Verify audit_program_create and edit POST flows."""
        client.force_login(admin_user)
        create_url = reverse("quality:audit_program_create")
        resp = client.get(create_url)
        assert resp.status_code == 200

        data = {
            "title": "New FY2026 Test Program",
            "program_year": 2026,
            "program_type": "internal_qms",
            "risk_basis": "low_risk_annual",
            "scope_description": "Testing program creation",
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
            "allocated_budget_hours": 150,
            "program_manager": admin_user.pk,
        }
        resp = client.post(create_url, data)
        assert resp.status_code == 302
        new_prog = AuditProgram.objects.filter(tenant=tenant_a, title=data["title"]).first()
        assert new_prog is not None
        assert new_prog.status == "draft"

        # Edit
        edit_url = reverse("quality:audit_program_edit", kwargs={"pk": new_prog.pk})
        resp = client.get(edit_url)
        assert resp.status_code == 200
        data["title"] = "Updated Program Title"
        resp = client.post(edit_url, data)
        assert resp.status_code == 302
        new_prog.refresh_from_db()
        assert new_prog.title == "Updated Program Title"

    def test_auditmanagement_audit_program_approve_view(self, client, admin_user, audit_program_a):
        """Verify audit_program_approve transitions status to approved."""
        client.force_login(admin_user)
        audit_program_a.status = "draft"
        audit_program_a.save()

        url = reverse("quality:audit_program_approve", kwargs={"pk": audit_program_a.pk})
        resp = client.post(url)
        assert resp.status_code == 302
        audit_program_a.refresh_from_db()
        assert audit_program_a.status == "approved"
        assert audit_program_a.approved_by == admin_user

    # --- 2. QualityAudit Views ---

    def test_auditmanagement_quality_audit_list_view(self, client, admin_user, quality_audit_a):
        """Verify quality_audit_list renders with multi-criteria filters."""
        client.force_login(admin_user)
        url = reverse("quality:quality_audit_list")
        resp = client.get(url)
        assert resp.status_code == 200
        assert "quality_audits" in resp.context
        assert "audit_type_choices" in resp.context
        assert quality_audit_a.title.encode() in resp.content

    def test_auditmanagement_quality_audit_detail_view(self, client, admin_user, quality_audit_a):
        """Verify quality_audit_detail context variables and relationships."""
        client.force_login(admin_user)
        url = reverse("quality:quality_audit_detail", kwargs={"pk": quality_audit_a.pk})
        resp = client.get(url)
        assert resp.status_code == 200
        assert resp.context["quality_audit"] == quality_audit_a
        assert resp.context["obj"] == quality_audit_a
        assert "findings" in resp.context
        assert "regulatory_hosts" in resp.context

    def test_auditmanagement_quality_audit_publish_and_close(self, client, admin_user, quality_audit_a):
        """Verify quality_audit_publish_report and close actions."""
        client.force_login(admin_user)
        pub_url = reverse("quality:quality_audit_publish_report", kwargs={"pk": quality_audit_a.pk})
        resp = client.post(pub_url)
        assert resp.status_code == 302
        quality_audit_a.refresh_from_db()
        assert quality_audit_a.status == "reporting"
        assert quality_audit_a.report_published_date is not None

        close_url = reverse("quality:quality_audit_close", kwargs={"pk": quality_audit_a.pk})
        resp = client.post(close_url)
        assert resp.status_code == 302
        quality_audit_a.refresh_from_db()
        assert quality_audit_a.status == "closed"

    # --- 3. AuditFinding Views & CAPA Flow ---

    def test_auditmanagement_audit_finding_list_view(self, client, admin_user, audit_finding_a):
        """Verify audit_finding_list returns findings with severity indicators."""
        client.force_login(admin_user)
        url = reverse("quality:audit_finding_list")
        resp = client.get(url)
        assert resp.status_code == 200
        assert "audit_findings" in resp.context
        assert "open_count" in resp.context

    def test_auditmanagement_audit_finding_detail_view(self, client, admin_user, audit_finding_a):
        """Verify audit_finding_detail passes response_form when open."""
        client.force_login(admin_user)
        url = reverse("quality:audit_finding_detail", kwargs={"pk": audit_finding_a.pk})
        resp = client.get(url)
        assert resp.status_code == 200
        assert resp.context["audit_finding"] == audit_finding_a
        assert resp.context["obj"] == audit_finding_a
        assert "response_form" in resp.context

    def test_auditmanagement_audit_finding_submit_response_view(self, client, admin_user, audit_finding_a):
        """Verify auditee remediation response submission."""
        client.force_login(admin_user)
        url = reverse("quality:audit_finding_submit_response", kwargs={"pk": audit_finding_a.pk})
        data = {
            "containment_action": "Applied temporary physical label.",
            "root_cause_summary": "Printer ran out of thermal ribbons.",
            "corrective_action_plan": "Install automatic low-ribbon sensor and alarm.",
        }
        resp = client.post(url, data)
        assert resp.status_code == 302
        audit_finding_a.refresh_from_db()
        assert audit_finding_a.status == "response_submitted"
        assert audit_finding_a.containment_action == data["containment_action"]

    def test_auditmanagement_audit_finding_create_capa_view(self, client, admin_user, audit_finding_a):
        """Verify closed-loop CAPA creation from audit finding."""
        client.force_login(admin_user)
        audit_finding_a.severity = "major"
        audit_finding_a.save()

        url = reverse("quality:audit_finding_create_capa", kwargs={"pk": audit_finding_a.pk})
        resp = client.post(url)
        assert resp.status_code == 302
        audit_finding_a.refresh_from_db()
        assert audit_finding_a.status == "capa_in_progress"
        assert audit_finding_a.linked_capa is not None
        assert "CAPA from Audit Finding" in audit_finding_a.linked_capa.title
        assert audit_finding_a.linked_capa.risk_priority == "high"
        assert audit_finding_a.linked_capa.quality_owner == admin_user

    # --- 4. RegulatoryInspectionHost & Command Centers ---

    def test_auditmanagement_regulatory_inspection_host_list_view(self, client, admin_user, inspection_host_a):
        """Verify regulatory_inspection_host_list renders."""
        client.force_login(admin_user)
        url = reverse("quality:regulatory_inspection_host_list")
        resp = client.get(url)
        assert resp.status_code == 200
        assert "regulatory_inspection_hosts" in resp.context
        assert inspection_host_a.inspection_title.encode() in resp.content

    def test_auditmanagement_regulatory_inspection_request_flow(self, client, admin_user, inspection_host_a):
        """Verify logging and fulfilling inspection document requests."""
        client.force_login(admin_user)
        initial_logged = inspection_host_a.requests_logged_count
        initial_fulfilled = inspection_host_a.requests_fulfilled_count

        log_url = reverse("quality:regulatory_inspection_host_log_request", kwargs={"pk": inspection_host_a.pk})
        resp = client.post(log_url, {"request_description": "Cleanroom air particulate logs", "priority": "urgent"})
        assert resp.status_code == 302
        inspection_host_a.refresh_from_db()
        assert inspection_host_a.requests_logged_count == initial_logged + 1

        fulfill_url = reverse("quality:regulatory_inspection_host_fulfill_request", kwargs={"pk": inspection_host_a.pk})
        resp = client.post(fulfill_url, {"request_id": "REQ-1", "fulfillment_notes": "Delivered to inspector."})
        assert resp.status_code == 302
        inspection_host_a.refresh_from_db()
        assert inspection_host_a.requests_fulfilled_count == initial_fulfilled + 1

    def test_auditmanagement_audit_action_tracker_view(self, client, admin_user, audit_finding_a):
        """Verify audit_action_tracker command center renders."""
        client.force_login(admin_user)
        url = reverse("quality:audit_action_tracker")
        resp = client.get(url)
        assert resp.status_code == 200
        assert "open_findings" in resp.context
        assert "total_open_count" in resp.context

    def test_auditmanagement_audit_war_room_view(self, client, admin_user, inspection_host_a):
        """Verify audit_war_room live command center renders."""
        client.force_login(admin_user)
        url = reverse("quality:audit_war_room")
        resp = client.get(url)
        assert resp.status_code == 200
        assert "active_inspections" in resp.context
        assert "selected_host" in resp.context

        # Host selection query parameter
        resp_host = client.get(url, {"host": inspection_host_a.pk})
        assert resp_host.status_code == 200
        assert resp_host.context["selected_host"] == inspection_host_a

    # --- 5. CSV Export Views ---

    def test_auditmanagement_csv_exports(self, client, admin_user):
        """Verify all 4 CSV export endpoints stream compliant CSV with security headers."""
        client.force_login(admin_user)
        endpoints = [
            reverse("quality:audit_program_export_csv"),
            reverse("quality:quality_audit_export_csv"),
            reverse("quality:audit_finding_export_csv"),
            reverse("quality:regulatory_inspection_host_export_csv"),
        ]
        for url in endpoints:
            resp = client.get(url)
            assert resp.status_code == 200
            assert resp["Content-Type"].startswith("text/csv")
            assert "attachment;" in resp["Content-Disposition"]
            assert resp["X-Content-Type-Options"] == "nosniff"
            assert len(resp.content) > 0
