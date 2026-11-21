import pytest
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone

from apps.quality.models import (
    RegulatorySubmission,
    ProductRegistration,
    RegulatoryCommitment,
    PostMarketSurveillanceReport,
)


@pytest.mark.django_db
def test_regulatorycompliance_dashboard_view(client, admin_user, regulatory_submission_a, product_registration_a, regulatory_commitment_a, post_market_surveillance_report_a):
    client.force_login(admin_user)
    res = client.get(reverse("quality:regulatory_dashboard"))
    assert res.status_code == 200
    assert "active_registrations" in res.context
    assert res.context["active_registrations"] >= 1
    assert res.context["open_commitments"] >= 1


@pytest.mark.django_db
def test_regulatorycompliance_submission_views(client, admin_user, tenant_a, regulatory_submission_a):
    client.force_login(admin_user)

    # 1. List view & filters
    url = reverse("quality:regulatory_submission_list")
    res = client.get(url)
    assert res.status_code == 200
    assert regulatory_submission_a.number in res.content.decode()

    # Search filter
    res = client.get(url, {"q": regulatory_submission_a.product_code, "status": "approved_cleared"})
    assert res.status_code == 200
    assert regulatory_submission_a.title in res.content.decode()

    # 2. Detail view
    res = client.get(reverse("quality:regulatory_submission_detail", kwargs={"pk": regulatory_submission_a.pk}))
    assert res.status_code == 200
    assert regulatory_submission_a.number in res.content.decode()

    # 3. Create view
    res = client.get(reverse("quality:regulatory_submission_create"))
    assert res.status_code == 200

    create_data = {
        "title": "New 510(k) Premarket Dossier",
        "submission_type": "510k",
        "product_name": "Ventilator Flow Sensor",
        "product_code": "CBK-FS",
        "device_class": "class_iib",
        "status": "draft",
    }
    res = client.post(reverse("quality:regulatory_submission_create"), data=create_data)
    assert res.status_code == 302
    created = RegulatorySubmission.objects.filter(tenant=tenant_a, title="New 510(k) Premarket Dossier").first()
    assert created is not None

    # 4. Edit view
    res = client.get(reverse("quality:regulatory_submission_edit", kwargs={"pk": created.pk}))
    assert res.status_code == 200

    edit_data = {
        "title": "New 510(k) Premarket Dossier Updated",
        "submission_type": "510k",
        "product_name": "Ventilator Flow Sensor Pro",
        "device_class": "class_iib",
        "status": "authoring",
    }
    res = client.post(reverse("quality:regulatory_submission_edit", kwargs={"pk": created.pk}), data=edit_data)
    assert res.status_code == 302
    created.refresh_from_db()
    assert created.title == "New 510(k) Premarket Dossier Updated"

    # 5. Export view
    res = client.get(reverse("quality:regulatory_submission_export"))
    assert res.status_code == 200
    assert "text/csv" in res.headers["Content-Type"]

    # 6. Delete view
    res = client.post(reverse("quality:regulatory_submission_delete", kwargs={"pk": created.pk}))
    assert res.status_code == 302
    assert not RegulatorySubmission.objects.filter(pk=created.pk).exists()


@pytest.mark.django_db
def test_regulatorycompliance_registration_views(client, admin_user, tenant_a, product_registration_a):
    client.force_login(admin_user)

    url = reverse("quality:product_registration_list")
    res = client.get(url)
    assert res.status_code == 200
    assert product_registration_a.product_name in res.content.decode()

    # Detail view
    res = client.get(reverse("quality:product_registration_detail", kwargs={"pk": product_registration_a.pk}))
    assert res.status_code == 200

    # Create view
    res = client.get(reverse("quality:product_registration_create"))
    assert res.status_code == 200

    create_data = {
        "registration_title": "EU MDR Class IIb Certificate",
        "registration_type": "ce_certificate",
        "jurisdiction_country": "European Union",
        "product_name": "Dialyzer Membrane",
        "product_code": "MDR-01",
        "status": "active",
        "renewal_lead_days": 90,
    }
    res = client.post(reverse("quality:product_registration_create"), data=create_data)
    assert res.status_code == 302
    created = ProductRegistration.objects.filter(tenant=tenant_a, registration_title="EU MDR Class IIb Certificate").first()
    assert created is not None

    # Edit view
    res = client.get(reverse("quality:product_registration_edit", kwargs={"pk": created.pk}))
    assert res.status_code == 200

    # Export view
    res = client.get(reverse("quality:product_registration_export"))
    assert res.status_code == 200
    assert "text/csv" in res.headers["Content-Type"]

    # Delete view
    res = client.post(reverse("quality:product_registration_delete", kwargs={"pk": created.pk}))
    assert res.status_code == 302
    assert not ProductRegistration.objects.filter(pk=created.pk).exists()


