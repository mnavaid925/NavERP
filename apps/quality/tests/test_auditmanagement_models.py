"""Unit tests for Quality Management Sub-module 12.11 Audit Management models.

Tests models:
- AuditProgram (QPRG)
- QualityAudit (QAUD)
- AuditFinding (QFND)
- RegulatoryInspectionHost (QHST)
"""
from datetime import date, timedelta
from decimal import Decimal
import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.quality.models import (
    AuditProgram,
    QualityAudit,
    AuditFinding,
    RegulatoryInspectionHost,
)


@pytest.mark.django_db
class TestAuditManagementModels:
    """Test invariants, computed properties, auto-numbering, and constraints on 12.11 models."""

    def test_auditmanagement_audit_program_creation(self, audit_program_a, tenant_a, admin_user):
        """Verify AuditProgram auto-numbering, properties, and string representation."""
        assert audit_program_a.number.startswith("QPRG-")
        assert audit_program_a.tenant == tenant_a
        assert str(audit_program_a) == f"{audit_program_a.number} - {audit_program_a.title} ({audit_program_a.program_year})"
        assert audit_program_a.total_audits_count >= 0
        assert audit_program_a.progress_percentage >= 0

    def test_auditmanagement_audit_program_annotation_optimization(self, audit_program_a):
        """Verify AuditProgram property reuses annotated values when present to eliminate N+1 queries."""
        audit_program_a.annotated_total = 10
        audit_program_a.annotated_completed = 7
        assert audit_program_a.total_audits_count == 10
        assert audit_program_a.completed_audits_count == 7
        assert audit_program_a.progress_percentage == 70

    def test_auditmanagement_quality_audit_creation(self, quality_audit_a, audit_program_a, tenant_a):
        """Verify QualityAudit fields, parent program linkage, and auto-numbering."""
        assert quality_audit_a.number.startswith("QAUD-")
        assert quality_audit_a.tenant == tenant_a
        assert quality_audit_a.program == audit_program_a
        assert str(quality_audit_a) == f"{quality_audit_a.number} - {quality_audit_a.title}"
        assert quality_audit_a.days_open >= 0

    def test_auditmanagement_quality_audit_is_overdue(self, quality_audit_a):
        """Verify QualityAudit.is_overdue respects status and dates."""
        today = timezone.now().date()
        quality_audit_a.status = "in_progress"
        quality_audit_a.planned_end_date = today - timedelta(days=2)
        assert quality_audit_a.is_overdue is True

        quality_audit_a.planned_end_date = today + timedelta(days=5)
        assert quality_audit_a.is_overdue is False

        quality_audit_a.status = "closed"
        quality_audit_a.planned_end_date = today - timedelta(days=2)
        assert quality_audit_a.is_overdue is False

    def test_auditmanagement_audit_finding_creation_and_sync(self, audit_finding_a, quality_audit_a):
        """Verify AuditFinding creation, number prefix, and parent audit sync."""
        assert audit_finding_a.number.startswith("QFND-")
        assert audit_finding_a.audit == quality_audit_a
        assert "QFND-" in str(audit_finding_a)

        # Parent audit counts must be synchronized on finding save
        quality_audit_a.refresh_from_db()
        assert quality_audit_a.total_findings_count >= 1
        assert quality_audit_a.minor_findings_count >= 1

    def test_auditmanagement_audit_finding_delete_sync(self, quality_audit_a, tenant_a, admin_user):
        """Verify deleting an AuditFinding invokes sync_findings_counts on parent audit."""
        initial_count = quality_audit_a.total_findings_count
        finding = AuditFinding.objects.create(
            tenant=tenant_a,
            audit=quality_audit_a,
            finding_number_in_audit=99,
            title="Temporary finding to delete",
            severity="critical",
            standard_clause="ISO 13485:2016 §4.1",
            requirement_statement="Test requirement",
            condition_evidence="Test evidence",
            assignee=admin_user,
            response_due_date=timezone.now().date() + timedelta(days=10),
            status="issued",
        )
        quality_audit_a.refresh_from_db()
        assert quality_audit_a.total_findings_count == initial_count + 1
        assert quality_audit_a.critical_findings_count >= 1

        finding.delete()
        quality_audit_a.refresh_from_db()
        assert quality_audit_a.total_findings_count == initial_count
        assert quality_audit_a.critical_findings_count == 0

    def test_auditmanagement_audit_finding_is_overdue_alignment(self, audit_finding_a):
        """Verify AuditFinding.is_overdue only triggers for un-remediated states."""
        today = timezone.now().date()
        audit_finding_a.response_due_date = today - timedelta(days=3)

        audit_finding_a.status = "issued"
        assert audit_finding_a.is_overdue is True

        audit_finding_a.status = "escalated"
        assert audit_finding_a.is_overdue is True

        audit_finding_a.status = "response_submitted"
        assert audit_finding_a.is_overdue is False

        audit_finding_a.status = "capa_in_progress"
        assert audit_finding_a.is_overdue is False

        audit_finding_a.status = "verification_pending"
        assert audit_finding_a.is_overdue is False

        audit_finding_a.status = "closed"
        assert audit_finding_a.is_overdue is False

    def test_auditmanagement_audit_finding_requires_capa(self, audit_finding_a):
        """Verify requires_capa logic for critical/major observations without CAPA link."""
        audit_finding_a.severity = "minor"
        audit_finding_a.linked_capa = None
        assert audit_finding_a.requires_capa is False

        audit_finding_a.severity = "major"
        assert audit_finding_a.requires_capa is True

        audit_finding_a.severity = "critical"
        assert audit_finding_a.requires_capa is True

    def test_auditmanagement_regulatory_inspection_host(self, inspection_host_a, tenant_a):
        """Verify RegulatoryInspectionHost calculations and properties."""
        assert inspection_host_a.number.startswith("QHST-")
        assert inspection_host_a.tenant == tenant_a
        assert str(inspection_host_a) == f"{inspection_host_a.number} - {inspection_host_a.agency_name} ({inspection_host_a.inspection_title})"

        assert inspection_host_a.is_active is True
        assert inspection_host_a.pending_requests_count == 2
        # 10 / 12 * 100 = 83%
        assert inspection_host_a.fulfillment_rate == 83

    def test_auditmanagement_unique_constraints(self, audit_program_a, tenant_a, admin_user):
        """Verify database composite uniqueness constraints on (tenant, number)."""
        with pytest.raises(IntegrityError):
            AuditProgram.objects.create(
                tenant=tenant_a,
                number=audit_program_a.number,
                title="Duplicate Program Number",
                program_year=2026,
                program_type="internal_qms",
                risk_basis="low_risk_annual",
                scope_description="Duplicate scope",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                program_manager=admin_user,
            )
