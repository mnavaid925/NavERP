"""
Unit tests for apps/quality forms (Sub-module 12.6: Supplier & Vendor Quality Management).

Covers:
- SupplierQualificationAuditForm:
  - System field exclusions (tenant, number, created_at, updated_at).
  - Valid submission creates and updates record with proper fields.
  - Score boundary validations (0-100).
  - Date ordering validations (next_audit_due_date >= audit_date).
  - Foreign key scoping (supplier, lead_auditor, quality_agreement scoped to tenant).
  - Inactive users exclusion from lead_auditor queryset.
  - Cross-tenant FK rejection via reject_foreign.
  - Widgets and CSS styling classes.
- SupplierQualityScorecardForm:
  - System field exclusions (tenant, number, overall_score, grade, created_at, updated_at).
  - Valid submission with automated composite score computation.
  - Dimension scores range validations (0-100 for all 5 dimensions).
  - Receiving counts validation (lots_rejected <= total_lots_received).
  - Period date validation (period_end >= period_start).
  - Manual override validation (justification required when is_manual_override=True).
  - Status transition protection (clean_status blocks publishing directly from form).
  - Foreign key scoping (supplier, evaluated_by scoped to tenant).
  - Cross-tenant FK rejection via reject_foreign.
  - Widgets and CSS styling classes.
- SupplierCorrectiveActionForm:
  - System field exclusions (tenant, number, closed_at, created_at, updated_at).
  - Valid submission creating and updating SCARs.
  - Date validation (response_due_date >= issued_date, containment_due_date >= issued_date).
  - Containment action validation when in containment active status.
  - Status transition protection (clean_status blocks closing directly from form).
  - Foreign key scoping (supplier, purchase_order, non_conformance, qualification_audit, internal_capa, users).
  - Cross-tenant FK rejection via reject_foreign.
  - Widgets and CSS styling classes.
- SupplierChangeNotificationForm:
  - System field exclusions (tenant, number, disposition, approved_by, disposition_notes, disposition_date, created_at, updated_at).
  - Valid submission creating and updating SCNs.
  - Form-Fit-Function (FFF) impact validation (notes required when affects_form_fit_function=True).
  - Foreign key scoping (supplier, design_project, requalification_audit, evaluated_by).
  - Cross-tenant FK rejection via reject_foreign.
  - Widgets and CSS styling classes.
- Cross-Cutting Form Invariants:
  - Empty tenant instantiation safety across all 4 forms.
  - Required fields validations on blank submissions.
"""

from datetime import timedelta
from decimal import Decimal
import pytest
from django import forms
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import Party, PartyRole
from apps.quality.forms import (
    SupplierChangeNotificationForm,
    SupplierCorrectiveActionForm,
    SupplierQualificationAuditForm,
    SupplierQualityScorecardForm,
)
from apps.quality.models import (
    CapaInvestigation,
    ControlledDocument,
    DesignProject,
    SupplierChangeNotification,
    SupplierCorrectiveAction,
    SupplierQualificationAudit,
    SupplierQualityScorecard,
)
from apps.scm.models import NonConformance, PurchaseOrder

pytestmark = pytest.mark.django_db


# =============================================================================
# Helper Utilities (Prefix: _supplierquality_*)
# =============================================================================

def _supplierquality_pk(val):
    """Return pk if val is a model instance, or val itself if scalar / None."""
    if hasattr(val, "pk"):
        return val.pk
    return val


def _supplierquality_date(days_offset=0):
    """Return an ISO formatted date string relative to today."""
    return (timezone.now().date() + timedelta(days=days_offset)).isoformat()


def _supplierquality_audit_base_data(supplier, auditor=None, doc=None, **extra):
    """Build valid baseline POST dictionary for SupplierQualificationAuditForm."""
    data = {
        "supplier": _supplierquality_pk(supplier),
        "assessment_type": "initial_qualification",
        "criticality_tier": "critical",
        "audit_method": "on_site",
        "qualification_status": "approved",
        "scope_commodities": "Medical catheters, surgical tubing",
        "score": "95.00",
        "audit_result": "passed",
        "critical_findings": 0,
        "major_findings": 1,
        "minor_findings": 2,
        "lead_auditor": _supplierquality_pk(auditor) if auditor else "",
        "audit_date": _supplierquality_date(-10),
        "qualified_date": _supplierquality_date(-5),
        "next_audit_due_date": _supplierquality_date(355),
        "certificate_expiry_date": _supplierquality_date(720),
        "dock_to_stock_eligible": True,
        "skip_lot_approved": False,
        "requires_coa": True,
        "quality_agreement": _supplierquality_pk(doc) if doc else "",
        "notes": "Facility complies with ISO 13485 cleanroom standards.",
    }
    data.update(extra)
    return data


def _supplierquality_scorecard_base_data(supplier, evaluator=None, **extra):
    """Build valid baseline POST dictionary for SupplierQualityScorecardForm."""
    data = {
        "supplier": _supplierquality_pk(supplier),
        "cadence": "quarterly",
        "period_start": _supplierquality_date(-90),
        "period_end": _supplierquality_date(0),
        "status": "draft",
        "lot_acceptance_rate_score": "95.00",
        "defect_ppm_score": "92.00",
        "scar_responsiveness_score": "90.00",
        "audit_compliance_score": "88.00",
        "documentation_coa_score": "96.00",
        "total_lots_received": 100,
        "lots_rejected": 2,
        "total_scars_issued": 1,
        "evaluated_by": _supplierquality_pk(evaluator) if evaluator else "",
        "is_manual_override": False,
        "override_justification": "",
        "evaluation_notes": "Consistent delivery quality and fast response times.",
    }
    data.update(extra)
    return data


