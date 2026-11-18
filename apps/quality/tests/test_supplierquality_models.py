"""Unit tests for Sub-module 12.6 Supplier & Vendor Quality Management models."""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.quality.models import (
    SupplierQualificationAudit,
    SupplierQualityScorecard,
    SupplierCorrectiveAction,
    SupplierChangeNotification,
)


# =============================================================================
# Helper Utilities
# =============================================================================

def _supplierquality_sample_date(days_offset=0):
    """Return date relative to today."""
    return timezone.now().date() + timedelta(days=days_offset)


# =============================================================================
# 1. SupplierQualificationAudit Model Tests
# =============================================================================

@pytest.mark.django_db
def test_supplierquality_audit_creation_and_number_autogen(audit_a):
    assert audit_a.pk is not None
    assert audit_a.number.startswith("QSQA-")
    assert audit_a.NUMBER_PREFIX == "QSQA"
    assert audit_a.dock_to_stock_eligible is True
    assert audit_a.requires_coa is True
    assert audit_a.score == Decimal("94.50")
    assert audit_a.qualification_status == "approved"
    assert audit_a.audit_result == "passed"


@pytest.mark.django_db
def test_supplierquality_audit_str_representation(audit_a):
    expected = f"{audit_a.number} — {audit_a.supplier.name} ({audit_a.get_qualification_status_display()})"
    assert str(audit_a) == expected


@pytest.mark.django_db
def test_supplierquality_audit_choices_and_css_helpers(audit_a):
    # Verify status CSS mapping
    status_map = {
        "under_evaluation": "badge-amber",
        "approved": "badge-green",
        "conditional": "badge-info",
        "suspended": "badge-red",
        "disqualified": "badge-muted",
    }
    for status_val, badge in status_map.items():
        audit_a.qualification_status = status_val
        assert audit_a.status_css == badge
    audit_a.qualification_status = "unknown_status"
    assert audit_a.status_css == "badge-slate"

    # Verify criticality tier CSS mapping
    tier_map = {
        "critical": "badge-red",
        "major": "badge-amber",
        "minor": "badge-slate",
        "indirect": "badge-muted",
    }
    for tier_val, badge in tier_map.items():
        audit_a.criticality_tier = tier_val
        assert audit_a.tier_css == badge
    audit_a.criticality_tier = "unknown_tier"
    assert audit_a.tier_css == "badge-slate"

    # Verify audit result CSS mapping
    result_map = {
        "pending": "badge-slate",
        "passed": "badge-green",
        "passed_with_capa": "badge-amber",
        "failed": "badge-red",
        "exempt": "badge-muted",
    }
    for result_val, badge in result_map.items():
        audit_a.audit_result = result_val
        assert audit_a.result_css == badge
    audit_a.audit_result = "unknown_result"
    assert audit_a.result_css == "badge-slate"


@pytest.mark.django_db
def test_supplierquality_audit_properties_findings_expired_overdue(tenant_a, supplier_party_a):
    today = timezone.now().date()
    audit = SupplierQualificationAudit.objects.create(
        tenant=tenant_a,
        supplier=supplier_party_a,
        critical_findings=2,
        major_findings=3,
        minor_findings=5,
        certificate_expiry_date=today - timedelta(days=10),
        next_audit_due_date=today - timedelta(days=5),
    )
    assert audit.total_findings == 10
    assert audit.is_expired is True
    assert audit.is_audit_overdue is True

    # Future dates
    audit.certificate_expiry_date = today + timedelta(days=365)
    audit.next_audit_due_date = today + timedelta(days=180)
    assert audit.is_expired is False
    assert audit.is_audit_overdue is False

    # None dates
    audit.certificate_expiry_date = None
    audit.next_audit_due_date = None
    assert audit.is_expired is False
    assert audit.is_audit_overdue is False


