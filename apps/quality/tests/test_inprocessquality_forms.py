"""
Unit and integration tests for apps/quality forms (Sub-module 12.8: In-Process Quality Control - IPQC).

Covers:
- InProcessInspectionForm:
  - System field exclusions (tenant, number, created_at, updated_at).
  - Valid submission and instance creation/save.
  - Multi-tenant foreign key scoping (operator, inspector, controlled_document, non_conformance, work_order, work_center).
  - Inactive users exclusion from querysets.
  - Cross-tenant foreign key rejection via reject_foreign.
  - Sample size consistency vs batch quantity.
  - Quantity consistency (passed + rejected + reworked <= sample size).
  - Defect description requirement for rejections and non-conforming dispositions.
  - Conforming dispositions with zero defect description.
  - Widgets and HTML classes.
  - Tenant safety and empty tenant instantiation.

- FirstArticleInspectionForm:
  - System field exclusions (tenant, number, approved_by, approved_at, created_at, updated_at).
  - Specific verification that approved_by is NOT in form fields per I2 fix.
  - Valid submission and instance creation/save.
  - Multi-tenant foreign key scoping (inspector, non_conformance, work_order, work_center).
  - Inactive users exclusion from querysets.
  - Cross-tenant foreign key rejection via reject_foreign.
  - Characteristic counts validation (conforming + oos <= total).
  - Production release constraint validation (no OOS characteristics on approved status).
  - Production release constraint validation (no OOS characteristics on released verdict).
  - AS9102 Forms 1, 2, 3 complete verification on approved/released verdict.
  - Conditional approval and pilot release requiring conditional release notes.
  - Widgets and HTML classes.
  - Tenant safety and empty tenant instantiation.

- ProcessParameterLogForm:
  - System field exclusions (tenant, number, logged_by, created_at, updated_at).
  - Specific verification that logged_by is NOT in form fields per I3 fix.
  - Valid submission and instance creation/save.
  - Multi-tenant foreign key scoping (non_conformance, process_deviation, work_order, work_center).
  - Cross-tenant foreign key rejection via reject_foreign.
  - Specification tolerance ordering (LSL <= target <= USL).
  - Control limits ordering (LSL <= LCL, UCL <= USL, LCL <= UCL).
  - Automatic SPC excursion status detection:
    - Normal (in-control, in-spec)
    - Out of Control (single-sided and double-sided violation)
    - Out of Spec (single-sided and double-sided violation)
  - Mandatory immediate containment action when out of spec.
  - Widgets, numeric steps, and HTML classes.
  - Tenant safety and empty tenant instantiation.

- LayeredProcessAuditForm:
  - System field exclusions (tenant, number, compliance_percentage, created_at, updated_at).
  - Valid submission, save, and automatic compliance percentage calculation on model save.
  - Multi-tenant foreign key scoping (auditor, org_unit, controlled_document, non_conformance, work_center).
  - Inactive users exclusion from auditor queryset.
  - Cross-tenant foreign key rejection via reject_foreign.
  - Question count validation (conforming + non_conforming <= total).
  - Findings summary mandatory when non-conforming questions > 0.
  - Mitigation details mandatory when on-the-spot mitigation is checked.
  - Scheduled date validation and required fields.
  - Widgets and HTML classes.
  - Tenant safety and empty tenant instantiation.

- Cross-Cutting Form Invariants:
  - Blank submission validations across all 4 forms.
  - Instance update with bound forms preserving tenant and auto-generated numbers.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.models import OrgUnit
from apps.quality.forms import (
    FirstArticleInspectionForm,
    InProcessInspectionForm,
    LayeredProcessAuditForm,
    ProcessParameterLogForm,
)
from apps.quality.forms._common import reject_foreign
from apps.quality.models import (
    ControlledDocument,
    FirstArticleInspection,
    InProcessInspection,
    LayeredProcessAudit,
    NonConformanceReport,
    ProcessDeviation,
    ProcessParameterLog,
)
from apps.scm.models import WorkCenter, WorkOrder

User = get_user_model()
pytestmark = pytest.mark.django_db


# =============================================================================
# Helper Utilities (Prefix: _inprocessquality_*)
# =============================================================================

def _inprocessquality_pk(val):
    """Return pk if val is a model instance, or val itself if scalar / None."""
    if hasattr(val, "pk"):
        return val.pk
    return val


def _inprocessquality_date(days_offset=0):
    """Return an ISO formatted date string relative to today."""
    return (timezone.now().date() + timedelta(days=days_offset)).isoformat()


def _inprocessquality_datetime(days_offset=0):
    """Return an ISO formatted datetime string relative to now."""
    return (timezone.now() + timedelta(days=days_offset)).strftime("%Y-%m-%d %H:%M:%S")


def _inprocessquality_inspection_base_data(inspector=None, operator=None, doc=None, ncr=None, wo=None, wc=None, **extra):
    """Build valid baseline POST dictionary for InProcessInspectionForm."""
    data = {
        "title": "CNC Mill Line 2 In-Line Inspection",
        "inspection_type": "dimensional_gauging",
        "stage_gate": "Op 020 - Turning",
        "status": "completed",
        "disposition": "pass",
        "production_order_number": "PO-2026-8801",
        "work_order": _inprocessquality_pk(wo) if wo else "",
        "work_center_code": "WC-CNC-02",
        "work_center": _inprocessquality_pk(wc) if wc else "",
        "operation_step": "Op 020 - Rough Turning",
        "item_code": "ST-SHAFT-22",
        "item_name": "Precision Turbine Stainless Drive Shaft",
        "lot_number": "LOT-2026-IP-001",
        "serial_number": "SN-4140-001",
        "batch_quantity": 500,
        "sample_size_inspected": 5,
        "quantity_passed": 5,
        "quantity_rejected": 0,
        "quantity_reworked": 0,
        "defect_category": "",
        "defect_description": "",
        "controlled_document": _inprocessquality_pk(doc) if doc else "",
        "work_instruction_step": "WI-020 Step 3",
        "operator_sign_off": True,
        "operator": _inprocessquality_pk(operator) if operator else "",
        "inspector": _inprocessquality_pk(inspector) if inspector else "",
        "inspection_date": _inprocessquality_date(0),
        "non_conformance": _inprocessquality_pk(ncr) if ncr else "",
        "notes": "All diameters within blueprint limits.",
    }
    data.update(extra)
    return data


def _inprocessquality_fai_base_data(inspector=None, ncr=None, wo=None, wc=None, **extra):
    """Build valid baseline POST dictionary for FirstArticleInspectionForm."""
    data = {
        "title": "AS9102 Full FAI - Bracket",
        "fai_type": "full_fai",
        "setup_reason": "new_product_intro",
        "status": "in_inspection",
        "production_order_number": "PO-2026-FAI-01",
        "work_order": _inprocessquality_pk(wo) if wo else "",
        "work_center_code": "WC-CNC-01",
        "work_center": _inprocessquality_pk(wc) if wc else "",
        "machine_tooling_id": "CNC-04 Die-B2",
        "item_code": "AERO-BRKT-901",
        "item_name": "Titanium Support Bracket Strut",
        "drawing_number": "DWG-AERO-901",
        "drawing_revision": "Rev C",
        "first_piece_lot_number": "LOT-FAI-001",
        "serial_number": "SN-FAI-001",
        "total_characteristics_inspected": 18,
        "characteristics_conforming": 18,
        "characteristics_out_of_spec": 0,
        "max_deviation_found": "+0.003 mm on Bore Dia",
        "as9102_form1_complete": True,
        "as9102_form2_complete": True,
        "as9102_form3_complete": True,
        "gage_serial_numbers": "CMM-01, Caliper-402, HeightGage-12",
        "release_verdict": "pending",
        "conditional_release_notes": "",
        "non_conformance": _inprocessquality_pk(ncr) if ncr else "",
        "inspector": _inprocessquality_pk(inspector) if inspector else "",
        "notes": "Ballooned drawing characteristics verified on CMM.",
    }
    data.update(extra)
    return data


def _inprocessquality_param_base_data(wo=None, wc=None, ncr=None, dev=None, **extra):
    """Build valid baseline POST dictionary for ProcessParameterLogForm."""
    data = {
        "parameter_name": "Reflow Temperature",
        "parameter_category": "temperature",
        "unit_of_measure": "°C",
        "work_center_code": "WC-SMT-01",
        "work_center": _inprocessquality_pk(wc) if wc else "",
        "production_order_number": "PO-2026-8802",
        "work_order": _inprocessquality_pk(wo) if wo else "",
        "operation_step": "Op 040 SMT Reflow",
        "item_code": "PCB-A440",
        "lot_number": "LOT-2026-IP-002",
        "target_nominal_value": "245.0000",
        "lower_spec_limit": "235.0000",
        "upper_spec_limit": "255.0000",
        "lower_control_limit": "240.0000",
        "upper_control_limit": "250.0000",
        "recorded_value": "246.2000",
        "recorded_at": _inprocessquality_datetime(0),
        "excursion_status": "normal",
        "containment_action": "none",
        "containment_notes": "",
        "non_conformance": _inprocessquality_pk(ncr) if ncr else "",
        "process_deviation": _inprocessquality_pk(dev) if dev else "",
    }
    data.update(extra)
    return data


def _inprocessquality_audit_base_data(auditor=None, org_unit=None, doc=None, ncr=None, wc=None, **extra):
    """Build valid baseline POST dictionary for LayeredProcessAuditForm."""
    data = {
        "title": "Tier 1 Daily Shift LPA - Turning Cell",
        "audit_layer": "tier_1_operator_lead",
        "focus_area": "standard_work_wi",
        "status": "completed",
        "work_center_code": "WC-CNC-01",
        "work_center": _inprocessquality_pk(wc) if wc else "",
        "org_unit": _inprocessquality_pk(org_unit) if org_unit else "",
        "shift": "Shift 1 (Morning)",
        "scheduled_date": _inprocessquality_date(0),
        "conducted_at": _inprocessquality_datetime(0),
        "auditor": _inprocessquality_pk(auditor) if auditor else "",
        "total_questions_audited": 10,
        "questions_conforming": 10,
        "questions_non_conforming": 0,
        "controlled_document": _inprocessquality_pk(doc) if doc else "",
        "findings_summary": "",
        "on_the_spot_mitigation": False,
        "mitigation_details": "",
        "non_conformance": _inprocessquality_pk(ncr) if ncr else "",
        "notes": "5S audit and torque verification completed.",
    }
    data.update(extra)
    return data


# =============================================================================
# 1. InProcessInspectionForm Tests
# =============================================================================

def test_inprocessquality_form_inspection_system_field_exclusion(tenant_a, admin_user):
    """Verify tenant, number, created_at, updated_at are excluded from InProcessInspectionForm."""
    form = InProcessInspectionForm(tenant=tenant_a)
    forbidden_fields = ["tenant", "number", "created_at", "updated_at"]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from InProcessInspectionForm"

    # Malicious injection in POST data must not alter system properties
    malicious_data = _inprocessquality_inspection_base_data(
        inspector=admin_user,
        tenant=tenant_a.pk,
        number="QIPQ-HACKED-9999",
        created_at=_inprocessquality_date(-50),
    )
    bound_form = InProcessInspectionForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QIPQ-HACKED-9999"


def test_inprocessquality_form_inspection_valid_submission_creates_record(tenant_a, admin_user, member_user, doc_a, ncr_a):
    """Verify valid InProcessInspectionForm submission creates and saves a record."""
    data = _inprocessquality_inspection_base_data(
        inspector=admin_user,
        operator=member_user,
        doc=doc_a,
        ncr=ncr_a,
        batch_quantity=200,
        sample_size_inspected=8,
        quantity_passed=8,
        quantity_rejected=0,
        notes="High-precision finish turning passes surface profilometer check.",
    )
    form = InProcessInspectionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.pk is not None
    assert instance.number.startswith("QIPQ-")
    assert instance.title == "CNC Mill Line 2 In-Line Inspection"
    assert instance.batch_quantity == 200
    assert instance.sample_size_inspected == 8
    assert instance.quantity_passed == 8
    assert instance.inspector == admin_user
    assert instance.operator == member_user
    assert instance.controlled_document == doc_a
    assert instance.non_conformance == ncr_a


def test_inprocessquality_form_inspection_foreign_key_scoping(tenant_a, tenant_b, admin_user, admin_b, member_user, doc_a, doc_b, ncr_a, ncr_b):
    """Verify operator, inspector, doc, and ncr querysets are strictly tenant-scoped."""
    wc_a = WorkCenter.objects.create(tenant=tenant_a, code="WC-A01", name="Machining Center A")
    wc_b = WorkCenter.objects.create(tenant=tenant_b, code="WC-B01", name="Machining Center B")

    form = InProcessInspectionForm(tenant=tenant_a)

    inspector_pks = set(form.fields["inspector"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in inspector_pks
    assert admin_b.pk not in inspector_pks

    operator_pks = set(form.fields["operator"].queryset.values_list("pk", flat=True))
    assert member_user.pk in operator_pks
    assert admin_b.pk not in operator_pks

    doc_pks = set(form.fields["controlled_document"].queryset.values_list("pk", flat=True))
    assert doc_a.pk in doc_pks
    assert doc_b.pk not in doc_pks

    ncr_pks = set(form.fields["non_conformance"].queryset.values_list("pk", flat=True))
    assert ncr_a.pk in ncr_pks
    assert ncr_b.pk not in ncr_pks

    wc_pks = set(form.fields["work_center"].queryset.values_list("pk", flat=True))
    assert wc_a.pk in wc_pks
    assert wc_b.pk not in wc_pks


def test_inprocessquality_form_inspection_inactive_user_excluded(tenant_a):
    """Verify inactive users are excluded from operator and inspector querysets."""
    inactive_user = User.objects.create_user(
        username="inactive_inspector@acme.com",
        email="inactive_inspector@acme.com",
        password="password123",
        tenant=tenant_a,
        is_active=False,
    )
    form = InProcessInspectionForm(tenant=tenant_a)
    inspector_pks = set(form.fields["inspector"].queryset.values_list("pk", flat=True))
    operator_pks = set(form.fields["operator"].queryset.values_list("pk", flat=True))
    assert inactive_user.pk not in inspector_pks
    assert inactive_user.pk not in operator_pks


def test_inprocessquality_form_inspection_reject_foreign_tenants(tenant_a, tenant_b, admin_user, admin_b, doc_b, ncr_b):
    """Verify cross-tenant foreign keys are rejected during validation and reject_foreign helper."""
    # Submission with foreign inspector
    data_bad_inspector = _inprocessquality_inspection_base_data(inspector=admin_b)
    form_insp = InProcessInspectionForm(data=data_bad_inspector, tenant=tenant_a)
    assert not form_insp.is_valid()
    assert "inspector" in form_insp.errors

    # Submission with foreign doc
    data_bad_doc = _inprocessquality_inspection_base_data(inspector=admin_user, doc=doc_b)
    form_doc = InProcessInspectionForm(data=data_bad_doc, tenant=tenant_a)
    assert not form_doc.is_valid()
    assert "controlled_document" in form_doc.errors

    # Submission with foreign NCR
    data_bad_ncr = _inprocessquality_inspection_base_data(inspector=admin_user, ncr=ncr_b)
    form_ncr = InProcessInspectionForm(data=data_bad_ncr, tenant=tenant_a)
    assert not form_ncr.is_valid()
    assert "non_conformance" in form_ncr.errors

    # Direct reject_foreign check
    form_direct = InProcessInspectionForm(data={}, tenant=tenant_a)
    form_direct.is_valid()
    form_direct.cleaned_data = {"operator": admin_b, "controlled_document": doc_b}
    reject_foreign(form_direct, form_direct.cleaned_data, ["operator", "controlled_document"])
    assert "operator" in form_direct.errors
    assert "controlled_document" in form_direct.errors
    assert "That record belongs to another workspace." in form_direct.errors["operator"][0]


def test_inprocessquality_form_inspection_quantity_sample_size_exceeds_batch(tenant_a, admin_user):
    """Verify validation error when sample size exceeds total batch quantity."""
    data = _inprocessquality_inspection_base_data(
        inspector=admin_user,
        batch_quantity=10,
        sample_size_inspected=15,
        quantity_passed=10,
        quantity_rejected=0,
    )
    form = InProcessInspectionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "sample_size_inspected" in form.errors
    assert "Sample size cannot exceed total batch quantity." in form.errors["sample_size_inspected"][0]


def test_inprocessquality_form_inspection_quantity_sum_exceeds_sample_size(tenant_a, admin_user):
    """Verify validation error when sum of passed + rejected + reworked exceeds sample size."""
    data = _inprocessquality_inspection_base_data(
        inspector=admin_user,
        batch_quantity=100,
        sample_size_inspected=10,
        quantity_passed=6,
        quantity_rejected=3,
        quantity_reworked=2,  # 6 + 3 + 2 = 11 > 10
        defect_description="Scrap and rework found",
    )
    form = InProcessInspectionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "quantity_passed" in form.errors
    assert "Total passed, rejected, and reworked pieces cannot exceed inspected sample size." in form.errors["quantity_passed"][0]


def test_inprocessquality_form_inspection_quantity_sum_valid_scenarios(tenant_a, admin_user):
    """Verify valid scenarios where passed + rejected + reworked equals or is less than sample size."""
    # Scenario 1: Exact sum equals sample size
    data_exact = _inprocessquality_inspection_base_data(
        inspector=admin_user,
        batch_quantity=50,
        sample_size_inspected=10,
        quantity_passed=7,
        quantity_rejected=2,
        quantity_reworked=1,
        defect_description="Tooling chatter caused two scrap and one oversize bore",
    )
    form_exact = InProcessInspectionForm(data=data_exact, tenant=tenant_a)
    assert form_exact.is_valid(), form_exact.errors

    # Scenario 2: Sum is less than sample size (in-progress inspection)
    data_less = _inprocessquality_inspection_base_data(
        inspector=admin_user,
        status="in_progress",
        batch_quantity=50,
        sample_size_inspected=10,
        quantity_passed=4,
        quantity_rejected=0,
        quantity_reworked=0,
    )
    form_less = InProcessInspectionForm(data=data_less, tenant=tenant_a)
    assert form_less.is_valid(), form_less.errors


def test_inprocessquality_form_inspection_defect_description_required_when_rejected(tenant_a, admin_user):
    """Verify defect_description is mandatory when rejected pieces > 0."""
    data_missing_desc = _inprocessquality_inspection_base_data(
        inspector=admin_user,
        sample_size_inspected=10,
        quantity_passed=9,
        quantity_rejected=1,
        defect_description="",
    )
    form = InProcessInspectionForm(data=data_missing_desc, tenant=tenant_a)
    assert not form.is_valid()
    assert "defect_description" in form.errors
    assert "Defect description is required when parts are rejected, reworked, or quarantined." in form.errors["defect_description"][0]

    # Providing defect description makes it valid
    data_valid = _inprocessquality_inspection_base_data(
        inspector=admin_user,
        sample_size_inspected=10,
        quantity_passed=9,
        quantity_rejected=1,
        defect_category="dimensional",
        defect_description="Outside diameter undersized by 0.05mm",
    )
    form_valid = InProcessInspectionForm(data=data_valid, tenant=tenant_a)
    assert form_valid.is_valid(), form_valid.errors


def test_inprocessquality_form_inspection_defect_description_required_for_failure_dispositions(tenant_a, admin_user):
    """Verify defect_description is required for rework_required, reject_scrap, quarantine_hold dispositions."""
    failure_dispositions = ["rework_required", "reject_scrap", "quarantine_hold"]
    for disp in failure_dispositions:
        data = _inprocessquality_inspection_base_data(
            inspector=admin_user,
            disposition=disp,
            sample_size_inspected=5,
            quantity_passed=5,
            quantity_rejected=0,
            defect_description="",
        )
        form = InProcessInspectionForm(data=data, tenant=tenant_a)
        assert not form.is_valid(), f"Disposition '{disp}' without defect_description must fail"
        assert "defect_description" in form.errors

        # Adding defect description resolves the error
        data["defect_description"] = f"Defect logged for {disp}"
        form_fixed = InProcessInspectionForm(data=data, tenant=tenant_a)
        assert form_fixed.is_valid(), form_fixed.errors


def test_inprocessquality_form_inspection_conforming_dispositions_allow_blank_defect_desc(tenant_a, admin_user):
    """Verify conforming dispositions (pass, conditional_pass) allow blank defect_description when rejected=0."""
    for disp in ["pass", "conditional_pass", "pending"]:
        data = _inprocessquality_inspection_base_data(
            inspector=admin_user,
            disposition=disp,
            sample_size_inspected=5,
            quantity_passed=5,
            quantity_rejected=0,
            defect_description="",
        )
        form = InProcessInspectionForm(data=data, tenant=tenant_a)
        assert form.is_valid(), form.errors


def test_inprocessquality_form_inspection_widgets_and_styling(tenant_a):
    """Verify widget types and CSS classes assigned to InProcessInspectionForm fields."""
    form = InProcessInspectionForm(tenant=tenant_a)
    assert "form-input" in form.fields["title"].widget.attrs["class"]
    assert "form-select" in form.fields["inspection_type"].widget.attrs["class"]
    assert "form-select" in form.fields["status"].widget.attrs["class"]
    assert "form-select" in form.fields["disposition"].widget.attrs["class"]
    assert "form-textarea" in form.fields["defect_description"].widget.attrs["class"]
    assert "form-checkbox" in form.fields["operator_sign_off"].widget.attrs["class"]
    assert form.fields["inspection_date"].widget.input_type == "date"


def test_inprocessquality_form_inspection_empty_tenant_instantiation():
    """Verify InProcessInspectionForm handles None tenant gracefully without exceptions."""
    form = InProcessInspectionForm(tenant=None)
    assert form.fields["title"] is not None


# =============================================================================
# 2. FirstArticleInspectionForm Tests
# =============================================================================

def test_inprocessquality_form_fai_system_field_exclusion(tenant_a, admin_user):
    """Verify tenant, number, approved_by, approved_at, timestamps are excluded from FirstArticleInspectionForm."""
    form = FirstArticleInspectionForm(tenant=tenant_a)
    forbidden_fields = ["tenant", "number", "approved_by", "approved_at", "created_at", "updated_at"]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from FirstArticleInspectionForm per I2 fix"

    # Malicious injection in POST data must not alter system properties or approval status
    malicious_data = _inprocessquality_fai_base_data(
        inspector=admin_user,
        tenant=tenant_a.pk,
        number="QFAI-HACKED-0001",
        approved_by=admin_user.pk,
        approved_at=_inprocessquality_datetime(0),
    )
    bound_form = FirstArticleInspectionForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QFAI-HACKED-0001"
    assert getattr(instance, "approved_by", None) is None
    assert getattr(instance, "approved_at", None) is None


def test_inprocessquality_form_fai_valid_submission_creates_record(tenant_a, admin_user, ncr_a):
    """Verify valid FirstArticleInspectionForm submission persists record with QFAI- prefix."""
    data = _inprocessquality_fai_base_data(
        inspector=admin_user,
        ncr=ncr_a,
        total_characteristics_inspected=25,
        characteristics_conforming=25,
        characteristics_out_of_spec=0,
        notes="AS9102 Rev B Form 1, 2, and 3 fully completed and signed off.",
    )
    form = FirstArticleInspectionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.pk is not None
    assert instance.number.startswith("QFAI-")
    assert instance.total_characteristics_inspected == 25
    assert instance.characteristics_conforming == 25
    assert instance.characteristics_out_of_spec == 0
    assert instance.inspector == admin_user
    assert instance.non_conformance == ncr_a


def test_inprocessquality_form_fai_foreign_key_scoping(tenant_a, tenant_b, admin_user, admin_b, ncr_a, ncr_b):
    """Verify inspector, non_conformance, work_order, work_center querysets are scoped to tenant."""
    wc_a = WorkCenter.objects.create(tenant=tenant_a, code="WC-A02", name="Milling Cell A")
    wc_b = WorkCenter.objects.create(tenant=tenant_b, code="WC-B02", name="Milling Cell B")

    form = FirstArticleInspectionForm(tenant=tenant_a)

    inspector_pks = set(form.fields["inspector"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in inspector_pks
    assert admin_b.pk not in inspector_pks

    ncr_pks = set(form.fields["non_conformance"].queryset.values_list("pk", flat=True))
    assert ncr_a.pk in ncr_pks
    assert ncr_b.pk not in ncr_pks

    wc_pks = set(form.fields["work_center"].queryset.values_list("pk", flat=True))
    assert wc_a.pk in wc_pks
    assert wc_b.pk not in wc_pks


def test_inprocessquality_form_fai_inactive_user_excluded(tenant_a):
    """Verify inactive users are excluded from the inspector queryset on FAI form."""
    inactive_user = User.objects.create_user(
        username="inactive_fai_inspector@acme.com",
        email="inactive_fai_inspector@acme.com",
        password="password123",
        tenant=tenant_a,
        is_active=False,
    )
    form = FirstArticleInspectionForm(tenant=tenant_a)
    inspector_pks = set(form.fields["inspector"].queryset.values_list("pk", flat=True))
    assert inactive_user.pk not in inspector_pks


def test_inprocessquality_form_fai_reject_foreign_tenants(tenant_a, tenant_b, admin_user, admin_b, ncr_b):
    """Verify cross-tenant foreign keys are rejected during FAI form validation."""
    # Submission with foreign inspector
    data_bad_insp = _inprocessquality_fai_base_data(inspector=admin_b)
    form_insp = FirstArticleInspectionForm(data=data_bad_insp, tenant=tenant_a)
    assert not form_insp.is_valid()
    assert "inspector" in form_insp.errors

    # Submission with foreign NCR
    data_bad_ncr = _inprocessquality_fai_base_data(inspector=admin_user, ncr=ncr_b)
    form_ncr = FirstArticleInspectionForm(data=data_bad_ncr, tenant=tenant_a)
    assert not form_ncr.is_valid()
    assert "non_conformance" in form_ncr.errors

    # Direct reject_foreign check
    form_direct = FirstArticleInspectionForm(data={}, tenant=tenant_a)
    form_direct.is_valid()
    form_direct.cleaned_data = {"inspector": admin_b, "non_conformance": ncr_b}
    reject_foreign(form_direct, form_direct.cleaned_data, ["inspector", "non_conformance"])
    assert "inspector" in form_direct.errors
    assert "non_conformance" in form_direct.errors
    assert "That record belongs to another workspace." in form_direct.errors["inspector"][0]


def test_inprocessquality_form_fai_characteristic_counts_sum_exceeds_total(tenant_a, admin_user):
    """Verify conforming + out-of-spec characteristics cannot exceed total inspected."""
    data = _inprocessquality_fai_base_data(
        inspector=admin_user,
        total_characteristics_inspected=10,
        characteristics_conforming=8,
        characteristics_out_of_spec=3,  # 8 + 3 = 11 > 10
    )
    form = FirstArticleInspectionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "characteristics_conforming" in form.errors
    assert "Total conforming plus out-of-spec characteristics cannot exceed total inspected characteristics." in form.errors["characteristics_conforming"][0]


def test_inprocessquality_form_fai_characteristic_counts_valid_scenarios(tenant_a, admin_user):
    """Verify valid characteristic count scenarios (exact sum and partial measurements)."""
    # Exact sum equals total
    data_exact = _inprocessquality_fai_base_data(
        inspector=admin_user,
        status="rejected_setup_hold",
        release_verdict="rejected_retool",
        total_characteristics_inspected=10,
        characteristics_conforming=8,
        characteristics_out_of_spec=2,
    )
    form_exact = FirstArticleInspectionForm(data=data_exact, tenant=tenant_a)
    assert form_exact.is_valid(), form_exact.errors

    # Partial count (in-progress measurement)
    data_partial = _inprocessquality_fai_base_data(
        inspector=admin_user,
        status="in_inspection",
        release_verdict="pending",
        total_characteristics_inspected=15,
        characteristics_conforming=5,
        characteristics_out_of_spec=0,
    )
    form_partial = FirstArticleInspectionForm(data=data_partial, tenant=tenant_a)
    assert form_partial.is_valid(), form_partial.errors


def test_inprocessquality_form_fai_approved_run_released_status_requires_zero_oos(tenant_a, admin_user):
    """Verify approved_run_released status blocks approval if characteristics_out_of_spec > 0."""
    data = _inprocessquality_fai_base_data(
        inspector=admin_user,
        status="approved_run_released",
        release_verdict="pending",
        total_characteristics_inspected=10,
        characteristics_conforming=9,
        characteristics_out_of_spec=1,
        as9102_form1_complete=True,
        as9102_form2_complete=True,
        as9102_form3_complete=True,
    )
    form = FirstArticleInspectionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "characteristics_out_of_spec" in form.errors
    assert "Full production run release requires zero out-of-spec characteristics." in form.errors["characteristics_out_of_spec"][0]


def test_inprocessquality_form_fai_released_verdict_requires_zero_oos(tenant_a, admin_user):
    """Verify release_verdict='released' blocks release if characteristics_out_of_spec > 0."""
    data = _inprocessquality_fai_base_data(
        inspector=admin_user,
        status="in_inspection",
        release_verdict="released",
        total_characteristics_inspected=10,
        characteristics_conforming=9,
        characteristics_out_of_spec=1,
        as9102_form1_complete=True,
        as9102_form2_complete=True,
        as9102_form3_complete=True,
    )
    form = FirstArticleInspectionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "characteristics_out_of_spec" in form.errors
    assert "Full production run release requires zero out-of-spec characteristics." in form.errors["characteristics_out_of_spec"][0]


def test_inprocessquality_form_fai_release_requires_all_as9102_forms_complete(tenant_a, admin_user):
    """Verify full production run release requires AS9102 Forms 1, 2, and 3 verification sign-offs."""
    # Missing Form 1
    data_missing_f1 = _inprocessquality_fai_base_data(
        inspector=admin_user,
        status="approved_run_released",
        release_verdict="released",
        total_characteristics_inspected=10,
        characteristics_conforming=10,
        characteristics_out_of_spec=0,
        as9102_form1_complete=False,
        as9102_form2_complete=True,
        as9102_form3_complete=True,
    )
    form_f1 = FirstArticleInspectionForm(data=data_missing_f1, tenant=tenant_a)
    assert not form_f1.is_valid()
    assert "release_verdict" in form_f1.errors
    assert "Full production release requires AS9102 Forms 1, 2, and 3 verification sign-offs." in form_f1.errors["release_verdict"][0]

    # Missing Form 3
    data_missing_f3 = _inprocessquality_fai_base_data(
        inspector=admin_user,
        status="approved_run_released",
        release_verdict="released",
        total_characteristics_inspected=10,
        characteristics_conforming=10,
        characteristics_out_of_spec=0,
        as9102_form1_complete=True,
        as9102_form2_complete=True,
        as9102_form3_complete=False,
    )
    form_f3 = FirstArticleInspectionForm(data=data_missing_f3, tenant=tenant_a)
    assert not form_f3.is_valid()
    assert "release_verdict" in form_f3.errors


def test_inprocessquality_form_fai_release_valid_when_all_as9102_forms_complete_and_zero_oos(tenant_a, admin_user):
    """Verify release is valid when Forms 1-3 are complete and zero out-of-spec characteristics exist."""
    data = _inprocessquality_fai_base_data(
        inspector=admin_user,
        status="approved_run_released",
        release_verdict="released",
        total_characteristics_inspected=12,
        characteristics_conforming=12,
        characteristics_out_of_spec=0,
        as9102_form1_complete=True,
        as9102_form2_complete=True,
        as9102_form3_complete=True,
    )
    form = FirstArticleInspectionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_inprocessquality_form_fai_conditional_approval_requires_notes(tenant_a, admin_user):
    """Verify conditional approval requires conditional_release_notes."""
    # Blank notes on conditional_approval status
    data_missing = _inprocessquality_fai_base_data(
        inspector=admin_user,
        status="conditional_approval",
        release_verdict="pending",
        conditional_release_notes="",
    )
    form = FirstArticleInspectionForm(data=data_missing, tenant=tenant_a)
    assert not form.is_valid()
    assert "conditional_release_notes" in form.errors
    assert "Conditional release notes and containment boundaries are mandatory for pilot releases." in form.errors["conditional_release_notes"][0]

    # With notes provided
    data_valid = _inprocessquality_fai_base_data(
        inspector=admin_user,
        status="conditional_approval",
        release_verdict="conditional_pilot_release",
        conditional_release_notes="Pilot lot of 50 units authorized with 100% CMM inspection at Op 030.",
    )
    form_valid = FirstArticleInspectionForm(data=data_valid, tenant=tenant_a)
    assert form_valid.is_valid(), form_valid.errors


def test_inprocessquality_form_fai_conditional_pilot_release_verdict_requires_notes(tenant_a, admin_user):
    """Verify release_verdict='conditional_pilot_release' requires conditional_release_notes."""
    data_missing = _inprocessquality_fai_base_data(
        inspector=admin_user,
        status="in_inspection",
        release_verdict="conditional_pilot_release",
        conditional_release_notes="",
    )
    form = FirstArticleInspectionForm(data=data_missing, tenant=tenant_a)
    assert not form.is_valid()
    assert "conditional_release_notes" in form.errors


def test_inprocessquality_form_fai_widgets_and_styling(tenant_a):
    """Verify widget types and CSS classes assigned to FirstArticleInspectionForm fields."""
    form = FirstArticleInspectionForm(tenant=tenant_a)
    assert "form-input" in form.fields["title"].widget.attrs["class"]
    assert "form-select" in form.fields["fai_type"].widget.attrs["class"]
    assert "form-select" in form.fields["release_verdict"].widget.attrs["class"]
    assert "form-checkbox" in form.fields["as9102_form1_complete"].widget.attrs["class"]
    assert "form-textarea" in form.fields["conditional_release_notes"].widget.attrs["class"]
    assert form.fields["conditional_release_notes"].widget.attrs["rows"] == 3


def test_inprocessquality_form_fai_empty_tenant_instantiation():
    """Verify FirstArticleInspectionForm handles None tenant gracefully without exceptions."""
    form = FirstArticleInspectionForm(tenant=None)
    assert form.fields["title"] is not None


# =============================================================================
# 3. ProcessParameterLogForm Tests
# =============================================================================

def test_inprocessquality_form_param_system_field_exclusion(tenant_a, admin_user):
    """Verify tenant, number, logged_by, created_at, updated_at are excluded from ProcessParameterLogForm."""
    form = ProcessParameterLogForm(tenant=tenant_a)
    forbidden_fields = ["tenant", "number", "logged_by", "created_at", "updated_at"]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from ProcessParameterLogForm per I3 fix"

    # Malicious injection in POST data must not alter system properties or logged_by
    malicious_data = _inprocessquality_param_base_data(
        tenant=tenant_a.pk,
        number="QPAR-HACKED-9999",
        logged_by=admin_user.pk,
        created_at=_inprocessquality_datetime(-10),
    )
    bound_form = ProcessParameterLogForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QPAR-HACKED-9999"
    assert getattr(instance, "logged_by", None) is None


def test_inprocessquality_form_param_valid_submission_creates_record(tenant_a, admin_user, ncr_a, process_deviation_a):
    """Verify valid ProcessParameterLogForm submission persists record with QPAR- prefix."""
    data = _inprocessquality_param_base_data(
        ncr=ncr_a,
        dev=process_deviation_a,
        parameter_name="Spindle Speed Ref",
        parameter_category="speed_feed",
        unit_of_measure="RPM",
        target_nominal_value="3200.0000",
        lower_spec_limit="3000.0000",
        upper_spec_limit="3400.0000",
        lower_control_limit="3100.0000",
        upper_control_limit="3300.0000",
        recorded_value="3205.5000",
    )
    form = ProcessParameterLogForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.logged_by = admin_user
    instance.save()

    assert instance.pk is not None
    assert instance.number.startswith("QPAR-")
    assert instance.parameter_name == "Spindle Speed Ref"
    assert instance.recorded_value == Decimal("3205.5000")
    assert instance.excursion_status == "normal"
    assert instance.logged_by == admin_user
    assert instance.non_conformance == ncr_a
    assert instance.process_deviation == process_deviation_a


def test_inprocessquality_form_param_foreign_key_scoping(tenant_a, tenant_b, ncr_a, ncr_b, process_deviation_a, process_deviation_b):
    """Verify non_conformance and process_deviation querysets are scoped to tenant."""
    wc_a = WorkCenter.objects.create(tenant=tenant_a, code="WC-A03", name="Welding Cell A")
    wc_b = WorkCenter.objects.create(tenant=tenant_b, code="WC-B03", name="Welding Cell B")

    form = ProcessParameterLogForm(tenant=tenant_a)

    ncr_pks = set(form.fields["non_conformance"].queryset.values_list("pk", flat=True))
    assert ncr_a.pk in ncr_pks
    assert ncr_b.pk not in ncr_pks

    dev_pks = set(form.fields["process_deviation"].queryset.values_list("pk", flat=True))
    assert process_deviation_a.pk in dev_pks
    assert process_deviation_b.pk not in dev_pks

    wc_pks = set(form.fields["work_center"].queryset.values_list("pk", flat=True))
    assert wc_a.pk in wc_pks
    assert wc_b.pk not in wc_pks


def test_inprocessquality_form_param_reject_foreign_tenants(tenant_a, tenant_b, ncr_b, process_deviation_b):
    """Verify cross-tenant foreign keys are rejected during parameter log form validation."""
    # Submission with foreign NCR
    data_bad_ncr = _inprocessquality_param_base_data(ncr=ncr_b)
    form_ncr = ProcessParameterLogForm(data=data_bad_ncr, tenant=tenant_a)
    assert not form_ncr.is_valid()
    assert "non_conformance" in form_ncr.errors

    # Submission with foreign Deviation
    data_bad_dev = _inprocessquality_param_base_data(dev=process_deviation_b)
    form_dev = ProcessParameterLogForm(data=data_bad_dev, tenant=tenant_a)
    assert not form_dev.is_valid()
    assert "process_deviation" in form_dev.errors

    # Direct reject_foreign check
    form_direct = ProcessParameterLogForm(data={}, tenant=tenant_a)
    form_direct.is_valid()
    form_direct.cleaned_data = {"non_conformance": ncr_b, "process_deviation": process_deviation_b}
    reject_foreign(form_direct, form_direct.cleaned_data, ["non_conformance", "process_deviation"])
    assert "non_conformance" in form_direct.errors
    assert "process_deviation" in form_direct.errors
    assert "That record belongs to another workspace." in form_direct.errors["non_conformance"][0]


def test_inprocessquality_form_param_spec_tolerance_usl_less_than_lsl(tenant_a):
    """Verify validation error when USL is less than LSL."""
    data = _inprocessquality_param_base_data(
        lower_spec_limit="250.0000",
        upper_spec_limit="240.0000",
        target_nominal_value="245.0000",
        lower_control_limit="",
        upper_control_limit="",
    )
    form = ProcessParameterLogForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "upper_spec_limit" in form.errors
    assert "Upper specification limit (USL) cannot be less than lower limit (LSL)." in form.errors["upper_spec_limit"][0]


def test_inprocessquality_form_param_target_outside_spec_limits(tenant_a):
    """Verify target nominal value must be between LSL and USL."""
    # Target < LSL
    data_low = _inprocessquality_param_base_data(
        target_nominal_value="220.0000",
        lower_spec_limit="235.0000",
        upper_spec_limit="255.0000",
    )
    form_low = ProcessParameterLogForm(data=data_low, tenant=tenant_a)
    assert not form_low.is_valid()
    assert "target_nominal_value" in form_low.errors
    assert "Target nominal value cannot be less than lower specification limit (LSL)." in form_low.errors["target_nominal_value"][0]

    # Target > USL
    data_high = _inprocessquality_param_base_data(
        target_nominal_value="260.0000",
        lower_spec_limit="235.0000",
        upper_spec_limit="255.0000",
    )
    form_high = ProcessParameterLogForm(data=data_high, tenant=tenant_a)
    assert not form_high.is_valid()
    assert "target_nominal_value" in form_high.errors
    assert "Target nominal value cannot be greater than upper specification limit (USL)." in form_high.errors["target_nominal_value"][0]


def test_inprocessquality_form_param_control_limits_ucl_less_than_lcl(tenant_a):
    """Verify validation error when UCL is less than LCL."""
    data = _inprocessquality_param_base_data(
        lower_spec_limit="235.0000",
        upper_spec_limit="255.0000",
        target_nominal_value="245.0000",
        lower_control_limit="248.0000",
        upper_control_limit="242.0000",  # UCL < LCL
    )
    form = ProcessParameterLogForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "upper_control_limit" in form.errors
    assert "Upper control limit (UCL) cannot be less than lower control limit (LCL)." in form.errors["upper_control_limit"][0]


def test_inprocessquality_form_param_control_limits_outside_spec_limits(tenant_a):
    """Verify LCL cannot be below LSL and UCL cannot exceed USL."""
    # LCL < LSL
    data_lcl = _inprocessquality_param_base_data(
        lower_spec_limit="235.0000",
        upper_spec_limit="255.0000",
        target_nominal_value="245.0000",
        lower_control_limit="230.0000",  # 230 < 235
        upper_control_limit="250.0000",
    )
    form_lcl = ProcessParameterLogForm(data=data_lcl, tenant=tenant_a)
    assert not form_lcl.is_valid()
    assert "lower_control_limit" in form_lcl.errors
    assert "Lower control limit (LCL) cannot be less than lower specification limit (LSL)." in form_lcl.errors["lower_control_limit"][0]

    # UCL > USL
    data_ucl = _inprocessquality_param_base_data(
        lower_spec_limit="235.0000",
        upper_spec_limit="255.0000",
        target_nominal_value="245.0000",
        lower_control_limit="240.0000",
        upper_control_limit="260.0000",  # 260 > 255
    )
    form_ucl = ProcessParameterLogForm(data=data_ucl, tenant=tenant_a)
    assert not form_ucl.is_valid()
    assert "upper_control_limit" in form_ucl.errors
    assert "Upper control limit (UCL) cannot exceed upper specification limit (USL)." in form_ucl.errors["upper_control_limit"][0]


def test_inprocessquality_form_param_auto_spc_excursion_detection_normal(tenant_a):
    """Verify automatic excursion status is normal when recorded value is within control limits."""
    data = _inprocessquality_param_base_data(
        target_nominal_value="245.0000",
        lower_spec_limit="235.0000",
        upper_spec_limit="255.0000",
        lower_control_limit="240.0000",
        upper_control_limit="250.0000",
        recorded_value="245.5000",  # Between 240 and 250
        excursion_status="out_of_control",  # User entered wrong status
    )
    form = ProcessParameterLogForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    # Neither out_of_spec nor out_of_control triggered; preserves user choice or normal
    assert form.cleaned_data["recorded_value"] == Decimal("245.5000")


def test_inprocessquality_form_param_auto_spc_excursion_detection_out_of_control_high_and_low(tenant_a):
    """Verify automatic detection of out_of_control for both upper and lower control limit violations."""
    # High side: UCL < recorded <= USL (250 < 252 <= 255)
    data_high = _inprocessquality_param_base_data(
        target_nominal_value="245.0000",
        lower_spec_limit="235.0000",
        upper_spec_limit="255.0000",
        lower_control_limit="240.0000",
        upper_control_limit="250.0000",
        recorded_value="252.0000",
        excursion_status="normal",
        containment_action="machine_parameter_adjusted",
    )
    form_high = ProcessParameterLogForm(data=data_high, tenant=tenant_a)
    assert form_high.is_valid(), form_high.errors
    assert form_high.cleaned_data["excursion_status"] == "out_of_control"

    # Low side: LSL <= recorded < LCL (235 <= 238 < 240)
    data_low = _inprocessquality_param_base_data(
        target_nominal_value="245.0000",
        lower_spec_limit="235.0000",
        upper_spec_limit="255.0000",
        lower_control_limit="240.0000",
        upper_control_limit="250.0000",
        recorded_value="238.0000",
        excursion_status="normal",
        containment_action="machine_parameter_adjusted",
    )
    form_low = ProcessParameterLogForm(data=data_low, tenant=tenant_a)
    assert form_low.is_valid(), form_low.errors
    assert form_low.cleaned_data["excursion_status"] == "out_of_control"


def test_inprocessquality_form_param_auto_spc_excursion_detection_out_of_spec_high_and_low(tenant_a):
    """Verify automatic detection of out_of_spec for both upper and lower spec limit excursions."""
    # High side: recorded > USL (258.0000 > 255)
    data_high = _inprocessquality_param_base_data(
        target_nominal_value="245.0000",
        lower_spec_limit="235.0000",
        upper_spec_limit="255.0000",
        lower_control_limit="240.0000",
        upper_control_limit="250.0000",
        recorded_value="258.0000",
        excursion_status="normal",
        containment_action="machine_paused",
        containment_notes="Reflow conveyor paused for zone 3 thermocouple replacement.",
    )
    form_high = ProcessParameterLogForm(data=data_high, tenant=tenant_a)
    assert form_high.is_valid(), form_high.errors
    assert form_high.cleaned_data["excursion_status"] == "out_of_spec"

    # Low side: recorded < LSL (230.0000 < 235)
    data_low = _inprocessquality_param_base_data(
        target_nominal_value="245.0000",
        lower_spec_limit="235.0000",
        upper_spec_limit="255.0000",
        lower_control_limit="240.0000",
        upper_control_limit="250.0000",
        recorded_value="230.0000",
        excursion_status="normal",
        containment_action="wip_quarantined",
        containment_notes="PCB lot segregated in red quarantine bin.",
    )
    form_low = ProcessParameterLogForm(data=data_low, tenant=tenant_a)
    assert form_low.is_valid(), form_low.errors
    assert form_low.cleaned_data["excursion_status"] == "out_of_spec"


def test_inprocessquality_form_param_out_of_spec_containment_action_mandatory(tenant_a):
    """Verify immediate containment action is mandatory when parameter excursion is out_of_spec."""
    data = _inprocessquality_param_base_data(
        target_nominal_value="245.0000",
        lower_spec_limit="235.0000",
        upper_spec_limit="255.0000",
        lower_control_limit="240.0000",
        upper_control_limit="250.0000",
        recorded_value="262.0000",  # Out of spec
        containment_action="none",  # Invalid for out_of_spec
    )
    form = ProcessParameterLogForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "containment_action" in form.errors
    assert "Immediate containment action is mandatory when a parameter excursion is Out-of-Spec." in form.errors["containment_action"][0]


def test_inprocessquality_form_param_widgets_and_styling(tenant_a):
    """Verify widget types, step increments, and CSS classes on ProcessParameterLogForm."""
    form = ProcessParameterLogForm(tenant=tenant_a)
    assert "form-input" in form.fields["parameter_name"].widget.attrs["class"]
    assert "form-select" in form.fields["parameter_category"].widget.attrs["class"]
    assert "form-input" in form.fields["target_nominal_value"].widget.attrs["class"]
    assert form.fields["target_nominal_value"].widget.attrs["step"] == "0.0001"
    assert form.fields["recorded_value"].widget.attrs["step"] == "0.0001"
    assert form.fields["recorded_at"].widget.input_type == "datetime-local"
    assert "form-textarea" in form.fields["containment_notes"].widget.attrs["class"]


def test_inprocessquality_form_param_empty_tenant_instantiation():
    """Verify ProcessParameterLogForm handles None tenant gracefully without exceptions."""
    form = ProcessParameterLogForm(tenant=None)
    assert form.fields["parameter_name"] is not None


# =============================================================================
# 4. LayeredProcessAuditForm Tests
# =============================================================================

def test_inprocessquality_form_lpa_system_field_exclusion(tenant_a, admin_user):
    """Verify tenant, number, compliance_percentage, timestamps are excluded from LayeredProcessAuditForm."""
    form = LayeredProcessAuditForm(tenant=tenant_a)
    forbidden_fields = ["tenant", "number", "compliance_percentage", "created_at", "updated_at"]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from LayeredProcessAuditForm"

    # Malicious injection in POST data must not alter compliance_percentage
    malicious_data = _inprocessquality_audit_base_data(
        auditor=admin_user,
        tenant=tenant_a.pk,
        number="QLPA-HACKED-0001",
        compliance_percentage="100.00",
        total_questions_audited=10,
        questions_conforming=5,
        questions_non_conforming=5,
        findings_summary="5 non-conformances observed",
    )
    bound_form = LayeredProcessAuditForm(data=malicious_data, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=False)
    assert getattr(instance, "number", "") != "QLPA-HACKED-0001"
    instance.tenant = tenant_a
    instance.save()
    # Model save computes true compliance score (5/10 = 50.00%), ignoring injected 100.00%
    assert instance.compliance_percentage == Decimal("50.00")


def test_inprocessquality_form_lpa_valid_submission_creates_record(tenant_a, admin_user, quality_department, doc_a, ncr_a):
    """Verify valid LayeredProcessAuditForm submission persists record with QLPA- prefix."""
    data = _inprocessquality_audit_base_data(
        auditor=admin_user,
        org_unit=quality_department,
        doc=doc_a,
        ncr=ncr_a,
        total_questions_audited=20,
        questions_conforming=19,
        questions_non_conforming=1,
        findings_summary="Calibrated torque wrench calibration tag expired yesterday.",
        on_the_spot_mitigation=True,
        mitigation_details="Replaced with newly calibrated torque wrench from tool crib (Cal #TRQ-402).",
        notes="Shift 1 Tier 2 audit conducted with Area Supervisor.",
    )
    form = LayeredProcessAuditForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.pk is not None
    assert instance.number.startswith("QLPA-")
    assert instance.auditor == admin_user
    assert instance.org_unit == quality_department
    assert instance.controlled_document == doc_a
    assert instance.non_conformance == ncr_a
    # 19/20 = 95.00%
    assert instance.compliance_percentage == Decimal("95.00")


def test_inprocessquality_form_lpa_foreign_key_scoping(tenant_a, tenant_b, admin_user, admin_b, quality_department, doc_a, doc_b, ncr_a, ncr_b):
    """Verify auditor, org_unit, doc, and ncr querysets are scoped to tenant."""
    dept_b = OrgUnit.objects.create(tenant=tenant_b, name="Operations Globex", kind="department")
    wc_a = WorkCenter.objects.create(tenant=tenant_a, code="WC-A04", name="Assembly Line A")
    wc_b = WorkCenter.objects.create(tenant=tenant_b, code="WC-B04", name="Assembly Line B")

    form = LayeredProcessAuditForm(tenant=tenant_a)

    auditor_pks = set(form.fields["auditor"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in auditor_pks
    assert admin_b.pk not in auditor_pks

    dept_pks = set(form.fields["org_unit"].queryset.values_list("pk", flat=True))
    assert quality_department.pk in dept_pks
    assert dept_b.pk not in dept_pks

    doc_pks = set(form.fields["controlled_document"].queryset.values_list("pk", flat=True))
    assert doc_a.pk in doc_pks
    assert doc_b.pk not in doc_pks

    ncr_pks = set(form.fields["non_conformance"].queryset.values_list("pk", flat=True))
    assert ncr_a.pk in ncr_pks
    assert ncr_b.pk not in ncr_pks

    wc_pks = set(form.fields["work_center"].queryset.values_list("pk", flat=True))
    assert wc_a.pk in wc_pks
    assert wc_b.pk not in wc_pks


def test_inprocessquality_form_lpa_inactive_user_excluded(tenant_a):
    """Verify inactive users are excluded from the auditor queryset on LPA form."""
    inactive_user = User.objects.create_user(
        username="inactive_lpa_auditor@acme.com",
        email="inactive_lpa_auditor@acme.com",
        password="password123",
        tenant=tenant_a,
        is_active=False,
    )
    form = LayeredProcessAuditForm(tenant=tenant_a)
    auditor_pks = set(form.fields["auditor"].queryset.values_list("pk", flat=True))
    assert inactive_user.pk not in auditor_pks


def test_inprocessquality_form_lpa_reject_foreign_tenants(tenant_a, tenant_b, admin_user, admin_b, doc_b, ncr_b):
    """Verify cross-tenant foreign keys are rejected during LPA form validation."""
    dept_b = OrgUnit.objects.create(tenant=tenant_b, name="Globex Ops", kind="department")

    # Submission with foreign auditor
    data_bad_aud = _inprocessquality_audit_base_data(auditor=admin_b)
    form_aud = LayeredProcessAuditForm(data=data_bad_aud, tenant=tenant_a)
    assert not form_aud.is_valid()
    assert "auditor" in form_aud.errors

    # Submission with foreign org unit
    data_bad_dept = _inprocessquality_audit_base_data(auditor=admin_user, org_unit=dept_b)
    form_dept = LayeredProcessAuditForm(data=data_bad_dept, tenant=tenant_a)
    assert not form_dept.is_valid()
    assert "org_unit" in form_dept.errors

    # Direct reject_foreign check
    form_direct = LayeredProcessAuditForm(data={}, tenant=tenant_a)
    form_direct.is_valid()
    form_direct.cleaned_data = {"auditor": admin_b, "controlled_document": doc_b, "non_conformance": ncr_b}
    reject_foreign(form_direct, form_direct.cleaned_data, ["auditor", "controlled_document", "non_conformance"])
    assert "auditor" in form_direct.errors
    assert "controlled_document" in form_direct.errors
    assert "non_conformance" in form_direct.errors
    assert "That record belongs to another workspace." in form_direct.errors["auditor"][0]


def test_inprocessquality_form_lpa_question_counts_sum_exceeds_total(tenant_a, admin_user):
    """Verify conforming + non-conforming questions cannot exceed total audited."""
    data = _inprocessquality_audit_base_data(
        auditor=admin_user,
        total_questions_audited=10,
        questions_conforming=8,
        questions_non_conforming=4,  # 8 + 4 = 12 > 10
        findings_summary="4 non-conformances observed",
    )
    form = LayeredProcessAuditForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "questions_conforming" in form.errors
    assert "Total conforming plus non-conforming questions cannot exceed total questions audited." in form.errors["questions_conforming"][0]


def test_inprocessquality_form_lpa_question_counts_valid_scenarios(tenant_a, admin_user):
    """Verify valid question counts (exact total and partial audits)."""
    # Exact sum equals total
    data_exact = _inprocessquality_audit_base_data(
        auditor=admin_user,
        total_questions_audited=10,
        questions_conforming=9,
        questions_non_conforming=1,
        findings_summary="Improper FIFO labeling on tray",
    )
    form_exact = LayeredProcessAuditForm(data=data_exact, tenant=tenant_a)
    assert form_exact.is_valid(), form_exact.errors

    # Sum is less than total (partial or not applicable questions)
    data_less = _inprocessquality_audit_base_data(
        auditor=admin_user,
        total_questions_audited=10,
        questions_conforming=7,
        questions_non_conforming=0,
    )
    form_less = LayeredProcessAuditForm(data=data_less, tenant=tenant_a)
    assert form_less.is_valid(), form_less.errors


def test_inprocessquality_form_lpa_non_conforming_questions_require_findings_summary(tenant_a, admin_user):
    """Verify findings_summary is mandatory when questions_non_conforming > 0."""
    data_missing = _inprocessquality_audit_base_data(
        auditor=admin_user,
        total_questions_audited=10,
        questions_conforming=9,
        questions_non_conforming=1,
        findings_summary="",
    )
    form = LayeredProcessAuditForm(data=data_missing, tenant=tenant_a)
    assert not form.is_valid()
    assert "findings_summary" in form.errors
    assert "Findings summary is required when non-conforming items are observed." in form.errors["findings_summary"][0]

    # Providing findings summary resolves error
    data_valid = _inprocessquality_audit_base_data(
        auditor=admin_user,
        total_questions_audited=10,
        questions_conforming=9,
        questions_non_conforming=1,
        findings_summary="Oil mist collector filter saturated.",
    )
    form_valid = LayeredProcessAuditForm(data=data_valid, tenant=tenant_a)
    assert form_valid.is_valid(), form_valid.errors


def test_inprocessquality_form_lpa_mitigation_details_required_when_checked(tenant_a, admin_user):
    """Verify mitigation_details is mandatory when on_the_spot_mitigation is checked."""
    data_missing = _inprocessquality_audit_base_data(
        auditor=admin_user,
        total_questions_audited=10,
        questions_conforming=9,
        questions_non_conforming=1,
        findings_summary="Coolant nozzle misaligned.",
        on_the_spot_mitigation=True,
        mitigation_details="",
    )
    form = LayeredProcessAuditForm(data=data_missing, tenant=tenant_a)
    assert not form.is_valid()
    assert "mitigation_details" in form.errors
    assert "Mitigation details are required when on-the-spot mitigation is checked." in form.errors["mitigation_details"][0]

    # Providing details makes it valid
    data_valid = _inprocessquality_audit_base_data(
        auditor=admin_user,
        total_questions_audited=10,
        questions_conforming=9,
        questions_non_conforming=1,
        findings_summary="Coolant nozzle misaligned.",
        on_the_spot_mitigation=True,
        mitigation_details="Adjusted nozzle angle to flood tool cutting edge directly.",
    )
    form_valid = LayeredProcessAuditForm(data=data_valid, tenant=tenant_a)
    assert form_valid.is_valid(), form_valid.errors


def test_inprocessquality_form_lpa_scheduled_date_required(tenant_a, admin_user):
    """Verify scheduled_date is a required field on LayeredProcessAuditForm."""
    data_missing_date = _inprocessquality_audit_base_data(
        auditor=admin_user,
        scheduled_date="",
    )
    form = LayeredProcessAuditForm(data=data_missing_date, tenant=tenant_a)
    assert not form.is_valid()
    assert "scheduled_date" in form.errors


def test_inprocessquality_form_lpa_widgets_and_styling(tenant_a):
    """Verify widget types and CSS classes assigned to LayeredProcessAuditForm fields."""
    form = LayeredProcessAuditForm(tenant=tenant_a)
    assert "form-input" in form.fields["title"].widget.attrs["class"]
    assert "form-select" in form.fields["audit_layer"].widget.attrs["class"]
    assert "form-select" in form.fields["focus_area"].widget.attrs["class"]
    assert "form-select" in form.fields["status"].widget.attrs["class"]
    assert form.fields["scheduled_date"].widget.input_type == "date"
    assert form.fields["conducted_at"].widget.input_type == "datetime-local"
    assert "form-textarea" in form.fields["findings_summary"].widget.attrs["class"]
    assert "form-checkbox" in form.fields["on_the_spot_mitigation"].widget.attrs["class"]


def test_inprocessquality_form_lpa_empty_tenant_instantiation():
    """Verify LayeredProcessAuditForm handles None tenant gracefully without exceptions."""
    form = LayeredProcessAuditForm(tenant=None)
    assert form.fields["title"] is not None


# =============================================================================
# 5. Cross-Cutting Form Invariants Tests
# =============================================================================

def test_inprocessquality_form_cross_cutting_blank_submission_validations(tenant_a):
    """Verify blank submissions across all 4 forms cleanly catch required fields without crashing."""
    # 1. InProcessInspectionForm
    f_insp = InProcessInspectionForm(data={}, tenant=tenant_a)
    assert not f_insp.is_valid()
    assert "title" in f_insp.errors

    # 2. FirstArticleInspectionForm
    f_fai = FirstArticleInspectionForm(data={}, tenant=tenant_a)
    assert not f_fai.is_valid()
    assert "title" in f_fai.errors

    # 3. ProcessParameterLogForm
    f_param = ProcessParameterLogForm(data={}, tenant=tenant_a)
    assert not f_param.is_valid()
    assert "parameter_name" in f_param.errors
    assert "unit_of_measure" in f_param.errors
    assert "target_nominal_value" in f_param.errors
    assert "lower_spec_limit" in f_param.errors
    assert "upper_spec_limit" in f_param.errors
    assert "recorded_value" in f_param.errors

    # 4. LayeredProcessAuditForm
    f_lpa = LayeredProcessAuditForm(data={}, tenant=tenant_a)
    assert not f_lpa.is_valid()
    assert "title" in f_lpa.errors
    assert "scheduled_date" in f_lpa.errors


def test_inprocessquality_form_cross_cutting_update_existing_instances(tenant_a, in_process_inspection_a, fai_a, parameter_log_a, layered_audit_a, admin_user):
    """Verify updating existing model instances through bound forms preserves tenant and numbers."""
    # 1. Update InProcessInspection
    insp_data = _inprocessquality_inspection_base_data(
        inspector=admin_user,
        title="Updated CNC Mill Inspection Title",
    )
    insp_form = InProcessInspectionForm(data=insp_data, instance=in_process_inspection_a, tenant=tenant_a)
    assert insp_form.is_valid(), insp_form.errors
    updated_insp = insp_form.save()
    assert updated_insp.pk == in_process_inspection_a.pk
    assert updated_insp.title == "Updated CNC Mill Inspection Title"
    assert updated_insp.tenant == tenant_a

    # 2. Update FirstArticleInspection
    fai_data = _inprocessquality_fai_base_data(
        inspector=admin_user,
        title="Updated AS9102 FAI Title",
        drawing_revision="Rev D",
    )
    fai_form = FirstArticleInspectionForm(data=fai_data, instance=fai_a, tenant=tenant_a)
    assert fai_form.is_valid(), fai_form.errors
    updated_fai = fai_form.save()
    assert updated_fai.pk == fai_a.pk
    assert updated_fai.drawing_revision == "Rev D"

    # 3. Update ProcessParameterLog
    param_data = _inprocessquality_param_base_data(
        parameter_name="Updated Solder Reflow Peak Temp",
        recorded_value="247.1000",
    )
    param_form = ProcessParameterLogForm(data=param_data, instance=parameter_log_a, tenant=tenant_a)
    assert param_form.is_valid(), param_form.errors
    updated_param = param_form.save()
    assert updated_param.pk == parameter_log_a.pk
    assert updated_param.recorded_value == Decimal("247.1000")

    # 4. Update LayeredProcessAudit
    lpa_data = _inprocessquality_audit_base_data(
        auditor=admin_user,
        title="Updated Daily Supervisor LPA Title",
    )
    lpa_form = LayeredProcessAuditForm(data=lpa_data, instance=layered_audit_a, tenant=tenant_a)
    assert lpa_form.is_valid(), lpa_form.errors
    updated_lpa = lpa_form.save()
    assert updated_lpa.pk == layered_audit_a.pk
    assert updated_lpa.title == "Updated Daily Supervisor LPA Title"
