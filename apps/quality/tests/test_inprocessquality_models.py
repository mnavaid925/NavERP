"""Unit and invariant tests for Module 12.8 In-Process Quality Control (IPQC) models."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.quality.models import (
    ControlledDocument,
    FirstArticleInspection,
    InProcessInspection,
    LayeredProcessAudit,
    NonConformanceReport,
    ProcessDeviation,
    ProcessParameterLog,
)


# =============================================================================
# Helper Utilities
# =============================================================================

def _inprocessquality_sample_date(days_offset=0):
    """Return date relative to today."""
    return timezone.now().date() + timedelta(days=days_offset)


def _inprocessquality_sample_datetime(days_offset=0):
    """Return datetime relative to now."""
    return timezone.now() + timedelta(days=days_offset)


# =============================================================================
# 1. InProcessInspection Model Tests
# =============================================================================

@pytest.mark.django_db
def test_inprocessquality_inspection_creation_defaults_and_prefix(tenant_a, in_process_inspection_a):
    """Verify InProcessInspection prefix, number autogeneration, and default fields."""
    assert in_process_inspection_a.pk is not None
    assert in_process_inspection_a.NUMBER_PREFIX == "QIPQ"
    assert in_process_inspection_a.number.startswith("QIPQ-")
    assert in_process_inspection_a.title == "CNC Mill Line 2 In-Line Inspection"
    assert in_process_inspection_a.batch_quantity == 500
    assert in_process_inspection_a.sample_size_inspected == 5
    assert in_process_inspection_a.quantity_passed == 5
    assert in_process_inspection_a.quantity_rejected == 0

    # Minimal instance testing default fields
    insp_min = InProcessInspection.objects.create(
        tenant=tenant_a,
        title="Minimal In-Process Inspection",
    )
    assert insp_min.pk is not None
    assert insp_min.number.startswith("QIPQ-")
    assert insp_min.inspection_type == "visual_surface"
    assert insp_min.stage_gate == ""
    assert insp_min.status == "draft"
    assert insp_min.disposition == "pending"
    assert insp_min.production_order_number == ""
    assert insp_min.work_center_code == ""
    assert insp_min.operation_step == ""
    assert insp_min.item_code == ""
    assert insp_min.item_name == ""
    assert insp_min.lot_number == ""
    assert insp_min.serial_number == ""
    assert insp_min.batch_quantity == 1
    assert insp_min.sample_size_inspected == 1
    assert insp_min.quantity_passed == 0
    assert insp_min.quantity_rejected == 0
    assert insp_min.quantity_reworked == 0
    assert insp_min.defect_category == ""
    assert insp_min.defect_description == ""
    assert insp_min.work_instruction_step == ""
    assert insp_min.operator_sign_off is False
    assert insp_min.inspection_date is None
    assert insp_min.notes == ""


@pytest.mark.django_db
def test_inprocessquality_inspection_str_representation(tenant_a):
    """Verify InProcessInspection __str__ includes number, title, and disposition display."""
    insp = InProcessInspection.objects.create(
        tenant=tenant_a,
        title="Surface Roughness Check",
        disposition="pass",
    )
    expected = f"{insp.number} — Surface Roughness Check (Pass / Conforming)"
    assert str(insp) == expected


@pytest.mark.django_db
def test_inprocessquality_inspection_status_css_properties(tenant_a):
    """Verify status badge CSS mappings and fallback for unknown status."""
    insp = InProcessInspection.objects.create(
        tenant=tenant_a,
        title="Status CSS Check",
    )
    expected_status_map = {
        "draft": "badge-slate",
        "in_progress": "badge-amber",
        "completed": "badge-green",
        "cancelled": "badge-muted",
    }
    for choice, expected_badge in expected_status_map.items():
        insp.status = choice
        assert insp.status_css == expected_badge

    insp.status = "unknown_status"
    assert insp.status_css == "badge-slate"


@pytest.mark.django_db
def test_inprocessquality_inspection_disposition_css_properties(tenant_a):
    """Verify disposition badge CSS mappings and fallback for unknown disposition."""
    insp = InProcessInspection.objects.create(
        tenant=tenant_a,
        title="Disposition CSS Check",
    )
    expected_disp_map = {
        "pending": "badge-slate",
        "pass": "badge-green",
        "conditional_pass": "badge-info",
        "rework_required": "badge-amber",
        "reject_scrap": "badge-red",
        "quarantine_hold": "badge-red",
    }
    for choice, expected_badge in expected_disp_map.items():
        insp.disposition = choice
        assert insp.disposition_css == expected_badge

    insp.disposition = "unknown_disposition"
    assert insp.disposition_css == "badge-slate"


@pytest.mark.django_db
def test_inprocessquality_inspection_type_and_defect_css_properties(tenant_a):
    """Verify inspection type and defect category badge CSS mappings and fallbacks."""
    insp = InProcessInspection.objects.create(
        tenant=tenant_a,
        title="Type and Defect CSS Check",
    )
    expected_type_map = {
        "visual_surface": "badge-slate",
        "dimensional_gauging": "badge-info",
        "functional_test": "badge-amber",
        "automated_vision": "badge-info",
        "in_line_stage_gate": "badge-slate",
    }
    for choice, expected_badge in expected_type_map.items():
        insp.inspection_type = choice
        assert insp.type_css == expected_badge

    insp.inspection_type = "unlisted_type"
    assert insp.type_css == "badge-slate"

    expected_defect_map = {
        "": "badge-muted",
        "dimensional": "badge-amber",
        "surface_cosmetic": "badge-info",
        "functional_electrical": "badge-red",
        "material_flaw": "badge-red",
        "assembly_error": "badge-amber",
        "contamination": "badge-red",
        "other": "badge-slate",
    }
    for choice, expected_badge in expected_defect_map.items():
        insp.defect_category = choice
        assert insp.defect_css == expected_badge

    insp.defect_category = "unknown_defect"
    assert insp.defect_css == "badge-muted"

    assert insp.INSPECTION_TYPE_CSS == insp.TYPE_CSS
    assert insp.DEFECT_CATEGORY_CSS == insp.DEFECT_CSS


@pytest.mark.django_db
def test_inprocessquality_inspection_pass_rate_percentage(tenant_a):
    """Verify pass_rate_percentage property handles sample sizes and rounding correctly."""
    insp = InProcessInspection.objects.create(
        tenant=tenant_a,
        title="Pass Rate Check",
        sample_size_inspected=0,
        quantity_passed=0,
    )
    assert insp.pass_rate_percentage == 0.0

    insp.sample_size_inspected = 100
    insp.quantity_passed = 95
    assert insp.pass_rate_percentage == 95.0

    insp.sample_size_inspected = 7
    insp.quantity_passed = 5
    assert insp.pass_rate_percentage == 71.4

    insp.sample_size_inspected = 10
    insp.quantity_passed = 10
    assert insp.pass_rate_percentage == 100.0


@pytest.mark.django_db
def test_inprocessquality_inspection_is_failed_property(tenant_a):
    """Verify is_failed property flags scrap, quarantine, rework, or rejected quantity."""
    insp = InProcessInspection.objects.create(
        tenant=tenant_a,
        title="Failure Check",
        disposition="pass",
        quantity_rejected=0,
    )
    assert insp.is_failed is False

    insp.disposition = "conditional_pass"
    insp.quantity_rejected = 0
    assert insp.is_failed is False

    # Dispositions that constitute failure
    for failing_disp in ("reject_scrap", "quarantine_hold", "rework_required"):
        insp.disposition = failing_disp
        insp.quantity_rejected = 0
        assert insp.is_failed is True

    # Any rejected quantity also marks failure even if disposition is pass
    insp.disposition = "pass"
    insp.quantity_rejected = 1
    assert insp.is_failed is True


@pytest.mark.django_db
def test_inprocessquality_inspection_unique_tenant_number_constraint(tenant_a, tenant_b, in_process_inspection_a):
    """Verify unique constraint on (tenant, number) and cross-tenant independence."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            InProcessInspection.objects.create(
                tenant=tenant_a,
                number=in_process_inspection_a.number,
                title="Duplicate Number Inspection",
            )

    # Identical number under tenant_b must succeed
    insp_b = InProcessInspection.objects.create(
        tenant=tenant_b,
        number=in_process_inspection_a.number,
        title="Globex Same Number Inspection",
    )
    assert insp_b.pk is not None
    assert insp_b.number == in_process_inspection_a.number
    assert insp_b.tenant != in_process_inspection_a.tenant


