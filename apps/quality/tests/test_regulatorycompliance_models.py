import pytest
from datetime import timedelta
from django.db import IntegrityError
from django.utils import timezone

from apps.quality.models import (
    RegulatorySubmission,
    ProductRegistration,
    RegulatoryCommitment,
    PostMarketSurveillanceReport,
)


@pytest.mark.django_db
def test_regulatorycompliance_submission_str(regulatory_submission_a):
    expected = f"{regulatory_submission_a.number} — {regulatory_submission_a.title}"
    assert str(regulatory_submission_a) == expected


@pytest.mark.django_db
def test_regulatorycompliance_submission_properties(regulatory_submission_a):
    assert regulatory_submission_a.is_submitted is True
    assert regulatory_submission_a.is_approved is True
    assert regulatory_submission_a.days_under_review == 160
    assert regulatory_submission_a.status_css == "badge-green"

    regulatory_submission_a.status = "draft"
    regulatory_submission_a.actual_submission_date = None
    assert regulatory_submission_a.is_submitted is False
    assert regulatory_submission_a.is_approved is False
    assert regulatory_submission_a.days_under_review == 0
    assert regulatory_submission_a.status_css == "badge-slate"


@pytest.mark.django_db
def test_regulatorycompliance_submission_prefix(regulatory_submission_a):
    assert regulatory_submission_a.NUMBER_PREFIX == "QSUB"
    assert regulatory_submission_a.number.startswith("QSUB-")


@pytest.mark.django_db
def test_regulatorycompliance_registration_str(product_registration_a):
    expected = f"{product_registration_a.number} — {product_registration_a.product_name} ({product_registration_a.jurisdiction_country})"
    assert str(product_registration_a) == expected


@pytest.mark.django_db
def test_regulatorycompliance_registration_properties(product_registration_a):
    assert product_registration_a.is_active is True
    assert product_registration_a.days_to_expiration == 290
    assert product_registration_a.is_overdue_renewal is False
    assert product_registration_a.urgency_status == "normal"
    assert product_registration_a.status_css == "badge-green"

    today = timezone.now().date()
    product_registration_a.expiration_date = today - timedelta(days=5)
    assert product_registration_a.urgency_status == "expired"

    product_registration_a.expiration_date = today + timedelta(days=20)
    assert product_registration_a.urgency_status == "urgent"

    product_registration_a.expiration_date = today + timedelta(days=60)
    assert product_registration_a.urgency_status == "warning"

    product_registration_a.expiration_date = None
    assert product_registration_a.days_to_expiration is None
    assert product_registration_a.urgency_status == "normal"


@pytest.mark.django_db
def test_regulatorycompliance_commitment_str(regulatory_commitment_a):
    expected = f"{regulatory_commitment_a.number} — {regulatory_commitment_a.title}"
    assert str(regulatory_commitment_a) == expected


@pytest.mark.django_db
def test_regulatorycompliance_commitment_properties(regulatory_commitment_a):
    assert regulatory_commitment_a.is_overdue is False
    assert regulatory_commitment_a.days_remaining == 180
    assert regulatory_commitment_a.status_css == "badge-amber"

    today = timezone.now().date()
    regulatory_commitment_a.due_date = today - timedelta(days=10)
    assert regulatory_commitment_a.is_overdue is True
    assert regulatory_commitment_a.status_css == "badge-red"

    regulatory_commitment_a.status = "agency_accepted"
    assert regulatory_commitment_a.status_css == "badge-green"


@pytest.mark.django_db
def test_regulatorycompliance_pms_report_str(post_market_surveillance_report_a):
    expected = f"{post_market_surveillance_report_a.number} — {post_market_surveillance_report_a.report_title}"
    assert str(post_market_surveillance_report_a) == expected


@pytest.mark.django_db
def test_regulatorycompliance_pms_report_properties(post_market_surveillance_report_a):
    assert post_market_surveillance_report_a.complaint_rate_pct == round((18 / 1450) * 100, 4)
    assert post_market_surveillance_report_a.serious_incident_rate_pct == 0.0
    assert post_market_surveillance_report_a.status_css == "badge-green"
    assert post_market_surveillance_report_a.benefit_risk_css == "badge-green"

    post_market_surveillance_report_a.units_distributed = 0
    assert post_market_surveillance_report_a.complaint_rate_pct == 0.0
    assert post_market_surveillance_report_a.serious_incident_rate_pct == 0.0


@pytest.mark.django_db
def test_regulatorycompliance_unique_number_per_tenant(tenant_a, regulatory_submission_a):
    with pytest.raises(IntegrityError):
        RegulatorySubmission.objects.create(
            tenant=tenant_a,
            number=regulatory_submission_a.number,
            title="Duplicate submission",
            product_name="Device Duplicate",
        )