@pytest.mark.django_db
def test_supplierquality_audit_unique_tenant_number_constraint(tenant_a, audit_a, supplier_party_a):
    with pytest.raises(IntegrityError):
        SupplierQualificationAudit.objects.create(
            tenant=tenant_a,
            number=audit_a.number,
            supplier=supplier_party_a,
            assessment_type="initial_qualification",
        )


@pytest.mark.django_db
def test_supplierquality_audit_foreign_keys(audit_a, supplier_party_a, admin_user, doc_a):
    assert audit_a.supplier == supplier_party_a
    assert audit_a.lead_auditor == admin_user
    assert audit_a.quality_agreement == doc_a
    assert supplier_party_a.quality_qualifications.filter(pk=audit_a.pk).exists()
    assert admin_user.led_supplier_audits.filter(pk=audit_a.pk).exists()
    assert doc_a.supplier_qualifications.filter(pk=audit_a.pk).exists()


# =============================================================================
# 2. SupplierQualityScorecard Model Tests
# =============================================================================

@pytest.mark.django_db
def test_supplierquality_scorecard_creation_and_number_autogen(scorecard_a):
    assert scorecard_a.pk is not None
    assert scorecard_a.number.startswith("QSSC-")
    assert scorecard_a.NUMBER_PREFIX == "QSSC"
    assert scorecard_a.cadence == "quarterly"
    assert scorecard_a.status == "published"
    assert scorecard_a.overall_score is not None
    assert scorecard_a.grade == "grade_a"


@pytest.mark.django_db
def test_supplierquality_scorecard_str_representation(scorecard_a):
    expected = f"{scorecard_a.number} — {scorecard_a.supplier.name} ({scorecard_a.get_cadence_display()} {scorecard_a.period_end})"
    assert str(scorecard_a) == expected


@pytest.mark.django_db
def test_supplierquality_scorecard_weighted_composite_calculation(tenant_a, supplier_party_a):
    today = timezone.now().date()
    # Weights: Lot 30%, PPM 25%, SCAR 20%, Audit 15%, CoA 10%
    # 100 * 0.30 = 30.00
    #  80 * 0.25 = 20.00
    #  90 * 0.20 = 18.00
    #  70 * 0.15 = 10.50
    #  90 * 0.10 =  9.00
    # Total = 87.50 -> Grade B
    scorecard = SupplierQualityScorecard.objects.create(
        tenant=tenant_a,
        supplier=supplier_party_a,
        cadence="monthly",
        period_start=today - timedelta(days=30),
        period_end=today,
        lot_acceptance_rate_score=Decimal("100.00"),
        defect_ppm_score=Decimal("80.00"),
        scar_responsiveness_score=Decimal("90.00"),
        audit_compliance_score=Decimal("70.00"),
        documentation_coa_score=Decimal("90.00"),
    )
    assert scorecard.overall_score == Decimal("87.50")
    assert scorecard.grade == "grade_b"


@pytest.mark.django_db
def test_supplierquality_scorecard_grade_thresholds(tenant_a, supplier_party_a):
    today = timezone.now().date()

    def _create_scorecard_with_score(target_score):
        # Set all 5 scores to target_score so weighted composite equals target_score
        return SupplierQualityScorecard.objects.create(
            tenant=tenant_a,
            supplier=supplier_party_a,
            cadence="annual",
            period_start=today - timedelta(days=365),
            period_end=today,
            lot_acceptance_rate_score=Decimal(str(target_score)),
            defect_ppm_score=Decimal(str(target_score)),
            scar_responsiveness_score=Decimal(str(target_score)),
            audit_compliance_score=Decimal(str(target_score)),
            documentation_coa_score=Decimal(str(target_score)),
        )

    # Grade A: >= 90
    sc_a = _create_scorecard_with_score("95.00")
    assert sc_a.grade == "grade_a"
    sc_a_boundary = _create_scorecard_with_score("90.00")
    assert sc_a_boundary.grade == "grade_a"

    # Grade B: 80 - 89.9
    sc_b = _create_scorecard_with_score("85.00")
    assert sc_b.grade == "grade_b"
    sc_b_boundary = _create_scorecard_with_score("80.00")
    assert sc_b_boundary.grade == "grade_b"

    # Grade C: 70 - 79.9
    sc_c = _create_scorecard_with_score("75.00")
    assert sc_c.grade == "grade_c"
    sc_c_boundary = _create_scorecard_with_score("70.00")
    assert sc_c_boundary.grade == "grade_c"

    # Grade D: < 70
    sc_d = _create_scorecard_with_score("65.00")
    assert sc_d.grade == "grade_d"
    sc_d_zero = _create_scorecard_with_score("0.00")
    assert sc_d_zero.grade == "grade_d"