@pytest.mark.django_db
def test_inprocessquality_inspection_foreign_keys_and_relations(
    tenant_a, admin_user, doc_a, ncr_a
):
    """Verify foreign key relations to operator, inspector, SOP document, and NCR."""
    today = _inprocessquality_sample_date()
    insp = InProcessInspection.objects.create(
        tenant=tenant_a,
        title="Linked Inspection",
        operator=admin_user,
        inspector=admin_user,
        controlled_document=doc_a,
        non_conformance=ncr_a,
        inspection_date=today,
    )
    assert insp.operator == admin_user
    assert insp.inspector == admin_user
    assert insp.controlled_document == doc_a
    assert insp.non_conformance == ncr_a

    assert admin_user.operator_in_process_inspections.filter(pk=insp.pk).exists()
    assert admin_user.conducted_in_process_inspections.filter(pk=insp.pk).exists()
    assert doc_a.in_process_inspections.filter(pk=insp.pk).exists()
    assert ncr_a.in_process_inspections.filter(pk=insp.pk).exists()


# =============================================================================
# 2. FirstArticleInspection Model Tests
# =============================================================================

@pytest.mark.django_db
def test_inprocessquality_fai_creation_defaults_and_prefix(tenant_a, fai_a):
    """Verify FirstArticleInspection prefix, autogenerated number, and default fields."""
    assert fai_a.pk is not None
    assert fai_a.NUMBER_PREFIX == "QFAI"
    assert fai_a.number.startswith("QFAI-")
    assert fai_a.title == "AS9102 Full FAI - Bracket"
    assert fai_a.fai_type == "full_fai"
    assert fai_a.setup_reason == "new_product_intro"
    assert fai_a.total_characteristics_inspected == 18
    assert fai_a.characteristics_conforming == 18
    assert fai_a.characteristics_out_of_spec == 0

    # Minimal instance testing default fields
    fai_min = FirstArticleInspection.objects.create(
        tenant=tenant_a,
        title="Minimal FAI",
    )
    assert fai_min.pk is not None
    assert fai_min.number.startswith("QFAI-")
    assert fai_min.fai_type == "full_fai"
    assert fai_min.setup_reason == "machine_setup_change"
    assert fai_min.status == "draft"
    assert fai_min.production_order_number == ""
    assert fai_min.work_center_code == ""
    assert fai_min.machine_tooling_id == ""
    assert fai_min.item_code == ""
    assert fai_min.item_name == ""
    assert fai_min.drawing_number == ""
    assert fai_min.drawing_revision == ""
    assert fai_min.first_piece_lot_number == ""
    assert fai_min.serial_number == ""
    assert fai_min.total_characteristics_inspected == 0
    assert fai_min.characteristics_conforming == 0
    assert fai_min.characteristics_out_of_spec == 0
    assert fai_min.max_deviation_found == ""
    assert fai_min.as9102_form1_complete is False
    assert fai_min.as9102_form2_complete is False
    assert fai_min.as9102_form3_complete is False
    assert fai_min.gage_serial_numbers == ""
    assert fai_min.release_verdict == "pending"
    assert fai_min.conditional_release_notes == ""
    assert fai_min.approved_by is None
    assert fai_min.approved_at is None
    assert fai_min.notes == ""