def _supplierquality_scar_base_data(supplier, issued_by=None, audit=None, **extra):
    """Build valid baseline POST dictionary for SupplierCorrectiveActionForm."""
    data = {
        "supplier": _supplierquality_pk(supplier),
        "title": "Cannula Hub Mold Flash Defect",
        "severity": "major",
        "status": "draft",
        "defect_summary": "Flash observed around connector hub exceeding 0.1mm tolerance.",
        "affected_item_code": "HUB-CAN-002",
        "affected_item_name": "Luer-Lock Cannula Hub",
        "affected_lots": "LOT-2026-B81",
        "purchase_order": "",
        "non_conformance": "",
        "qualification_audit": _supplierquality_pk(audit) if audit else "",
        "internal_capa": "",
        "issued_date": _supplierquality_date(-2),
        "response_due_date": _supplierquality_date(12),
        "issued_by": _supplierquality_pk(issued_by) if issued_by else "",
        "containment_action": "Quarantine affected batch B81 in inspection cage.",
        "containment_due_date": _supplierquality_date(2),
        "containment_verified_at": "",
        "root_cause_summary": "Worn parting line shutoff on mold cavity #4.",
        "root_cause_category": "tooling_equipment",
        "vendor_investigation_details": "Tooling dismantled and cavity #4 insert found deformed.",
        "corrective_action_plan": "Replace cavity insert and re-measure first article samples.",
        "preventive_action_plan": "Implement preventive cavity maintenance at 25k cycles.",
        "implementation_due_date": _supplierquality_date(30),
        "implemented_at": "",
        "effectiveness_due_date": _supplierquality_date(60),
        "effectiveness_method": "Inspect next 3 consecutive shipments for zero flash.",
        "effectiveness_results": "",
        "is_effective": None,
        "verified_by": "",
    }
    data.update(extra)
    return data


def _supplierquality_scn_base_data(supplier, evaluator=None, audit=None, project=None, **extra):
    """Build valid baseline POST dictionary for SupplierChangeNotificationForm."""
    data = {
        "supplier": _supplierquality_pk(supplier),
        "title": "Polymer Resin Supplier Relocation",
        "supplier_scn_number": "PCN-2026-901",
        "change_category": "facility_location",
        "risk_level": "level_2_moderate",
        "status": "received",
        "description": "Supplier resin synthesis moving from Plant 1 to Plant 2.",
        "proposed_effective_date": _supplierquality_date(45),
        "first_affected_lot": "LOT-RES-701",
        "affected_item_code": "RES-PEEK-01",
        "affected_item_name": "Medical Grade PEEK Granules",
        "affects_form_fit_function": False,
        "requires_requalification": False,
        "requires_design_change": False,
        "requires_regulatory_filing": False,
        "requires_customer_notification": False,
        "samples_required": True,
        "impact_assessment_notes": "No formulation changes. Equivalency validation testing underway.",
        "design_project": _supplierquality_pk(project) if project else "",
        "requalification_audit": _supplierquality_pk(audit) if audit else "",
        "evaluated_by": _supplierquality_pk(evaluator) if evaluator else "",
    }
    data.update(extra)
    return data


# =============================================================================
# 1. SupplierQualificationAuditForm Tests
# =============================================================================

def test_supplierquality_audit_form_system_field_exclusion(tenant_a, supplier_party_a, admin_user):
    """Verify tenant, number, created_at, updated_at are excluded from SupplierQualificationAuditForm."""
    form = SupplierQualificationAuditForm(tenant=tenant_a)
    forbidden_fields = ["tenant", "number", "created_at", "updated_at"]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from SupplierQualificationAuditForm"

    # Malicious injection in POST data must not alter system properties
    malicious_data = _supplierquality_audit_base_data(
        supplier_party_a,
        admin_user,
        tenant=tenant_a.pk,
        number="QSQA-HACKED-9999",
        created_at=_supplierquality_date(-100),
    )
    bound_form = SupplierQualificationAuditForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QSQA-HACKED-9999"


def test_supplierquality_audit_form_valid_submission_creates_record(tenant_a, supplier_party_a, admin_user, doc_a):
    """Verify valid form submission creates a persisted record with QSQA- auto-number."""
    data = _supplierquality_audit_base_data(
        supplier_party_a,
        auditor=admin_user,
        doc=doc_a,
        score="94.75",
        notes="Audit conducted on-site in cleanroom suite A.",
    )
    form = SupplierQualificationAuditForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    audit = form.save(commit=False)
    audit.tenant = tenant_a
    audit.save()

    assert audit.pk is not None
    assert audit.number.startswith("QSQA-")
    assert audit.supplier == supplier_party_a
    assert audit.lead_auditor == admin_user
    assert audit.quality_agreement == doc_a
    assert audit.score == Decimal("94.75")
    assert audit.dock_to_stock_eligible is True
    assert audit.requires_coa is True