@pytest.mark.django_db
def test_supplierquality_scorecard_manual_override_behavior(tenant_a, supplier_party_a):
    today = timezone.now().date()

    # Case 1: Manual override with explicit score and grade provided
    sc_override = SupplierQualityScorecard(
        tenant=tenant_a,
        supplier=supplier_party_a,
        cadence="quarterly",
        period_start=today - timedelta(days=90),
        period_end=today,
        lot_acceptance_rate_score=Decimal("100.00"),
        defect_ppm_score=Decimal("100.00"),
        scar_responsiveness_score=Decimal("100.00"),
        audit_compliance_score=Decimal("100.00"),
        documentation_coa_score=Decimal("100.00"),
        is_manual_override=True,
        overall_score=Decimal("65.00"),
        grade="grade_d",
        override_justification="Supplier audit failed critical regulatory milestone.",
    )
    sc_override.save()
    assert sc_override.overall_score == Decimal("65.00")
    assert sc_override.grade == "grade_d"

    # Case 2: Manual override with overall_score None falls back to composite calculation
    sc_override_fallback = SupplierQualityScorecard(
        tenant=tenant_a,
        supplier=supplier_party_a,
        cadence="quarterly",
        period_start=today - timedelta(days=90),
        period_end=today,
        lot_acceptance_rate_score=Decimal("80.00"),
        defect_ppm_score=Decimal("80.00"),
        scar_responsiveness_score=Decimal("80.00"),
        audit_compliance_score=Decimal("80.00"),
        documentation_coa_score=Decimal("80.00"),
        is_manual_override=True,
        overall_score=None,
        grade="",
    )
    sc_override_fallback.save()
    assert sc_override_fallback.overall_score == Decimal("80.00")
    assert sc_override_fallback.grade == "grade_b"

    # Case 3: When is_manual_override is False, score and grade are strictly calculated
    sc_auto = SupplierQualityScorecard(
        tenant=tenant_a,
        supplier=supplier_party_a,
        cadence="quarterly",
        period_start=today - timedelta(days=90),
        period_end=today,
        lot_acceptance_rate_score=Decimal("95.00"),
        defect_ppm_score=Decimal("95.00"),
        scar_responsiveness_score=Decimal("95.00"),
        audit_compliance_score=Decimal("95.00"),
        documentation_coa_score=Decimal("95.00"),
        is_manual_override=False,
        overall_score=Decimal("50.00"),  # Attempt to force wrong score
        grade="grade_d",
    )
    sc_auto.save()
    assert sc_auto.overall_score == Decimal("95.00")
    assert sc_auto.grade == "grade_a"