@pytest.mark.django_db
def test_inprocessquality_fai_str_representation(tenant_a):
    """Verify FirstArticleInspection __str__ includes number, title, and release verdict display."""
    fai = FirstArticleInspection.objects.create(
        tenant=tenant_a,
        title="Turbine Disk FAI",
        release_verdict="released",
    )
    expected = f"{fai.number} — Turbine Disk FAI (Full Production Run Released)"
    assert str(fai) == expected


@pytest.mark.django_db
def test_inprocessquality_fai_type_and_reason_css_properties(tenant_a):
    """Verify FAI type and setup reason badge CSS mappings and fallbacks."""
    fai = FirstArticleInspection.objects.create(
        tenant=tenant_a,
        title="FAI CSS Check",
    )
    expected_type_map = {
        "full_fai": "badge-info",
        "delta_partial_fai": "badge-slate",
    }
    for choice, expected_badge in expected_type_map.items():
        fai.fai_type = choice
        assert fai.type_css == expected_badge

    fai.fai_type = "unlisted_type"
    assert fai.type_css == "badge-slate"

    expected_reason_map = {
        "new_product_intro": "badge-info",
        "machine_setup_change": "badge-slate",
        "tooling_die_change": "badge-slate",
        "process_revision": "badge-amber",
        "material_lot_change": "badge-slate",
        "drawing_revision": "badge-amber",
        "periodic_recertification": "badge-info",
    }
    for choice, expected_badge in expected_reason_map.items():
        fai.setup_reason = choice
        assert fai.reason_css == expected_badge

    fai.setup_reason = "unknown_reason"
    assert fai.reason_css == "badge-slate"


