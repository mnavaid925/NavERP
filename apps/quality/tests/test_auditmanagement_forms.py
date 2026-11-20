"""Unit tests for Quality Management Sub-module 12.11 Audit Management forms.

Tests forms:
- AuditProgramForm
- QualityAuditForm
- AuditFindingForm
- AuditFindingResponseForm
- RegulatoryInspectionHostForm
- InspectionLogRequestForm
"""
from datetime import date, timedelta
import pytest

from apps.quality.forms import (
    AuditProgramForm,
    QualityAuditForm,
    AuditFindingForm,
    AuditFindingResponseForm,
    RegulatoryInspectionHostForm,
    InspectionLogRequestForm,
)


@pytest.mark.django_db
class TestAuditManagementForms:
    """Test validation logic, tenant scoping, reject_foreign, and security exclusions."""

    def test_auditmanagement_audit_program_form_valid(self, tenant_a, admin_user):
        """Verify AuditProgramForm validates correct input and tenant scopes user FKs."""
        data = {
            "title": "FY2027 Quality Audit Program",
            "program_year": 2027,
            "program_type": "internal_qms",
            "risk_basis": "low_risk_annual",
            "scope_description": "Comprehensive internal quality audits.",
            "start_date": date(2027, 1, 1),
            "end_date": date(2027, 12, 31),
            "allocated_budget_hours": 320,
            "program_manager": admin_user.pk,
            "notes": "Valid program test.",
        }
        form = AuditProgramForm(data=data, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_auditmanagement_audit_program_form_date_validation(self, tenant_a, admin_user):
        """Verify end_date < start_date raises validation error."""
        data = {
            "title": "Invalid Date Program",
            "program_year": 2026,
            "program_type": "internal_qms",
            "risk_basis": "low_risk_annual",
            "scope_description": "Invalid dates",
            "start_date": date(2026, 12, 31),
            "end_date": date(2026, 1, 1),
            "allocated_budget_hours": 100,
            "program_manager": admin_user.pk,
        }
        form = AuditProgramForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "end_date" in form.errors

    def test_auditmanagement_audit_program_form_reject_foreign(self, tenant_a, admin_b):
        """Verify cross-tenant program_manager is rejected."""
        data = {
            "title": "Cross Tenant Manager Program",
            "program_year": 2026,
            "program_type": "internal_qms",
            "risk_basis": "low_risk_annual",
            "scope_description": "Testing reject_foreign",
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
            "program_manager": admin_b.pk,
        }
        form = AuditProgramForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "program_manager" in form.errors

    def test_auditmanagement_audit_program_form_excludes_system_fields(self):
        """Verify tenant, number, and status are strictly excluded from AuditProgramForm."""
        for field in ("tenant", "number", "status"):
            assert field not in AuditProgramForm.Meta.fields

    def test_auditmanagement_quality_audit_form_valid(self, tenant_a, audit_program_a, admin_user, quality_department):
        """Verify QualityAuditForm validates with tenant scoping."""
        data = {
            "program": audit_program_a.pk,
            "title": "ISO 13485 Documentation Audit",
            "audit_type": "internal_system",
            "audit_method": "on_site",
            "standard_framework": "iso_13485_2016",
            "target_org_unit": quality_department.pk,
            "lead_auditor": admin_user.pk,
            "planned_start_date": date(2026, 6, 1),
            "planned_end_date": date(2026, 6, 5),
            "scope_objectives": "Verify compliance with ISO 13485 Section 4.",
        }
        form = QualityAuditForm(data=data, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_auditmanagement_quality_audit_form_auditor_independence(self, tenant_a, audit_program_a, admin_user):
        """Verify auditor independence: lead auditor cannot audit their own lead role."""
        data = {
            "program": audit_program_a.pk,
            "title": "Self Audit Attempt",
            "audit_type": "internal_system",
            "audit_method": "on_site",
            "standard_framework": "iso_13485_2016",
            "lead_auditor": admin_user.pk,
            "auditee_lead": admin_user.pk,
            "planned_start_date": date(2026, 6, 1),
            "planned_end_date": date(2026, 6, 5),
            "scope_objectives": "Self-audit",
        }
        form = QualityAuditForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "auditee_lead" in form.errors
        assert "independence" in str(form.errors["auditee_lead"]).lower()

    def test_auditmanagement_quality_audit_form_excludes_workflow_fields(self):
        """Verify status and outcome are excluded from form to prevent mass-assignment bypass."""
        for field in ("tenant", "number", "status", "outcome"):
            assert field not in QualityAuditForm.Meta.fields

    def test_auditmanagement_audit_finding_form_valid(self, tenant_a, quality_audit_a, admin_user, quality_department):
        """Verify AuditFindingForm validates correctly."""
        data = {
            "audit": quality_audit_a.pk,
            "finding_number_in_audit": 1,
            "title": "Document retention policy gap",
            "severity": "minor",
            "standard_clause": "ISO 13485:2016 §4.2.5",
            "requirement_statement": "Records shall be maintained for device lifetime.",
            "condition_evidence": "SOP-DOC-01 states 5 years rather than lifetime.",
            "audited_org_unit": quality_department.pk,
            "assignee": admin_user.pk,
            "response_due_date": date(2026, 7, 1),
        }
        form = AuditFindingForm(data=data, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_auditmanagement_audit_finding_form_excludes_workflow_fields(self):
        """Verify status, closure_notes, and verification fields are excluded."""
        for field in ("tenant", "number", "status", "closure_notes", "closure_verified_by", "closed_date"):
            assert field not in AuditFindingForm.Meta.fields

    def test_auditmanagement_audit_finding_response_form(self):
        """Verify AuditFindingResponseForm binds and validates remediation fields."""
        data = {
            "containment_action": "Quarantine old document revisions immediately.",
            "root_cause_summary": "Template omitted regulatory lifetime clause.",
            "corrective_action_plan": "Update SOP-DOC-01 and retrain document coordinators.",
        }
        form = AuditFindingResponseForm(data=data)
        assert form.is_valid(), form.errors
        assert form.cleaned_data["containment_action"] == data["containment_action"]

    def test_auditmanagement_regulatory_inspection_host_form_valid(self, tenant_a, quality_audit_a, admin_user):
        """Verify RegulatoryInspectionHostForm validates with proper tenant scoping."""
        data = {
            "audit": quality_audit_a.pk,
            "inspection_title": "ISO 13485 Notified Body Surveillance",
            "agency_or_body": "iso_notified_body",
            "agency_name": "BSI Group The Netherlands",
            "lead_inspector_name": "Lead Auditor Maria van Dijk",
            "inspection_purpose": "routine_surveillance",
            "announcement_status": "announced",
            "scheduled_start_date": date(2026, 9, 1),
            "scheduled_end_date": date(2026, 9, 4),
            "front_room_lead": admin_user.pk,
            "back_room_lead": admin_user.pk,
            "war_room_location": "Conference Room 101",
            "status": "preparation",
            "observations_count": 0,
            "formal_outcome": "pending",
        }
        form = RegulatoryInspectionHostForm(data=data, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_auditmanagement_regulatory_inspection_host_form_excludes_debrief(self):
        """Verify daily_summary_notes is excluded to protect debrief stream from overwrite."""
        for field in ("tenant", "number", "daily_summary_notes", "requests_logged_count", "requests_fulfilled_count"):
            assert field not in RegulatoryInspectionHostForm.Meta.fields

    def test_auditmanagement_inspection_log_request_form(self, tenant_a, admin_user):
        """Verify InspectionLogRequestForm validates document requests."""
        data = {
            "request_description": "Provide training records for cleanroom operators in Line 3.",
            "assigned_sme": admin_user.pk,
            "priority": "urgent",
        }
        form = InspectionLogRequestForm(data=data, tenant=tenant_a)
        assert form.is_valid(), form.errors