@pytest.mark.django_db
def test_supplierquality_scorecard_properties_and_css_helpers(scorecard_a):
    # Status CSS
    status_map = {
        "draft": "badge-slate",
        "under_review": "badge-amber",
        "published": "badge-green",
        "disputed": "badge-red",
    }
    for val, badge in status_map.items():
        scorecard_a.status = val
        assert scorecard_a.status_css == badge

    # Cadence CSS
    cadence_map = {
        "monthly": "badge-info",
        "quarterly": "badge-slate",
        "semi_annual": "badge-amber",
        "annual": "badge-slate",
    }
    for val, badge in cadence_map.items():
        scorecard_a.cadence = val
        assert scorecard_a.cadence_css == badge

    # Grade CSS
    grade_map = {
        "grade_a": "badge-green",
        "grade_b": "badge-info",
        "grade_c": "badge-amber",
        "grade_d": "badge-red",
    }
    for val, badge in grade_map.items():
        scorecard_a.grade = val
        assert scorecard_a.grade_css == badge

    # is_expired property
    today = timezone.now().date()
    scorecard_a.period_end = today - timedelta(days=1)
    assert scorecard_a.is_expired is True
    scorecard_a.period_end = today + timedelta(days=30)
    assert scorecard_a.is_expired is False

    # is_action_required property
    scorecard_a.grade = "grade_a"
    scorecard_a.overall_score = Decimal("94.00")
    assert scorecard_a.is_action_required is False

    scorecard_a.grade = "grade_c"
    assert scorecard_a.is_action_required is True

    scorecard_a.grade = "grade_d"
    assert scorecard_a.is_action_required is True

    scorecard_a.grade = "grade_b"
    scorecard_a.overall_score = Decimal("78.00")
    assert scorecard_a.is_action_required is True


@pytest.mark.django_db
def test_supplierquality_scorecard_unique_constraint_and_indexes(tenant_a, scorecard_a, supplier_party_a):
    today = timezone.now().date()
    with pytest.raises(IntegrityError):
        SupplierQualityScorecard.objects.create(
            tenant=tenant_a,
            number=scorecard_a.number,
            supplier=supplier_party_a,
            period_start=today - timedelta(days=30),
            period_end=today,
        )

    # Check that model index names are properly set
    index_names = {idx.name for idx in SupplierQualityScorecard._meta.indexes}
    assert "idx_qssc_ten_status" in index_names
    assert "idx_qssc_ten_supp" in index_names
    assert "idx_qssc_ten_grade" in index_names
    assert "idx_qssc_ten_cadence" in index_names


# =============================================================================
# 3. SupplierCorrectiveAction (SCAR) Model Tests
# =============================================================================

@pytest.mark.django_db
def test_supplierquality_scar_creation_and_number_autogen(scar_a):
    assert scar_a.pk is not None
    assert scar_a.number.startswith("QSCA-")
    assert scar_a.NUMBER_PREFIX == "QSCA"
    assert scar_a.severity == "major"
    assert scar_a.status == "containment_acknowledged"


@pytest.mark.django_db
def test_supplierquality_scar_str_representation(scar_a):
    expected = f"{scar_a.number} — {scar_a.supplier.name}: {scar_a.title}"
    assert str(scar_a) == expected


@pytest.mark.django_db
def test_supplierquality_scar_choices_and_css_helpers(scar_a):
    # Severity CSS
    severity_map = {
        "minor": "badge-slate",
        "major": "badge-amber",
        "critical": "badge-red",
    }
    for val, badge in severity_map.items():
        scar_a.severity = val
        assert scar_a.severity_css == badge

    # Status CSS
    status_map = {
        "draft": "badge-slate",
        "issued": "badge-amber",
        "containment_submitted": "badge-info",
        "rca_submitted": "badge-info",
        "action_plan_approved": "badge-info",
        "implemented": "badge-info",
        "effectiveness_verified": "badge-green",
        "closed": "badge-green",
        "cancelled": "badge-muted",
    }
    for val, badge in status_map.items():
        scar_a.status = val
        assert scar_a.status_css == badge

    # Root cause category CSS
    cat_map = {
        "raw_material": "badge-red",
        "process_parameter": "badge-amber",
        "tooling_equipment": "badge-slate",
        "operator_training": "badge-info",
        "packaging_handling": "badge-slate",
        "sub_tier_supplier": "badge-amber",
        "other": "badge-muted",
    }
    for val, badge in cat_map.items():
        scar_a.root_cause_category = val
        assert scar_a.category_css == badge