@pytest.mark.django_db
def test_inprocessquality_fai_status_and_verdict_css_properties(tenant_a):
    """Verify status and release verdict badge CSS mappings and fallbacks."""
    fai = FirstArticleInspection.objects.create(
        tenant=tenant_a,
        title="FAI Status and Verdict CSS Check",
    )
    expected_status_map = {
        "draft": "badge-slate",
        "in_inspection": "badge-amber",
        "approved_run_released": "badge-green",
        "conditional_approval": "badge-info",
        "rejected_setup_hold": "badge-red",
        "cancelled": "badge-muted",
    }
    for choice, expected_badge in expected_status_map.items():
        fai.status = choice
        assert fai.status_css == expected_badge

    fai.status = "unknown_status"
    assert fai.status_css == "badge-slate"

    expected_verdict_map = {
        "pending": "badge-slate",
        "released": "badge-green",
        "conditional_pilot_release": "badge-info",
        "rejected_retool": "badge-red",
    }
    for choice, expected_badge in expected_verdict_map.items():
        fai.release_verdict = choice
        assert fai.verdict_css == expected_badge

    fai.release_verdict = "unknown_verdict"
    assert fai.verdict_css == "badge-slate"


@pytest.mark.django_db
def test_inprocessquality_fai_as9102_form_completeness(tenant_a):
    """Verify AS9102 form completeness booleans and as9102_completed_all property."""
    fai = FirstArticleInspection.objects.create(
        tenant=tenant_a,
        title="AS9102 Completeness Check",
    )
    assert fai.as9102_completed_all is False

    fai.as9102_form1_complete = True
    assert fai.as9102_completed_all is False

    fai.as9102_form2_complete = True
    assert fai.as9102_completed_all is False

    fai.as9102_form3_complete = True
    assert fai.as9102_completed_all is True

    fai.as9102_form1_complete = False
    assert fai.as9102_completed_all is False


@pytest.mark.django_db
def test_inprocessquality_fai_conformance_rate(tenant_a):
    """Verify conformance_rate property calculation and zero-sample safety."""
    fai = FirstArticleInspection.objects.create(
        tenant=tenant_a,
        title="Conformance Rate Check",
        total_characteristics_inspected=0,
        characteristics_conforming=0,
    )
    assert fai.conformance_rate == 0.0

    fai.total_characteristics_inspected = 25
    fai.characteristics_conforming = 25
    assert fai.conformance_rate == 100.0

    fai.characteristics_conforming = 24
    assert fai.conformance_rate == 96.0

    fai.total_characteristics_inspected = 3
    fai.characteristics_conforming = 2
    assert fai.conformance_rate == 66.7


@pytest.mark.django_db
def test_inprocessquality_fai_is_approved_property(tenant_a):
    """Verify is_approved property checks status and release_verdict."""
    fai = FirstArticleInspection.objects.create(
        tenant=tenant_a,
        title="Approval Check",
        status="draft",
        release_verdict="pending",
    )
    assert fai.is_approved is False

    # Status matches approved_run_released
    fai.status = "approved_run_released"
    fai.release_verdict = "pending"
    assert fai.is_approved is True

    # Verdict matches released
    fai.status = "draft"
    fai.release_verdict = "released"
    assert fai.is_approved is True

    # Rejected status and verdict
    fai.status = "rejected_setup_hold"
    fai.release_verdict = "rejected_retool"
    assert fai.is_approved is False

    # Conditional approval
    fai.status = "conditional_approval"
    fai.release_verdict = "conditional_pilot_release"
    assert fai.is_approved is False


