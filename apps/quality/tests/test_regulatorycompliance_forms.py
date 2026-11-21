import pytest
from datetime import timedelta
from django.utils import timezone

from apps.quality.forms import (
    RegulatorySubmissionForm,
    ProductRegistrationForm,
    RegulatoryCommitmentForm,
    PostMarketSurveillanceReportForm,
)


@pytest.mark.django_db
def test_regulatorycompliance_submission_form_valid(tenant_a, regulatory_agency_party_a, quality_department, admin_user, doc_a):
    today = timezone.now().date()
    data = {
        "title": "CardioSense Premarket Notification 510(k)",
        "submission_type": "510k",
        "target_authority": regulatory_agency_party_a.pk,
        "org_unit": quality_department.pk,
        "product_name": "CardioSense Wireless Monitor",
        "product_code": "DPS",
        "device_class": "class_iib",
        "application_number": "K240999",
        "status": "draft",
        "planned_submission_date": today + timedelta(days=90),
        "lead_author": admin_user.pk,
        "technical_dossier": doc_a.pk,
        "technical_sections_summary": "Summary of verification testing.",
        "notes": "Testing notes.",
    }
    form = RegulatorySubmissionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_regulatorycompliance_submission_form_inverted_decision_date(tenant_a, admin_user):
    today = timezone.now().date()
    data = {
        "title": "Invalid Dates Submission",
        "submission_type": "510k",
        "product_name": "Device X",
        "actual_submission_date": today,
        "decision_date": today - timedelta(days=10),
    }
    form = RegulatorySubmissionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "decision_date" in form.errors
    assert "Decision date cannot be prior to actual submission date." in form.errors["decision_date"][0]


@pytest.mark.django_db
def test_regulatorycompliance_submission_form_reject_foreign_fk(tenant_a, regulatory_agency_party_b):
    data = {
        "title": "IDOR Probe Submission",
        "submission_type": "510k",
        "product_name": "Device X",
        "target_authority": regulatory_agency_party_b.pk,
    }
    form = RegulatorySubmissionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_authority" in form.errors


@pytest.mark.django_db
def test_regulatorycompliance_registration_form_valid(tenant_a, regulatory_agency_party_a, regulatory_submission_a, admin_user):
    today = timezone.now().date()
    data = {
        "registration_title": "US FDA 510(k) Device Listing",
        "registration_type": "national_listing",
        "jurisdiction_country": "USA",
        "regulatory_authority": regulatory_agency_party_a.pk,
        "product_name": "ApexVent V500",
        "product_code": "CBK",
        "intended_purpose": "Continuous ventilation.",
        "license_certificate_number": "D398201",
        "establishment_id": "FEI-3004819284",
        "status": "active",
        "initial_approval_date": today - timedelta(days=30),
        "effective_date": today - timedelta(days=30),
        "expiration_date": today + timedelta(days=335),
        "renewal_due_date": today + timedelta(days=245),
        "renewal_lead_days": 90,
        "regulatory_lead": admin_user.pk,
        "linked_submission": regulatory_submission_a.pk,
        "notes": "Testing notes.",
    }
    form = ProductRegistrationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_regulatorycompliance_registration_form_inverted_expiration(tenant_a, admin_user):
    today = timezone.now().date()
    data = {
        "registration_title": "Invalid Expiration Reg",
        "product_name": "Device Y",
        "jurisdiction_country": "Canada",
        "effective_date": today,
        "expiration_date": today - timedelta(days=30),
    }
    form = ProductRegistrationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "expiration_date" in form.errors
    assert "Expiration date cannot be prior to effective date." in form.errors["expiration_date"][0]


@pytest.mark.django_db
def test_regulatorycompliance_commitment_form_valid(tenant_a, regulatory_agency_party_a, regulatory_submission_a, admin_user):
    today = timezone.now().date()
    data = {
        "title": "Post-Approval Study Protocol",
        "commitment_type": "post_approval_study",
        "regulatory_agency": regulatory_agency_party_a.pk,
        "linked_submission": regulatory_submission_a.pk,
        "agency_reference_number": "FDA-Q01",
        "correspondence_date": today - timedelta(days=10),
        "commitment_description": "Submit interim safety data at 6 months.",
        "responsible_owner": admin_user.pk,
        "due_date": today + timedelta(days=180),
        "status": "in_progress",
        "verification_method": "Interim protocol.",
        "notes": "Testing notes.",
    }
    form = RegulatoryCommitmentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_regulatorycompliance_commitment_form_inverted_completion_date(tenant_a, admin_user):
    today = timezone.now().date()
    data = {
        "title": "Invalid Completion Commitment",
        "commitment_description": "Fix observation",
        "due_date": today + timedelta(days=30),
        "correspondence_date": today,
        "completion_date": today - timedelta(days=5),
    }
    form = RegulatoryCommitmentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "completion_date" in form.errors
    assert "Completion date cannot be prior to agency correspondence date." in form.errors["completion_date"][0]


@pytest.mark.django_db
def test_regulatorycompliance_pms_report_form_valid(tenant_a, product_registration_a, admin_user):
    today = timezone.now().date()
    data = {
        "report_title": "ApexVent 2026 Periodic Safety Update Report",
        "report_type": "psur",
        "product_registration": product_registration_a.pk,
        "device_model_family": "ApexVent Model Family",
        "reporting_period_start": today - timedelta(days=365),
        "reporting_period_end": today - timedelta(days=1),
        "units_distributed": 1200,
        "total_complaints_count": 14,
        "serious_incidents_count": 0,
        "field_actions_count": 0,
        "benefit_risk_conclusion": "favorable",
        "benefit_risk_rationale": "Benefits remain favorable.",
        "pmcf_action_required": False,
        "status": "draft",
        "prepared_by": admin_user.pk,
        "next_report_due_date": today + timedelta(days=364),
        "notes": "Annual evaluation completed.",
    }
    form = PostMarketSurveillanceReportForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_regulatorycompliance_pms_report_form_inverted_period(tenant_a):
    today = timezone.now().date()
    data = {
        "report_title": "Inverted Period PMS Report",
        "device_model_family": "Family Z",
        "reporting_period_start": today,
        "reporting_period_end": today - timedelta(days=30),
    }
    form = PostMarketSurveillanceReportForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "reporting_period_end" in form.errors
    assert "Reporting period end date cannot be prior to start date." in form.errors["reporting_period_end"][0]
