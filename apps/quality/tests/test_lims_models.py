"""Model unit tests for Submodule 12.19 Laboratory Information Management (LIMS)."""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.quality.models import (
    LabSample,
    LabSpecification,
    LabTestWorksheet,
    OosInvestigation,
)


@pytest.mark.django_db
def test_lims_sample_creation_numbering_and_str(tenant_a, admin_user):
    sample = LabSample.objects.create(
        tenant=tenant_a,
        sample_name="Purified Water Loop 1 Sample",
        sample_type="water_purified",
        status="registered",
        matrix_description="High purity water",
        sampled_by=admin_user,
        quantity_collected=Decimal("100.0000"),
        unit_of_measure="mL",
    )
    assert sample.number.startswith("QSMP-")
    assert str(sample) == f"{sample.number} - Purified Water Loop 1 Sample (Purified Water / Utility)"
    assert not sample.is_received
    assert not sample.can_test
    assert sample.get_status_badge() == "badge-slate"
    assert sample.get_sample_type_badge() == "badge-info"


@pytest.mark.django_db
def test_lims_sample_status_properties(lab_sample_a):
    assert lab_sample_a.is_received
    assert lab_sample_a.can_test
    assert lab_sample_a.get_status_badge() == "badge-info"

    lab_sample_a.status = "approved"
    lab_sample_a.save()
    assert lab_sample_a.is_received
    assert not lab_sample_a.can_test
    assert lab_sample_a.get_status_badge() == "badge-green"


@pytest.mark.django_db
def test_lims_sample_quantity_validator(tenant_a, admin_user):
    sample = LabSample(
        tenant=tenant_a,
        sample_name="Invalid Negative Sample",
        quantity_collected=Decimal("-5.0000"),
    )
    with pytest.raises(ValidationError):
        sample.full_clean()


@pytest.mark.django_db
def test_lims_specification_creation_and_properties(tenant_a, admin_user):
    today = timezone.now().date()
    spec = LabSpecification.objects.create(
        tenant=tenant_a,
        title="Ventilator O2 Sensor Spec",
        specification_type="in_process",
        status="approved",
        version="1.2",
        product_code="SENS-O2",
        product_name="Oxygen Sensor Transducer",
        analytical_method_number="AM-SENS-09",
        test_category="chromatographic",
        target_parameter_name="Oxygen Concentration",
        parameter_unit="%",
        lower_limit=Decimal("99.0000"),
        upper_limit=Decimal("100.0000"),
        effective_date=today - timedelta(days=400),
        review_due_date=today - timedelta(days=10),
        approved_by=admin_user,
    )
    assert spec.number.startswith("QSPC-")
    assert str(spec) == f"{spec.number} - Ventilator O2 Sensor Spec v1.2 (SENS-O2)"
    assert spec.is_active
    assert spec.is_overdue_review
    assert spec.get_status_badge() == "badge-green"
    # Ensure badge-purple was fixed to badge-info per I7
    assert spec.get_test_category_badge() == "badge-info"


@pytest.mark.django_db
def test_lims_test_worksheet_properties_and_expiry(lab_test_worksheet_a):
    today = timezone.now().date()
    assert lab_test_worksheet_a.number.startswith("QWKS-")
    assert not lab_test_worksheet_a.is_overdue
    assert not lab_test_worksheet_a.reagent_expired
    assert not lab_test_worksheet_a.standards_expired
    assert lab_test_worksheet_a.get_status_badge() == "badge-amber"
    assert lab_test_worksheet_a.get_disposition_badge() == "badge-slate"

    # Test overdue condition
    lab_test_worksheet_a.scheduled_date = today - timedelta(days=2)
    assert lab_test_worksheet_a.is_overdue

    # Test expired reagent
    lab_test_worksheet_a.reagent_expiry_date = today - timedelta(days=1)
    assert lab_test_worksheet_a.reagent_expired

    # Test expired standards
    lab_test_worksheet_a.standards_expiry_date = today - timedelta(days=1)
    assert lab_test_worksheet_a.standards_expired


@pytest.mark.django_db
def test_lims_worksheet_rsd_negative_validator(tenant_a, lab_sample_a, lab_specification_a):
    wks = LabTestWorksheet(
        tenant=tenant_a,
        title="Invalid RSD Worksheet",
        sample=lab_sample_a,
        specification=lab_specification_a,
        relative_standard_deviation=Decimal("-1.50"),
    )
    with pytest.raises(ValidationError):
        wks.full_clean()


@pytest.mark.django_db
def test_lims_oos_investigation_creation_and_badges(oos_investigation_a):
    assert oos_investigation_a.number.startswith("QOOS-")
    assert oos_investigation_a.get_phase_badge() == "badge-amber"
    assert oos_investigation_a.get_status_badge() == "badge-amber"
    assert oos_investigation_a.get_severity_badge() == "badge-red"

    # Test root_cause_found badge is badge-info (not badge-purple)
    oos_investigation_a.status = "root_cause_found"
    assert oos_investigation_a.get_status_badge() == "badge-info"


@pytest.mark.django_db
def test_lims_tenant_unique_constraint(tenant_a, lab_sample_a):
    with pytest.raises(IntegrityError):
        LabSample.objects.create(
            tenant=tenant_a,
            number=lab_sample_a.number,
            sample_name="Duplicate Number Sample",
        )