@pytest.mark.django_db
def test_inprocessquality_fai_unique_tenant_number_constraint(tenant_a, tenant_b, fai_a):
    """Verify unique constraint on (tenant, number) for FirstArticleInspection."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FirstArticleInspection.objects.create(
                tenant=tenant_a,
                number=fai_a.number,
                title="Duplicate Number FAI",
            )

    fai_b = FirstArticleInspection.objects.create(
        tenant=tenant_b,
        number=fai_a.number,
        title="Globex Same Number FAI",
    )
    assert fai_b.pk is not None
    assert fai_b.number == fai_a.number
    assert fai_b.tenant != fai_a.tenant


@pytest.mark.django_db
def test_inprocessquality_fai_foreign_keys_and_approval_workflow(
    tenant_a, admin_user, ncr_a
):
    """Verify FAI foreign keys to inspector, approved_by, and non_conformance."""
    now = timezone.now()
    fai = FirstArticleInspection.objects.create(
        tenant=tenant_a,
        title="Approved Aerospace FAI",
        inspector=admin_user,
        approved_by=admin_user,
        approved_at=now,
        non_conformance=ncr_a,
    )
    assert fai.inspector == admin_user
    assert fai.approved_by == admin_user
    assert fai.approved_at == now
    assert fai.non_conformance == ncr_a

    assert admin_user.inspected_fais.filter(pk=fai.pk).exists()
    assert admin_user.approved_fais.filter(pk=fai.pk).exists()
    assert ncr_a.fais.filter(pk=fai.pk).exists()


# =============================================================================
# 3. ProcessParameterLog Model Tests
# =============================================================================

@pytest.mark.django_db
def test_inprocessquality_parameter_log_creation_defaults_and_prefix(tenant_a, parameter_log_a):
    """Verify ProcessParameterLog prefix, autogenerated number, and default fields."""
    assert parameter_log_a.pk is not None
    assert parameter_log_a.NUMBER_PREFIX == "QPAR"
    assert parameter_log_a.number.startswith("QPAR-")
    assert parameter_log_a.parameter_name == "Reflow Temperature"
    assert parameter_log_a.parameter_category == "temperature"
    assert parameter_log_a.unit_of_measure == "°C"
    assert parameter_log_a.target_nominal_value == Decimal("245.0000")
    assert parameter_log_a.recorded_value == Decimal("246.2000")
    assert parameter_log_a.excursion_status == "normal"

    # Minimal instance testing default fields
    log_min = ProcessParameterLog.objects.create(
        tenant=tenant_a,
        parameter_name="Spindle Speed",
        unit_of_measure="RPM",
        target_nominal_value=Decimal("1200.0000"),
        upper_spec_limit=Decimal("1250.0000"),
        lower_spec_limit=Decimal("1150.0000"),
        recorded_value=Decimal("1210.0000"),
    )
    assert log_min.pk is not None
    assert log_min.number.startswith("QPAR-")
    assert log_min.parameter_category == "temperature"
    assert log_min.work_center_code == ""
    assert log_min.production_order_number == ""
    assert log_min.operation_step == ""
    assert log_min.item_code == ""
    assert log_min.lot_number == ""
    assert log_min.upper_control_limit is None
    assert log_min.lower_control_limit is None
    assert log_min.recorded_at is not None
    assert log_min.excursion_status == "normal"
    assert log_min.containment_action == "none"
    assert log_min.containment_notes == ""
    assert log_min.logged_by is None


@pytest.mark.django_db
def test_inprocessquality_parameter_log_str_representation(tenant_a):
    """Verify ProcessParameterLog __str__ format."""
    log = ProcessParameterLog.objects.create(
        tenant=tenant_a,
        parameter_name="Bake Temperature",
        unit_of_measure="°C",
        target_nominal_value=Decimal("150.0000"),
        upper_spec_limit=Decimal("160.0000"),
        lower_spec_limit=Decimal("140.0000"),
        recorded_value=Decimal("152.5000"),
        excursion_status="normal",
    )
    expected = f"{log.number} — Bake Temperature: 152.5000 °C (Normal (In Control & In Spec))"
    assert str(log) == expected


@pytest.mark.django_db
def test_inprocessquality_parameter_log_css_properties(tenant_a):
    """Verify excursion, category, and containment CSS class mappings and fallbacks."""
    log = ProcessParameterLog.objects.create(
        tenant=tenant_a,
        parameter_name="Parameter CSS Check",
        unit_of_measure="bar",
        target_nominal_value=Decimal("10.0000"),
        upper_spec_limit=Decimal("12.0000"),
        lower_spec_limit=Decimal("8.0000"),
        recorded_value=Decimal("10.5000"),
    )

    expected_excursion_map = {
        "normal": "badge-green",
        "warning_pre_control": "badge-amber",
        "out_of_control": "badge-amber",
        "out_of_spec": "badge-red",
    }
    for choice, expected_badge in expected_excursion_map.items():
        log.excursion_status = choice
        assert log.excursion_css == expected_badge

    log.excursion_status = "unknown_excursion"
    assert log.excursion_css == "badge-slate"

    expected_category_map = {
        "temperature": "badge-red",
        "pressure": "badge-amber",
        "speed_feed": "badge-info",
        "torque": "badge-slate",
        "ph_chemical": "badge-info",
        "humidity": "badge-slate",
        "dimensional_thickness": "badge-info",
        "voltage_current": "badge-amber",
        "cycle_time": "badge-slate",
        "other": "badge-muted",
    }
    for choice, expected_badge in expected_category_map.items():
        log.parameter_category = choice
        assert log.category_css == expected_badge

    log.parameter_category = "unknown_category"
    assert log.category_css == "badge-slate"

    expected_containment_map = {
        "none": "badge-slate",
        "machine_parameter_adjusted": "badge-info",
        "machine_paused": "badge-amber",
        "wip_quarantined": "badge-red",
        "supervisor_escalated": "badge-amber",
        "ncr_initiated": "badge-red",
    }
    for choice, expected_badge in expected_containment_map.items():
        log.containment_action = choice
        assert log.containment_css == expected_badge

    log.containment_action = "unknown_containment"
    assert log.containment_css == "badge-slate"


@pytest.mark.django_db
def test_inprocessquality_parameter_log_excursion_status_properties(tenant_a):
    """Verify is_out_of_spec and is_out_of_control properties across excursion statuses."""
    log = ProcessParameterLog.objects.create(
        tenant=tenant_a,
        parameter_name="Limits Check",
        unit_of_measure="bar",
        target_nominal_value=Decimal("10.0000"),
        upper_spec_limit=Decimal("12.0000"),
        lower_spec_limit=Decimal("8.0000"),
        recorded_value=Decimal("10.0000"),
        excursion_status="normal",
    )
    assert log.is_out_of_spec is False
    assert log.is_out_of_control is False

    log.excursion_status = "warning_pre_control"
    assert log.is_out_of_spec is False
    assert log.is_out_of_control is False

    log.excursion_status = "out_of_control"
    assert log.is_out_of_spec is False
    assert log.is_out_of_control is True

    log.excursion_status = "out_of_spec"
    assert log.is_out_of_spec is True
    assert log.is_out_of_control is True


@pytest.mark.django_db
def test_inprocessquality_parameter_log_deviation_from_target(tenant_a):
    """Verify deviation_from_target calculation and None safety."""
    log = ProcessParameterLog.objects.create(
        tenant=tenant_a,
        parameter_name="Deviation Check",
        unit_of_measure="°C",
        target_nominal_value=Decimal("245.0000"),
        upper_spec_limit=Decimal("255.0000"),
        lower_spec_limit=Decimal("235.0000"),
        recorded_value=Decimal("246.2345"),
    )
    assert log.deviation_from_target == Decimal("1.2345")

    log.recorded_value = Decimal("243.8000")
    assert log.deviation_from_target == Decimal("-1.2000")

    log.target_nominal_value = None
    assert log.deviation_from_target == Decimal("0.0000")


@pytest.mark.django_db
def test_inprocessquality_parameter_log_unique_tenant_number_constraint(
    tenant_a, tenant_b, parameter_log_a
):
    """Verify unique constraint on (tenant, number) for ProcessParameterLog."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ProcessParameterLog.objects.create(
                tenant=tenant_a,
                number=parameter_log_a.number,
                parameter_name="Duplicate Log",
                unit_of_measure="bar",
                target_nominal_value=Decimal("5.0000"),
                upper_spec_limit=Decimal("6.0000"),
                lower_spec_limit=Decimal("4.0000"),
                recorded_value=Decimal("5.1000"),
            )

    log_b = ProcessParameterLog.objects.create(
        tenant=tenant_b,
        number=parameter_log_a.number,
        parameter_name="Globex Same Number Log",
        unit_of_measure="bar",
        target_nominal_value=Decimal("5.0000"),
        upper_spec_limit=Decimal("6.0000"),
        lower_spec_limit=Decimal("4.0000"),
        recorded_value=Decimal("5.1000"),
    )
    assert log_b.pk is not None
    assert log_b.number == parameter_log_a.number
    assert log_b.tenant != parameter_log_a.tenant