@pytest.mark.django_db
def test_supplierquality_scar_overdue_and_days_open_properties(tenant_a, supplier_party_a, admin_user):
    today = timezone.now().date()
    scar = SupplierCorrectiveAction.objects.create(
        tenant=tenant_a,
        supplier=supplier_party_a,
        title="Overdue and Open Days Test SCAR",
        defect_summary="Test defect",
        issued_date=today - timedelta(days=20),
        response_due_date=today - timedelta(days=5),
        status="issued",
    )
    assert scar.is_overdue is True
    assert scar.days_open == 20

    # If status is closed or cancelled, is_overdue should be False
    scar.status = "closed"
    assert scar.is_overdue is False
    scar.status = "cancelled"
    assert scar.is_overdue is False

    # Closed at specific date
    scar.closed_at = today - timedelta(days=10)
    assert scar.days_open == 10

    # Due date in future
    scar.status = "issued"
    scar.response_due_date = today + timedelta(days=10)
    assert scar.is_overdue is False


@pytest.mark.django_db
def test_supplierquality_scar_relations_and_unique_constraint(scar_a, audit_a, admin_user, tenant_a, supplier_party_a):
    assert scar_a.supplier == supplier_party_a
    assert scar_a.qualification_audit == audit_a
    assert scar_a.issued_by == admin_user

    with pytest.raises(IntegrityError):
        SupplierCorrectiveAction.objects.create(
            tenant=tenant_a,
            number=scar_a.number,
            supplier=supplier_party_a,
            title="Duplicate SCAR",
            defect_summary="Duplicate defect",
        )


# =============================================================================
# 4. SupplierChangeNotification (SCN) Model Tests
# =============================================================================

@pytest.mark.django_db
def test_supplierquality_scn_creation_and_number_autogen(scn_a):
    assert scn_a.pk is not None
    assert scn_a.number.startswith("QSCN-")
    assert scn_a.NUMBER_PREFIX == "QSCN"
    assert scn_a.change_category == "manufacturing_process"
    assert scn_a.risk_level == "level_2_moderate"
    assert scn_a.status == "technical_evaluation"


@pytest.mark.django_db
def test_supplierquality_scn_str_representation(scn_a):
    expected = f"{scn_a.number} — {scn_a.supplier.name}: {scn_a.title}"
    assert str(scn_a) == expected


@pytest.mark.django_db
def test_supplierquality_scn_choices_and_css_helpers(scn_a):
    # Change Category CSS
    category_map = {
        "raw_material": "badge-red",
        "manufacturing_process": "badge-amber",
        "facility_location": "badge-info",
        "tooling_equipment": "badge-slate",
        "packaging_labeling": "badge-slate",
        "specification_testing": "badge-amber",
        "sub_tier_supplier": "badge-amber",
        "other": "badge-muted",
    }
    for val, badge in category_map.items():
        scn_a.change_category = val
        assert scn_a.category_css == badge

    # Risk level CSS
    risk_map = {
        "level_1_minor": "badge-slate",
        "level_2_moderate": "badge-amber",
        "level_3_major": "badge-red",
    }
    for val, badge in risk_map.items():
        scn_a.risk_level = val
        assert scn_a.risk_css == badge

    # Status CSS
    status_map = {
        "received": "badge-slate",
        "under_assessment": "badge-amber",
        "technical_evaluation": "badge-info",
        "samples_pending": "badge-info",
        "approved": "badge-green",
        "conditional_approval": "badge-amber",
        "rejected": "badge-red",
        "implemented": "badge-green",
    }
    for val, badge in status_map.items():
        scn_a.status = val
        assert scn_a.status_css == badge

    # Disposition CSS
    disp_map = {
        "pending": "badge-slate",
        "approved": "badge-green",
        "conditional_approval": "badge-amber",
        "rejected": "badge-red",
    }
    for val, badge in disp_map.items():
        scn_a.disposition = val
        assert scn_a.disposition_css == badge