def test_supplierquality_audit_form_valid_submission_updates_record(tenant_a, audit_a, admin_user):
    """Verify valid form edit successfully updates existing audit instance."""
    data = _supplierquality_audit_base_data(
        audit_a.supplier,
        auditor=admin_user,
        score="98.50",
        notes="Re-audit verified complete closure of past findings.",
        audit_result="passed",
    )
    form = SupplierQualificationAuditForm(data=data, instance=audit_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    updated = form.save()

    assert updated.pk == audit_a.pk
    assert updated.score == Decimal("98.50")
    assert "complete closure" in updated.notes


def test_supplierquality_audit_form_score_boundary_validation(tenant_a, supplier_party_a):
    """Verify compliance score is strictly bounded between 0 and 100."""
    # Negative score
    bad_neg = _supplierquality_audit_base_data(supplier_party_a, score="-1.00")
    form_neg = SupplierQualificationAuditForm(data=bad_neg, tenant=tenant_a)
    assert not form_neg.is_valid()
    assert "score" in form_neg.errors

    # Over 100 score
    bad_over = _supplierquality_audit_base_data(supplier_party_a, score="100.01")
    form_over = SupplierQualificationAuditForm(data=bad_over, tenant=tenant_a)
    assert not form_over.is_valid()
    assert "score" in form_over.errors

    # Valid boundaries: 0.00 and 100.00
    valid_zero = _supplierquality_audit_base_data(supplier_party_a, score="0.00")
    form_zero = SupplierQualificationAuditForm(data=valid_zero, tenant=tenant_a)
    assert form_zero.is_valid(), form_zero.errors

    valid_hundred = _supplierquality_audit_base_data(supplier_party_a, score="100.00")
    form_hundred = SupplierQualificationAuditForm(data=valid_hundred, tenant=tenant_a)
    assert form_hundred.is_valid(), form_hundred.errors

    # Blank / None score is optional and valid
    valid_blank = _supplierquality_audit_base_data(supplier_party_a, score="")
    form_blank = SupplierQualificationAuditForm(data=valid_blank, tenant=tenant_a)
    assert form_blank.is_valid(), form_blank.errors


def test_supplierquality_audit_form_next_audit_due_date_validation(tenant_a, supplier_party_a):
    """Verify next_audit_due_date cannot precede audit_date."""
    # next due date earlier than audit date
    bad_data = _supplierquality_audit_base_data(
        supplier_party_a,
        audit_date="2026-11-20",
        next_audit_due_date="2026-11-19",
    )
    form = SupplierQualificationAuditForm(data=bad_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "next_audit_due_date" in form.errors

    # same date is accepted
    same_data = _supplierquality_audit_base_data(
        supplier_party_a,
        audit_date="2026-11-20",
        next_audit_due_date="2026-11-20",
    )
    form_same = SupplierQualificationAuditForm(data=same_data, tenant=tenant_a)
    assert form_same.is_valid(), form_same.errors

    # future date is accepted
    ok_data = _supplierquality_audit_base_data(
        supplier_party_a,
        audit_date="2026-11-20",
        next_audit_due_date="2027-11-20",
    )
    form_ok = SupplierQualificationAuditForm(data=ok_data, tenant=tenant_a)
    assert form_ok.is_valid(), form_ok.errors


def test_supplierquality_audit_form_foreign_key_scoping(tenant_a, tenant_b, supplier_party_a, supplier_party_b, admin_user, admin_b, doc_a):
    """Verify supplier, lead_auditor, and quality_agreement querysets are strictly tenant-scoped."""
    form = SupplierQualificationAuditForm(tenant=tenant_a)

    supplier_pks = set(form.fields["supplier"].queryset.values_list("pk", flat=True))
    assert supplier_party_a.pk in supplier_pks
    assert supplier_party_b.pk not in supplier_pks

    auditor_pks = set(form.fields["lead_auditor"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in auditor_pks
    assert admin_b.pk not in auditor_pks

    doc_pks = set(form.fields["quality_agreement"].queryset.values_list("pk", flat=True))
    assert doc_a.pk in doc_pks


def test_supplierquality_audit_form_inactive_user_excluded(tenant_a, supplier_party_a):
    """Verify inactive users are excluded from the lead_auditor queryset."""
    inactive_user = User.objects.create_user(
        username="inactive_auditor@acme.com",
        email="inactive_auditor@acme.com",
        password="password123",
        tenant=tenant_a,
        is_active=False,
    )
    form = SupplierQualificationAuditForm(tenant=tenant_a)
    auditor_pks = set(form.fields["lead_auditor"].queryset.values_list("pk", flat=True))
    assert inactive_user.pk not in auditor_pks


def test_supplierquality_audit_form_cross_tenant_fk_rejection(tenant_a, tenant_b, supplier_party_a, supplier_party_b, admin_user, admin_b, quality_doc_b):
    """Verify reject_foreign rejects foreign tenant supplier, lead_auditor, or quality agreement."""
    # Foreign supplier
    bad_supplier = _supplierquality_audit_base_data(supplier_party_b, auditor=admin_user)
    form_supp = SupplierQualificationAuditForm(data=bad_supplier, tenant=tenant_a)
    assert not form_supp.is_valid()
    assert "supplier" in form_supp.errors

    # Foreign lead auditor
    bad_auditor = _supplierquality_audit_base_data(supplier_party_a, auditor=admin_b)
    form_aud = SupplierQualificationAuditForm(data=bad_auditor, tenant=tenant_a)
    assert not form_aud.is_valid()
    assert "lead_auditor" in form_aud.errors

    # Foreign quality agreement doc
    bad_doc = _supplierquality_audit_base_data(supplier_party_a, auditor=admin_user, doc=quality_doc_b)
    form_doc = SupplierQualificationAuditForm(data=bad_doc, tenant=tenant_a)
    assert not form_doc.is_valid()
    assert "quality_agreement" in form_doc.errors


def test_supplierquality_audit_form_widgets_and_css(tenant_a):
    """Verify CSS classes and form widget configuration for SupplierQualificationAuditForm."""
    form = SupplierQualificationAuditForm(tenant=tenant_a)
    assert "form-select" in form.fields["supplier"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["assessment_type"].widget.attrs.get("class", "")
    assert "form-input" in form.fields["score"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["scope_commodities"].widget.attrs.get("class", "")
    assert "form-checkbox" in form.fields["dock_to_stock_eligible"].widget.attrs.get("class", "")


# =============================================================================
# 2. SupplierQualityScorecardForm Tests
# =============================================================================

def test_supplierquality_scorecard_form_system_field_exclusion(tenant_a, supplier_party_a):
    """Verify tenant, number, overall_score, grade, created_at, updated_at are excluded from form fields."""
    form = SupplierQualityScorecardForm(tenant=tenant_a)
    forbidden_fields = ["tenant", "number", "overall_score", "grade", "created_at", "updated_at"]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from SupplierQualityScorecardForm"

    # Malicious parameters in POST data must not override computed metrics
    malicious_data = _supplierquality_scorecard_base_data(
        supplier_party_a,
        tenant=tenant_a.pk,
        number="QSSC-HACKED-001",
        overall_score="99.99",
        grade="grade_a",
    )
    bound_form = SupplierQualityScorecardForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QSSC-HACKED-001"


def test_supplierquality_scorecard_form_valid_submission_creates_record(tenant_a, supplier_party_a, admin_user):
    """Verify valid form submission creates scorecard and calculates composite score on save."""
    data = _supplierquality_scorecard_base_data(
        supplier_party_a,
        evaluator=admin_user,
        lot_acceptance_rate_score="90.00",
        defect_ppm_score="90.00",
        scar_responsiveness_score="90.00",
        audit_compliance_score="90.00",
        documentation_coa_score="90.00",
        total_lots_received=50,
        lots_rejected=1,
    )
    form = SupplierQualityScorecardForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    scorecard = form.save(commit=False)
    scorecard.tenant = tenant_a
    scorecard.save()

    assert scorecard.pk is not None
    assert scorecard.number.startswith("QSSC-")
    assert scorecard.supplier == supplier_party_a
    assert scorecard.evaluated_by == admin_user
    assert scorecard.overall_score == Decimal("90.00")
    assert scorecard.grade == "grade_a"


def test_supplierquality_scorecard_form_valid_submission_updates_record(tenant_a, scorecard_a, admin_user):
    """Verify valid form edit successfully updates existing scorecard."""
    data = _supplierquality_scorecard_base_data(
        scorecard_a.supplier,
        evaluator=admin_user,
        status="under_review",
        lot_acceptance_rate_score="85.00",
        defect_ppm_score="85.00",
        scar_responsiveness_score="85.00",
        audit_compliance_score="85.00",
        documentation_coa_score="85.00",
        evaluation_notes="Updated evaluation notes after supplier response review.",
    )
    form = SupplierQualityScorecardForm(data=data, instance=scorecard_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    updated = form.save()

    assert updated.pk == scorecard_a.pk
    assert updated.status == "under_review"
    assert updated.overall_score == Decimal("85.00")
    assert updated.grade == "grade_b"


def test_supplierquality_scorecard_form_dimension_scores_validation(tenant_a, supplier_party_a):
    """Verify all 5 quality dimension scores must be within 0-100 range."""
    dimension_fields = [
        "lot_acceptance_rate_score",
        "defect_ppm_score",
        "scar_responsiveness_score",
        "audit_compliance_score",
        "documentation_coa_score",
    ]

    for field in dimension_fields:
        # Negative value
        bad_data_neg = _supplierquality_scorecard_base_data(supplier_party_a, **{field: "-0.50"})
        form_neg = SupplierQualityScorecardForm(data=bad_data_neg, tenant=tenant_a)
        assert not form_neg.is_valid()
        assert field in form_neg.errors

        # Exceeding 100
        bad_data_over = _supplierquality_scorecard_base_data(supplier_party_a, **{field: "105.00"})
        form_over = SupplierQualityScorecardForm(data=bad_data_over, tenant=tenant_a)
        assert not form_over.is_valid()
        assert field in form_over.errors


def test_supplierquality_scorecard_form_receiving_counts_validation(tenant_a, supplier_party_a):
    """Verify lots_rejected cannot exceed total_lots_received."""
    # lots_rejected > total_lots_received
    bad_counts = _supplierquality_scorecard_base_data(
        supplier_party_a,
        total_lots_received=25,
        lots_rejected=30,
    )
    form = SupplierQualityScorecardForm(data=bad_counts, tenant=tenant_a)
    assert not form.is_valid()
    assert "lots_rejected" in form.errors

    # lots_rejected <= total_lots_received is accepted
    ok_counts = _supplierquality_scorecard_base_data(
        supplier_party_a,
        total_lots_received=25,
        lots_rejected=25,
    )
    form_ok = SupplierQualityScorecardForm(data=ok_counts, tenant=tenant_a)
    assert form_ok.is_valid(), form_ok.errors


def test_supplierquality_scorecard_form_period_validation(tenant_a, supplier_party_a):
    """Verify period_end date cannot precede period_start date."""
    bad_period = _supplierquality_scorecard_base_data(
        supplier_party_a,
        period_start="2026-09-30",
        period_end="2026-09-01",
    )
    form = SupplierQualityScorecardForm(data=bad_period, tenant=tenant_a)
    assert not form.is_valid()
    assert "period_end" in form.errors

    ok_period = _supplierquality_scorecard_base_data(
        supplier_party_a,
        period_start="2026-09-01",
        period_end="2026-09-30",
    )
    form_ok = SupplierQualityScorecardForm(data=ok_period, tenant=tenant_a)
    assert form_ok.is_valid(), form_ok.errors


def test_supplierquality_scorecard_form_manual_override_validation(tenant_a, supplier_party_a):
    """Verify override_justification is mandatory when manual override is enabled."""
    # Manual override enabled with empty justification
    bad_override = _supplierquality_scorecard_base_data(
        supplier_party_a,
        is_manual_override=True,
        override_justification="   ",
    )
    form = SupplierQualityScorecardForm(data=bad_override, tenant=tenant_a)
    assert not form.is_valid()
    assert "override_justification" in form.errors

    # Manual override enabled with valid justification
    ok_override = _supplierquality_scorecard_base_data(
        supplier_party_a,
        is_manual_override=True,
        override_justification="Executive override approved by Quality Director due to raw material supply disruption.",
    )
    form_ok = SupplierQualityScorecardForm(data=ok_override, tenant=tenant_a)
    assert form_ok.is_valid(), form_ok.errors


def test_supplierquality_scorecard_form_clean_status_published_blocked(tenant_a, supplier_party_a):
    """Verify scorecards cannot be published directly via form submission."""
    data = _supplierquality_scorecard_base_data(supplier_party_a, status="published")
    form = SupplierQualityScorecardForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "status" in form.errors


def test_supplierquality_scorecard_form_foreign_key_scoping(tenant_a, tenant_b, supplier_party_a, supplier_party_b, admin_user, admin_b):
    """Verify supplier and evaluated_by querysets are strictly tenant-scoped."""
    form = SupplierQualityScorecardForm(tenant=tenant_a)

    supp_pks = set(form.fields["supplier"].queryset.values_list("pk", flat=True))
    assert supplier_party_a.pk in supp_pks
    assert supplier_party_b.pk not in supp_pks

    user_pks = set(form.fields["evaluated_by"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in user_pks
    assert admin_b.pk not in user_pks


def test_supplierquality_scorecard_form_cross_tenant_fk_rejection(tenant_a, tenant_b, supplier_party_a, supplier_party_b, admin_user, admin_b):
    """Verify reject_foreign rejects foreign tenant supplier or evaluator."""
    bad_supp = _supplierquality_scorecard_base_data(supplier_party_b, evaluator=admin_user)
    form_supp = SupplierQualityScorecardForm(data=bad_supp, tenant=tenant_a)
    assert not form_supp.is_valid()
    assert "supplier" in form_supp.errors

    bad_user = _supplierquality_scorecard_base_data(supplier_party_a, evaluator=admin_b)
    form_user = SupplierQualityScorecardForm(data=bad_user, tenant=tenant_a)
    assert not form_user.is_valid()
    assert "evaluated_by" in form_user.errors


def test_supplierquality_scorecard_form_widgets_and_css(tenant_a):
    """Verify CSS classes and widget types for SupplierQualityScorecardForm."""
    form = SupplierQualityScorecardForm(tenant=tenant_a)
    assert "form-select" in form.fields["supplier"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["cadence"].widget.attrs.get("class", "")
    assert "form-input" in form.fields["lot_acceptance_rate_score"].widget.attrs.get("class", "")
    assert "form-checkbox" in form.fields["is_manual_override"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["override_justification"].widget.attrs.get("class", "")


# =============================================================================
# 3. SupplierCorrectiveActionForm Tests
# =============================================================================

def test_supplierquality_scar_form_system_field_exclusion(tenant_a, supplier_party_a):
    """Verify tenant, number, closed_at, created_at, updated_at are excluded from form fields."""
    form = SupplierCorrectiveActionForm(tenant=tenant_a)
    forbidden_fields = ["tenant", "number", "closed_at", "created_at", "updated_at"]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from SupplierCorrectiveActionForm"

    # Malicious injection
    malicious_data = _supplierquality_scar_base_data(
        supplier_party_a,
        tenant=tenant_a.pk,
        number="QSCA-HACKED-001",
        closed_at=_supplierquality_date(0),
    )
    bound_form = SupplierCorrectiveActionForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QSCA-HACKED-001"
    assert instance.closed_at is None


def test_supplierquality_scar_form_valid_submission_creates_record(tenant_a, supplier_party_a, admin_user, audit_a):
    """Verify valid form submission creates persisted SCAR with QSCA- number."""
    data = _supplierquality_scar_base_data(
        supplier_party_a,
        issued_by=admin_user,
        audit=audit_a,
        severity="critical",
        title="Excessive Particulate Contamination in Vials",
        defect_summary="Glass particulate count exceeded 5 particles per mL threshold in receiving inspection.",
    )
    form = SupplierCorrectiveActionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    scar = form.save(commit=False)
    scar.tenant = tenant_a
    scar.save()

    assert scar.pk is not None
    assert scar.number.startswith("QSCA-")
    assert scar.supplier == supplier_party_a
    assert scar.qualification_audit == audit_a
    assert scar.severity == "critical"
    assert scar.issued_by == admin_user


def test_supplierquality_scar_form_valid_submission_updates_record(tenant_a, scar_a, admin_user):
    """Verify valid form edit successfully updates existing SCAR."""
    data = _supplierquality_scar_base_data(
        scar_a.supplier,
        issued_by=admin_user,
        status="rca_submitted",
        root_cause_summary="Vial washing rinse cycle nozzle pressure dropped below 2 bar.",
        root_cause_category="tooling_equipment",
        corrective_action_plan="Installed redundant pressure transducer and auto-cutoff valve.",
    )
    form = SupplierCorrectiveActionForm(data=data, instance=scar_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    updated = form.save()

    assert updated.pk == scar_a.pk
    assert updated.status == "rca_submitted"
    assert updated.root_cause_category == "tooling_equipment"
    assert "redundant pressure transducer" in updated.corrective_action_plan


def test_supplierquality_scar_form_response_due_date_validation(tenant_a, supplier_party_a):
    """Verify response_due_date cannot be earlier than issued_date."""
    bad_data = _supplierquality_scar_base_data(
        supplier_party_a,
        issued_date="2026-11-15",
        response_due_date="2026-11-10",
    )
    form = SupplierCorrectiveActionForm(data=bad_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "response_due_date" in form.errors

    ok_data = _supplierquality_scar_base_data(
        supplier_party_a,
        issued_date="2026-11-15",
        response_due_date="2026-11-25",
    )
    form_ok = SupplierCorrectiveActionForm(data=ok_data, tenant=tenant_a)
    assert form_ok.is_valid(), form_ok.errors


def test_supplierquality_scar_form_containment_due_date_validation(tenant_a, supplier_party_a):
    """Verify containment_due_date cannot precede issued_date."""
    bad_data = _supplierquality_scar_base_data(
        supplier_party_a,
        issued_date="2026-11-15",
        containment_due_date="2026-11-12",
    )
    form = SupplierCorrectiveActionForm(data=bad_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "containment_due_date" in form.errors


def test_supplierquality_scar_form_containment_status_validation(tenant_a, supplier_party_a):
    """Verify containment_action is mandatory when status is in containment phase."""
    bad_containment = _supplierquality_scar_base_data(
        supplier_party_a,
        status="containment_submitted",
        containment_action="   ",
    )
    form = SupplierCorrectiveActionForm(data=bad_containment, tenant=tenant_a)
    assert not form.is_valid()
    assert "containment_action" in form.errors

    ok_containment = _supplierquality_scar_base_data(
        supplier_party_a,
        status="containment_submitted",
        containment_action="Physical quarantine hold placed on all remaining inventory in Bay 3.",
    )
    form_ok = SupplierCorrectiveActionForm(data=ok_containment, tenant=tenant_a)
    assert form_ok.is_valid(), form_ok.errors


def test_supplierquality_scar_form_clean_status_closed_blocked(tenant_a, supplier_party_a):
    """Verify SCARs cannot be closed directly via form submission."""
    data = _supplierquality_scar_base_data(supplier_party_a, status="closed")
    form = SupplierCorrectiveActionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "status" in form.errors


def test_supplierquality_scar_form_foreign_key_scoping(tenant_a, tenant_b, supplier_party_a, supplier_party_b, audit_a, audit_b, admin_user, admin_b):
    """Verify all foreign key querysets are strictly tenant-scoped."""
    form = SupplierCorrectiveActionForm(tenant=tenant_a)

    supp_pks = set(form.fields["supplier"].queryset.values_list("pk", flat=True))
    assert supplier_party_a.pk in supp_pks
    assert supplier_party_b.pk not in supp_pks

    audit_pks = set(form.fields["qualification_audit"].queryset.values_list("pk", flat=True))
    assert audit_a.pk in audit_pks
    assert audit_b.pk not in audit_pks

    user_pks = set(form.fields["issued_by"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in user_pks
    assert admin_b.pk not in user_pks


def test_supplierquality_scar_form_cross_tenant_fk_rejection(tenant_a, tenant_b, supplier_party_a, supplier_party_b, audit_a, audit_b, admin_user, admin_b):
    """Verify reject_foreign rejects foreign tenant entities on SCAR form."""
    # Foreign supplier
    bad_supp = _supplierquality_scar_base_data(supplier_party_b, issued_by=admin_user)
    form_supp = SupplierCorrectiveActionForm(data=bad_supp, tenant=tenant_a)
    assert not form_supp.is_valid()
    assert "supplier" in form_supp.errors

    # Foreign qualification audit
    bad_audit = _supplierquality_scar_base_data(supplier_party_a, audit=audit_b, issued_by=admin_user)
    form_aud = SupplierCorrectiveActionForm(data=bad_audit, tenant=tenant_a)
    assert not form_aud.is_valid()
    assert "qualification_audit" in form_aud.errors

    # Foreign user
    bad_user = _supplierquality_scar_base_data(supplier_party_a, issued_by=admin_b)
    form_user = SupplierCorrectiveActionForm(data=bad_user, tenant=tenant_a)
    assert not form_user.is_valid()
    assert "issued_by" in form_user.errors


def test_supplierquality_scar_form_widgets_and_css(tenant_a):
    """Verify CSS classes and widget types for SupplierCorrectiveActionForm."""
    form = SupplierCorrectiveActionForm(tenant=tenant_a)
    assert "form-select" in form.fields["supplier"].widget.attrs.get("class", "")
    assert "form-input" in form.fields["title"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["severity"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["defect_summary"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["containment_action"].widget.attrs.get("class", "")


# =============================================================================
# 4. SupplierChangeNotificationForm Tests
# =============================================================================

def test_supplierquality_scn_form_system_field_exclusion(tenant_a, supplier_party_a):
    """Verify tenant, number, disposition, approved_by, disposition_notes, disposition_date, created_at, updated_at are excluded."""
    form = SupplierChangeNotificationForm(tenant=tenant_a)
    forbidden_fields = [
        "tenant",
        "number",
        "disposition",
        "approved_by",
        "disposition_notes",
        "disposition_date",
        "created_at",
        "updated_at",
    ]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from SupplierChangeNotificationForm"

    # Malicious POST injection
    malicious_data = _supplierquality_scn_base_data(
        supplier_party_a,
        tenant=tenant_a.pk,
        number="QSCN-HACKED-001",
        disposition="approved",
        disposition_notes="Bypassing disposition governance via form injection.",
    )
    bound_form = SupplierChangeNotificationForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QSCN-HACKED-001"
    assert instance.disposition == "pending"


def test_supplierquality_scn_form_valid_submission_creates_record(tenant_a, supplier_party_a, admin_user, audit_a):
    """Verify valid form submission creates persisted SCN with QSCN- number."""
    data = _supplierquality_scn_base_data(
        supplier_party_a,
        evaluator=admin_user,
        audit=audit_a,
        title="Laser Cutting Tool Upgrade on Cannula Line",
        change_category="tooling_equipment",
        risk_level="level_2_moderate",
        description="Upgrading 200W fiber laser to 500W ultrafast picosecond laser for cleaner edge finish.",
    )
    form = SupplierChangeNotificationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    scn = form.save(commit=False)
    scn.tenant = tenant_a
    scn.save()

    assert scn.pk is not None
    assert scn.number.startswith("QSCN-")
    assert scn.supplier == supplier_party_a
    assert scn.change_category == "tooling_equipment"
    assert scn.risk_level == "level_2_moderate"
    assert scn.evaluated_by == admin_user
    assert scn.requalification_audit == audit_a


def test_supplierquality_scn_form_valid_submission_updates_record(tenant_a, scn_a, admin_user):
    """Verify valid form edit successfully updates existing SCN."""
    data = _supplierquality_scn_base_data(
        scn_a.supplier,
        evaluator=admin_user,
        title="Ultrasonic Bath Frequency Upgrade - Validation Samples Received",
        status="technical_evaluation",
        samples_required=True,
        impact_assessment_notes="Prototypes undergoing microscopic particulate evaluation.",
    )
    form = SupplierChangeNotificationForm(data=data, instance=scn_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    updated = form.save()

    assert updated.pk == scn_a.pk
    assert updated.status == "technical_evaluation"
    assert updated.samples_required is True
    assert "microscopic particulate" in updated.impact_assessment_notes


def test_supplierquality_scn_form_fff_impact_validation(tenant_a, supplier_party_a):
    """Verify impact_assessment_notes is mandatory when change affects form, fit, or function."""
    # FFF True with empty impact notes
    bad_fff = _supplierquality_scn_base_data(
        supplier_party_a,
        affects_form_fit_function=True,
        impact_assessment_notes="   ",
    )
    form = SupplierChangeNotificationForm(data=bad_fff, tenant=tenant_a)
    assert not form.is_valid()
    assert "impact_assessment_notes" in form.errors

    # FFF True with valid notes
    ok_fff = _supplierquality_scn_base_data(
        supplier_party_a,
        affects_form_fit_function=True,
        impact_assessment_notes="Tolerance changes on inner diameter impact mating connector fit. CAD model revision required.",
    )
    form_ok = SupplierChangeNotificationForm(data=ok_fff, tenant=tenant_a)
    assert form_ok.is_valid(), form_ok.errors

    # FFF False with empty notes is allowed
    ok_no_fff = _supplierquality_scn_base_data(
        supplier_party_a,
        affects_form_fit_function=False,
        impact_assessment_notes="",
    )
    form_no_fff = SupplierChangeNotificationForm(data=ok_no_fff, tenant=tenant_a)
    assert form_no_fff.is_valid(), form_no_fff.errors


def test_supplierquality_scn_form_foreign_key_scoping(tenant_a, tenant_b, supplier_party_a, supplier_party_b, audit_a, audit_b, admin_user, admin_b, design_project_a, design_project_b):
    """Verify supplier, design_project, requalification_audit, and evaluated_by are tenant-scoped."""
    form = SupplierChangeNotificationForm(tenant=tenant_a)

    supp_pks = set(form.fields["supplier"].queryset.values_list("pk", flat=True))
    assert supplier_party_a.pk in supp_pks
    assert supplier_party_b.pk not in supp_pks

    proj_pks = set(form.fields["design_project"].queryset.values_list("pk", flat=True))
    assert design_project_a.pk in proj_pks
    assert design_project_b.pk not in proj_pks

    audit_pks = set(form.fields["requalification_audit"].queryset.values_list("pk", flat=True))
    assert audit_a.pk in audit_pks
    assert audit_b.pk not in audit_pks

    user_pks = set(form.fields["evaluated_by"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in user_pks
    assert admin_b.pk not in user_pks


def test_supplierquality_scn_form_cross_tenant_fk_rejection(tenant_a, tenant_b, supplier_party_a, supplier_party_b, audit_a, audit_b, admin_user, admin_b, design_project_b):
    """Verify reject_foreign rejects foreign tenant entities on SCN form."""
    # Foreign supplier
    bad_supp = _supplierquality_scn_base_data(supplier_party_b, evaluator=admin_user)
    form_supp = SupplierChangeNotificationForm(data=bad_supp, tenant=tenant_a)
    assert not form_supp.is_valid()
    assert "supplier" in form_supp.errors

    # Foreign audit
    bad_audit = _supplierquality_scn_base_data(supplier_party_a, audit=audit_b, evaluator=admin_user)
    form_aud = SupplierChangeNotificationForm(data=bad_audit, tenant=tenant_a)
    assert not form_aud.is_valid()
    assert "requalification_audit" in form_aud.errors

    # Foreign design project
    bad_proj = _supplierquality_scn_base_data(supplier_party_a, project=design_project_b, evaluator=admin_user)
    form_proj = SupplierChangeNotificationForm(data=bad_proj, tenant=tenant_a)
    assert not form_proj.is_valid()
    assert "design_project" in form_proj.errors

    # Foreign evaluator
    bad_user = _supplierquality_scn_base_data(supplier_party_a, evaluator=admin_b)
    form_user = SupplierChangeNotificationForm(data=bad_user, tenant=tenant_a)
    assert not form_user.is_valid()
    assert "evaluated_by" in form_user.errors


def test_supplierquality_scn_form_widgets_and_css(tenant_a):
    """Verify CSS classes and widget types for SupplierChangeNotificationForm."""
    form = SupplierChangeNotificationForm(tenant=tenant_a)
    assert "form-select" in form.fields["supplier"].widget.attrs.get("class", "")
    assert "form-input" in form.fields["title"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["change_category"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["description"].widget.attrs.get("class", "")
    assert "form-checkbox" in form.fields["affects_form_fit_function"].widget.attrs.get("class", "")


# =============================================================================
# 5. Cross-Cutting & Edge Case Tests
# =============================================================================

def test_supplierquality_forms_empty_tenant_instantiation():
    """Verify all 4 forms can be instantiated with tenant=None safely without runtime exception."""
    form_audit = SupplierQualificationAuditForm(tenant=None)
    assert form_audit.fields["supplier"] is not None

    form_scorecard = SupplierQualityScorecardForm(tenant=None)
    assert form_scorecard.fields["supplier"] is not None

    form_scar = SupplierCorrectiveActionForm(tenant=None)
    assert form_scar.fields["supplier"] is not None

    form_scn = SupplierChangeNotificationForm(tenant=None)
    assert form_scn.fields["supplier"] is not None


def test_supplierquality_forms_required_fields_validation(tenant_a):
    """Verify required fields trigger errors when empty POST data is submitted across all 4 forms."""
    # Audit: supplier is required
    audit_form = SupplierQualificationAuditForm(data={}, tenant=tenant_a)
    assert not audit_form.is_valid()
    assert "supplier" in audit_form.errors

    # Scorecard: supplier, period_start, period_end are required
    scorecard_form = SupplierQualityScorecardForm(data={}, tenant=tenant_a)
    assert not scorecard_form.is_valid()
    assert "supplier" in scorecard_form.errors
    assert "period_start" in scorecard_form.errors
    assert "period_end" in scorecard_form.errors

    # SCAR: supplier, title, defect_summary are required
    scar_form = SupplierCorrectiveActionForm(data={}, tenant=tenant_a)
    assert not scar_form.is_valid()
    assert "supplier" in scar_form.errors
    assert "title" in scar_form.errors
    assert "defect_summary" in scar_form.errors

    # SCN: supplier, title, description are required
    scn_form = SupplierChangeNotificationForm(data={}, tenant=tenant_a)
    assert not scn_form.is_valid()
    assert "supplier" in scn_form.errors
    assert "title" in scn_form.errors
    assert "description" in scn_form.errors
