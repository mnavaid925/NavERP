"""Form unit tests for Submodule 12.19 Laboratory Information Management (LIMS)."""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.quality.forms.LimsManagement.LabSamples import LabSampleForm
from apps.quality.forms.LimsManagement.LabSpecifications import LabSpecificationForm
from apps.quality.forms.LimsManagement.LabTestWorksheets import LabTestWorksheetForm
from apps.quality.forms.LimsManagement.OosInvestigations import OosInvestigationForm


@pytest.mark.django_db
def test_lims_sample_form_valid_and_exclusions(tenant_a, admin_user):
    form = LabSampleForm(
        tenant=tenant_a,
        data={
            "sample_name": "Stability Chamber A Sample",
            "sample_type": "stability",
            "status": "registered",
            "quantity_collected": "50.0000",
            "unit_of_measure": "g",
            "storage_condition": "refrigerated_2_8c",
            "storage_location": "Chamber A-01",
            "sampled_by": admin_user.pk,
            "sampled_at": "2026-11-20T10:00",
        },
    )
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.tenant == tenant_a
    assert instance.number.startswith("QSMP-")
    # Verify chain_of_custody_log has readonly widget
    assert form.fields["chain_of_custody_log"].widget.attrs.get("readonly") == "readonly"
    # Verify tenant and number are excluded
    assert "tenant" not in form.fields
    assert "number" not in form.fields


@pytest.mark.django_db
def test_lims_sample_form_reject_foreign_tenant(tenant_a, admin_b):
    form = LabSampleForm(
        tenant=tenant_a,
        data={
            "sample_name": "Cross-Tenant User Test",
            "sample_type": "raw_material",
            "status": "registered",
            "quantity_collected": "1.0000",
            "unit_of_measure": "g",
            "storage_condition": "ambient",
            "sampled_by": admin_b.pk,  # User from tenant_b
        },
    )
    assert not form.is_valid()
    assert "sampled_by" in form.errors


@pytest.mark.django_db
def test_lims_specification_form_limits_validation(tenant_a):
    # Invalid: lower_limit > upper_limit
    form = LabSpecificationForm(
        tenant=tenant_a,
        data={
            "title": "Invalid Limit Spec",
            "specification_type": "finished_product",
            "status": "draft",
            "test_category": "chemical",
            "version": "1.0",
            "product_code": "PRD-01",
            "product_name": "Product 01",
            "target_parameter_name": "Purity",
            "lower_limit": "105.0000",
            "upper_limit": "95.0000",
        },
    )
    assert not form.is_valid()
    assert "lower_limit" in form.errors


@pytest.mark.django_db
def test_lims_worksheet_form_qualitative_oos_preservation_c2(tenant_a, lab_sample_a, lab_specification_a, admin_user):
    # Numerical bounds pass (98.5 <= 99.5 <= 101.5), but user manually flags is_within_specification=False
    # Verify C2: qualitative OOS flag must NOT be overwritten to True!
    form = LabTestWorksheetForm(
        tenant=tenant_a,
        data={
            "title": "Particulate Defect Run",
            "sample": lab_sample_a.pk,
            "specification": lab_specification_a.pk,
            "status": "in_progress",
            "disposition": "oos_flagged",
            "assigned_analyst": admin_user.pk,
            "numeric_result": "99.5000",
            "is_within_specification": False,
            "qualitative_result": "Black particulate matter detected in solution",
        },
    )
    assert form.is_valid(), form.errors
    instance = form.save()
    assert not instance.is_within_specification
    assert instance.disposition == "oos_flagged"


@pytest.mark.django_db
def test_lims_worksheet_form_numeric_failure_flags_oos(tenant_a, lab_sample_a, lab_specification_a, admin_user):
    # Result = 95.0000, lower_limit is 98.5000 -> Out of Specification
    form = LabTestWorksheetForm(
        tenant=tenant_a,
        data={
            "title": "Low Assay Run",
            "sample": lab_sample_a.pk,
            "specification": lab_specification_a.pk,
            "status": "in_progress",
            "disposition": "conforms",  # user claimed conforms
            "assigned_analyst": admin_user.pk,
            "numeric_result": "95.0000",
            "is_within_specification": True,
        },
    )
    assert form.is_valid(), form.errors
    instance = form.save()
    assert not instance.is_within_specification
    assert instance.disposition == "oos_flagged"


@pytest.mark.django_db
def test_lims_oos_investigation_form_cross_record_consistency_i4(
    tenant_a, lab_test_worksheet_a, lab_sample_a, admin_user
):
    # Create an unrelated second sample in tenant_a
    other_sample = lab_sample_a.__class__.objects.create(
        tenant=tenant_a,
        sample_name="Unrelated Second Sample",
        sample_type="in_process",
    )
    # Attempt to pair lab_test_worksheet_a (linked to lab_sample_a) with other_sample
    form = OosInvestigationForm(
        tenant=tenant_a,
        data={
            "title": "Mismatched Sample-Worksheet OOS",
            "test_worksheet": lab_test_worksheet_a.pk,
            "sample": other_sample.pk,  # Mismatched!
            "investigation_phase": "phase_1_lab",
            "severity": "critical",
            "investigation_lead": admin_user.pk,
        },
    )
    assert not form.is_valid()
    assert "sample" in form.errors
    assert "Selected sample must match" in str(form.errors["sample"])