@pytest.mark.django_db
def test_supplierquality_scn_risk_and_impact_properties(tenant_a, supplier_party_a):
    scn = SupplierChangeNotification.objects.create(
        tenant=tenant_a,
        supplier=supplier_party_a,
        title="Impact Check SCN",
        description="Testing risk flags",
        risk_level="level_1_minor",
        affects_form_fit_function=False,
        requires_requalification=False,
        requires_regulatory_filing=False,
    )
    assert scn.has_critical_impact is False
    assert scn.is_high_risk is False

    # Trigger via form fit function
    scn.affects_form_fit_function = True
    assert scn.has_critical_impact is True
    assert scn.is_high_risk is True
    scn.affects_form_fit_function = False

    # Trigger via requalification
    scn.requires_requalification = True
    assert scn.has_critical_impact is True
    assert scn.is_high_risk is True
    scn.requires_requalification = False

    # Trigger via regulatory filing
    scn.requires_regulatory_filing = True
    assert scn.has_critical_impact is True
    assert scn.is_high_risk is True
    scn.requires_regulatory_filing = False

    # Trigger via Level 3 Major risk level directly
    scn.risk_level = "level_3_major"
    assert scn.is_high_risk is True


@pytest.mark.django_db
def test_supplierquality_scn_relations_and_unique_constraint(scn_a, audit_a, admin_user, tenant_a, supplier_party_a):
    assert scn_a.supplier == supplier_party_a
    assert scn_a.requalification_audit == audit_a
    assert scn_a.evaluated_by == admin_user

    with pytest.raises(IntegrityError):
        SupplierChangeNotification.objects.create(
            tenant=tenant_a,
            number=scn_a.number,
            supplier=supplier_party_a,
            title="Duplicate SCN",
            description="Duplicate test",
        )


# =============================================================================
# 5. Multi-Tenancy Isolation Tests
# =============================================================================

@pytest.mark.django_db
def test_supplierquality_cross_tenant_isolation(
    tenant_a, tenant_b, audit_a, audit_b, scorecard_a, scorecard_b, scar_a, scar_b, scn_a, scn_b
):
    # SupplierQualificationAudit isolation
    audits_a = SupplierQualificationAudit.objects.filter(tenant=tenant_a)
    audits_b = SupplierQualificationAudit.objects.filter(tenant=tenant_b)
    assert audits_a.filter(pk=audit_a.pk).exists()
    assert not audits_a.filter(pk=audit_b.pk).exists()
    assert audits_b.filter(pk=audit_b.pk).exists()
    assert not audits_b.filter(pk=audit_a.pk).exists()

    # SupplierQualityScorecard isolation
    scs_a = SupplierQualityScorecard.objects.filter(tenant=tenant_a)
    scs_b = SupplierQualityScorecard.objects.filter(tenant=tenant_b)
    assert scs_a.filter(pk=scorecard_a.pk).exists()
    assert not scs_a.filter(pk=scorecard_b.pk).exists()
    assert scs_b.filter(pk=scorecard_b.pk).exists()
    assert not scs_b.filter(pk=scorecard_a.pk).exists()

    # SupplierCorrectiveAction isolation
    scars_a = SupplierCorrectiveAction.objects.filter(tenant=tenant_a)
    scars_b = SupplierCorrectiveAction.objects.filter(tenant=tenant_b)
    assert scars_a.filter(pk=scar_a.pk).exists()
    assert not scars_a.filter(pk=scar_b.pk).exists()
    assert scars_b.filter(pk=scar_b.pk).exists()
    assert not scars_b.filter(pk=scar_a.pk).exists()

    # SupplierChangeNotification isolation
    scns_a = SupplierChangeNotification.objects.filter(tenant=tenant_a)
    scns_b = SupplierChangeNotification.objects.filter(tenant=tenant_b)
    assert scns_a.filter(pk=scn_a.pk).exists()
    assert not scns_a.filter(pk=scn_b.pk).exists()
    assert scns_b.filter(pk=scn_b.pk).exists()
    assert not scns_b.filter(pk=scn_a.pk).exists()