@pytest.mark.django_db
def test_inprocessquality_parameter_log_foreign_keys(
    tenant_a, admin_user, ncr_a, process_deviation_a
):
    """Verify parameter log foreign keys to logged_by, non_conformance, and process_deviation."""
    log = ProcessParameterLog.objects.create(
        tenant=tenant_a,
        parameter_name="Anodizing Bath pH",
        unit_of_measure="pH",
        target_nominal_value=Decimal("7.0000"),
        upper_spec_limit=Decimal("7.5000"),
        lower_spec_limit=Decimal("6.5000"),
        recorded_value=Decimal("7.8000"),
        excursion_status="out_of_spec",
        containment_action="ncr_initiated",
        logged_by=admin_user,
        non_conformance=ncr_a,
        process_deviation=process_deviation_a,
    )
    assert log.logged_by == admin_user
    assert log.non_conformance == ncr_a
    assert log.process_deviation == process_deviation_a

    assert admin_user.logged_parameters.filter(pk=log.pk).exists()
    assert ncr_a.parameter_logs.filter(pk=log.pk).exists()
    assert process_deviation_a.parameter_logs.filter(pk=log.pk).exists()


# =============================================================================
# 4. LayeredProcessAudit Model Tests
# =============================================================================

@pytest.mark.django_db
def test_inprocessquality_lpa_creation_defaults_and_prefix(tenant_a, layered_audit_a):
    """Verify LayeredProcessAudit prefix, autogenerated number, and default fields."""
    assert layered_audit_a.pk is not None
    assert layered_audit_a.NUMBER_PREFIX == "QLPA"
    assert layered_audit_a.number.startswith("QLPA-")
    assert layered_audit_a.title == "Daily Supervisor LPA"
    assert layered_audit_a.audit_layer == "tier_2_supervisor"
    assert layered_audit_a.focus_area == "standard_work_wi"
    assert layered_audit_a.total_questions_audited == 10
    assert layered_audit_a.questions_conforming == 10
    assert layered_audit_a.questions_non_conforming == 0
    assert layered_audit_a.compliance_percentage == Decimal("100.00")

    today = _inprocessquality_sample_date()
    lpa_min = LayeredProcessAudit.objects.create(
        tenant=tenant_a,
        title="Minimal LPA Checklist",
        scheduled_date=today,
    )
    assert lpa_min.pk is not None
    assert lpa_min.number.startswith("QLPA-")
    assert lpa_min.audit_layer == "tier_1_operator_lead"
    assert lpa_min.focus_area == "standard_work_wi"
    assert lpa_min.status == "scheduled"
    assert lpa_min.work_center_code == ""
    assert lpa_min.shift == ""
    assert lpa_min.total_questions_audited == 10
    assert lpa_min.questions_conforming == 10
    assert lpa_min.questions_non_conforming == 0
    assert lpa_min.compliance_percentage == Decimal("100.00")
    assert lpa_min.findings_summary == ""
    assert lpa_min.on_the_spot_mitigation is False
    assert lpa_min.mitigation_details == ""
    assert lpa_min.auditor is None
    assert lpa_min.conducted_at is None
    assert lpa_min.notes == ""