@pytest.mark.django_db
def test_regulatorycompliance_commitment_views(client, admin_user, tenant_a, regulatory_commitment_a, regulatory_submission_a, product_registration_a, inspection_host_a):
    client.force_login(admin_user)

    url = reverse("quality:regulatory_commitment_list")
    res = client.get(url)
    assert res.status_code == 200
    assert regulatory_commitment_a.title in res.content.decode()

    # Detail view
    res = client.get(reverse("quality:regulatory_commitment_detail", kwargs={"pk": regulatory_commitment_a.pk}))
    assert res.status_code == 200

    # Create with contextual pre-fill
    res = client.get(reverse("quality:regulatory_commitment_create"), {
        "submission": regulatory_submission_a.pk,
        "registration": product_registration_a.pk,
        "inspection": inspection_host_a.pk,
    })
    assert res.status_code == 200

    today = timezone.now().date()
    create_data = {
        "title": "483 Observation #1 Response",
        "commitment_type": "inspection_483_response",
        "commitment_description": "Update calibration procedure for environmental sensors.",
        "due_date": today + timedelta(days=15),
        "status": "open",
    }
    res = client.post(reverse("quality:regulatory_commitment_create"), data=create_data)
    assert res.status_code == 302
    created = RegulatoryCommitment.objects.filter(tenant=tenant_a, title="483 Observation #1 Response").first()
    assert created is not None

    # Export view
    res = client.get(reverse("quality:regulatory_commitment_export"))
    assert res.status_code == 200

    # Delete view
    res = client.post(reverse("quality:regulatory_commitment_delete", kwargs={"pk": created.pk}))
    assert res.status_code == 302
    assert not RegulatoryCommitment.objects.filter(pk=created.pk).exists()


@pytest.mark.django_db
def test_regulatorycompliance_pms_report_views(client, admin_user, tenant_a, post_market_surveillance_report_a, product_registration_a):
    client.force_login(admin_user)

    url = reverse("quality:post_market_surveillance_report_list")
    res = client.get(url)
    assert res.status_code == 200
    assert post_market_surveillance_report_a.report_title in res.content.decode()

    # Detail view
    res = client.get(reverse("quality:post_market_surveillance_report_detail", kwargs={"pk": post_market_surveillance_report_a.pk}))
    assert res.status_code == 200

    # Create with pre-fill
    res = client.get(reverse("quality:post_market_surveillance_report_create"), {"registration": product_registration_a.pk})
    assert res.status_code == 200

    today = timezone.now().date()
    create_data = {
        "report_title": "ApexVent Trend Review Q1",
        "report_type": "vigilance_trend",
        "device_model_family": "ApexVent Family",
        "reporting_period_start": today - timedelta(days=90),
        "reporting_period_end": today - timedelta(days=1),
        "units_distributed": 300,
        "total_complaints_count": 2,
        "serious_incidents_count": 0,
        "field_actions_count": 0,
        "benefit_risk_conclusion": "favorable",
        "status": "draft",
    }
    res = client.post(reverse("quality:post_market_surveillance_report_create"), data=create_data)
    assert res.status_code == 302
    created = PostMarketSurveillanceReport.objects.filter(tenant=tenant_a, report_title="ApexVent Trend Review Q1").first()
    assert created is not None

    # Export view
    res = client.get(reverse("quality:post_market_surveillance_report_export"))
    assert res.status_code == 200

    # Delete view
    res = client.post(reverse("quality:post_market_surveillance_report_delete", kwargs={"pk": created.pk}))
    assert res.status_code == 302
    assert not PostMarketSurveillanceReport.objects.filter(pk=created.pk).exists()