@pytest.mark.django_db
def test_inprocessquality_lpa_str_representation(tenant_a):
    """Verify LayeredProcessAudit __str__ format."""
    today = _inprocessquality_sample_date()
    lpa = LayeredProcessAudit.objects.create(
        tenant=tenant_a,
        title="Weekly Tier 2 LPA",
        audit_layer="tier_2_supervisor",
        scheduled_date=today,
    )
    expected = f"{lpa.number} — Weekly Tier 2 LPA (Tier 2: Area Production Supervisor (Weekly))"
    assert str(lpa) == expected


@pytest.mark.django_db
def test_inprocessquality_lpa_css_properties(tenant_a):
    """Verify audit_layer, focus_area, and status badge CSS class mappings and fallbacks."""
    today = _inprocessquality_sample_date()
    lpa = LayeredProcessAudit.objects.create(
        tenant=tenant_a,
        title="LPA CSS Check",
        scheduled_date=today,
    )

    expected_layer_map = {
        "tier_1_operator_lead": "badge-slate",
        "tier_2_supervisor": "badge-info",
        "tier_3_quality_manager": "badge-amber",
        "tier_4_plant_executive": "badge-green",
    }
    for choice, expected_badge in expected_layer_map.items():
        lpa.audit_layer = choice
        assert lpa.layer_css == expected_badge

    lpa.audit_layer = "unknown_layer"
    assert lpa.layer_css == "badge-slate"

    expected_focus_map = {
        "standard_work_wi": "badge-info",
        "tooling_machine_setup": "badge-slate",
        "material_handling_fifo": "badge-slate",
        "gauging_calibration": "badge-info",
        "environmental_5s": "badge-green",
        "safety_poka_yoke": "badge-amber",
    }
    for choice, expected_badge in expected_focus_map.items():
        lpa.focus_area = choice
        assert lpa.focus_css == expected_badge

    lpa.focus_area = "unknown_focus"
    assert lpa.focus_css == "badge-slate"

    expected_status_map = {
        "scheduled": "badge-slate",
        "in_progress": "badge-amber",
        "completed": "badge-green",
        "cancelled": "badge-muted",
    }
    for choice, expected_badge in expected_status_map.items():
        lpa.status = choice
        assert lpa.status_css == expected_badge

    lpa.status = "unknown_status"
    assert lpa.status_css == "badge-slate"


@pytest.mark.django_db
def test_inprocessquality_lpa_save_compliance_score_calculation(tenant_a):
    """Verify save() compliance score calculation and clamping between 0.00 and 100.00."""
    today = _inprocessquality_sample_date()
    lpa = LayeredProcessAudit(
        tenant=tenant_a,
        title="Score Calculation LPA",
        scheduled_date=today,
        total_questions_audited=10,
        questions_conforming=10,
    )
    lpa.save()
    assert lpa.compliance_percentage == Decimal("100.00")

    # 8 of 10 conforming => 80.00%
    lpa.questions_conforming = 8
    lpa.save()
    assert lpa.compliance_percentage == Decimal("80.00")

    # 9 of 10 conforming => 90.00%
    lpa.questions_conforming = 9
    lpa.save()
    assert lpa.compliance_percentage == Decimal("90.00")

    # 1 of 3 conforming => 33.33%
    lpa.total_questions_audited = 3
    lpa.questions_conforming = 1
    lpa.save()
    assert lpa.compliance_percentage == Decimal("33.33")

    # 0 conforming => 0.00%
    lpa.total_questions_audited = 10
    lpa.questions_conforming = 0
    lpa.save()
    assert lpa.compliance_percentage == Decimal("0.00")

    # Over-conforming (e.g. 15 of 10) => clamped to 100.00%
    lpa.total_questions_audited = 10
    lpa.questions_conforming = 15
    lpa.save()
    assert lpa.compliance_percentage == Decimal("100.00")

    # total_questions_audited = 0 does not divide by zero
    lpa.total_questions_audited = 0
    lpa.save()
    # Preserves previous compliance_percentage
    assert lpa.compliance_percentage == Decimal("100.00")


@pytest.mark.django_db
def test_inprocessquality_lpa_compliance_rate_display_and_passing(tenant_a):
    """Verify compliance_rate_display formatting and is_passing threshold (>= 90%)."""
    today = _inprocessquality_sample_date()
    lpa = LayeredProcessAudit.objects.create(
        tenant=tenant_a,
        title="Passing Threshold LPA",
        scheduled_date=today,
        total_questions_audited=10,
        questions_conforming=10,
    )
    assert lpa.compliance_rate_display == "100.00%"
    assert lpa.is_passing is True

    # 90.00% is exactly passing
    lpa.questions_conforming = 9
    lpa.save()
    assert lpa.compliance_rate_display == "90.00%"
    assert lpa.is_passing is True

    # 89.99% is failing
    lpa.compliance_percentage = Decimal("89.99")
    assert lpa.compliance_rate_display == "89.99%"
    assert lpa.is_passing is False

    # 50.00% is failing
    lpa.questions_conforming = 5
    lpa.save()
    assert lpa.compliance_rate_display == "50.00%"
    assert lpa.is_passing is False


@pytest.mark.django_db
def test_inprocessquality_lpa_unique_tenant_number_constraint(tenant_a, tenant_b, layered_audit_a):
    """Verify unique constraint on (tenant, number) for LayeredProcessAudit."""
    today = _inprocessquality_sample_date()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            LayeredProcessAudit.objects.create(
                tenant=tenant_a,
                number=layered_audit_a.number,
                title="Duplicate Number LPA",
                scheduled_date=today,
            )

    lpa_b = LayeredProcessAudit.objects.create(
        tenant=tenant_b,
        number=layered_audit_a.number,
        title="Globex Same Number LPA",
        scheduled_date=today,
    )
    assert lpa_b.pk is not None
    assert lpa_b.number == layered_audit_a.number
    assert lpa_b.tenant != layered_audit_a.tenant


@pytest.mark.django_db
def test_inprocessquality_lpa_foreign_keys_and_relations(
    tenant_a, admin_user, quality_department, doc_a, ncr_a
):
    """Verify LPA foreign keys to auditor, org_unit, controlled_document, and non_conformance."""
    today = _inprocessquality_sample_date()
    lpa = LayeredProcessAudit.objects.create(
        tenant=tenant_a,
        title="Comprehensive LPA Audit",
        scheduled_date=today,
        auditor=admin_user,
        org_unit=quality_department,
        controlled_document=doc_a,
        non_conformance=ncr_a,
    )
    assert lpa.auditor == admin_user
    assert lpa.org_unit == quality_department
    assert lpa.controlled_document == doc_a
    assert lpa.non_conformance == ncr_a

    assert admin_user.conducted_lpas.filter(pk=lpa.pk).exists()
    assert quality_department.quality_lpas.filter(pk=lpa.pk).exists()
    assert doc_a.lpa_audits.filter(pk=lpa.pk).exists()
    assert ncr_a.lpas.filter(pk=lpa.pk).exists()
