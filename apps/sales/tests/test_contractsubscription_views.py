"""Tests for Sales 8.15 Contract & Subscription Management views."""
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.sales.models import (
    CustomerContract,
    CustomerSubscription,
    UsageMeterRecord,
    ContractObligation,
    CPQQuote,
)


@pytest.mark.django_db
def test_contractsubscription_workspace_view(client_a, cs_contract_a, cs_subscription_a):
    today = timezone.localdate()
    cs_contract_a.end_date = today + timezone.timedelta(days=20)
    cs_contract_a.save()

    url = reverse("sales:contract_subscription_workspace")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "total_arr" in resp.context
    assert "total_tcv" in resp.context
    assert "urgent_contracts" in resp.context
    assert "urgent_subscriptions" in resp.context
    assert "sla_compliance_rate" in resp.context
    html = resp.content.decode("utf-8")
    assert "Contract & Subscription Workspace" in html
    assert cs_contract_a.number in html


@pytest.mark.django_db
def test_contractsubscription_renewal_dashboard_view(client_a, cs_contract_a):
    url = reverse("sales:renewal_automation_dashboard")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "upcoming_renewals" in resp.context
    assert "auto_renew_candidates" in resp.context
    assert "expiring_30_days" in resp.context
    html = resp.content.decode("utf-8")
    assert "Renewal Automation Dashboard" in html


@pytest.mark.django_db
def test_contractsubscription_contract_list_and_filter(client_a, cs_contract_a):
    url = reverse("sales:customer_contract_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert cs_contract_a in resp.context["contracts"]

    # Filter with query param
    resp_filtered = client_a.get(url, {"q": cs_contract_a.number})
    assert resp_filtered.status_code == 200
    assert cs_contract_a in resp_filtered.context["contracts"]


@pytest.mark.django_db
def test_contractsubscription_subscription_list_and_arr(client_a, cs_subscription_a):
    url = reverse("sales:customer_subscription_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert cs_subscription_a in resp.context["subscriptions"]
    assert "total_arr" in resp.context
    assert resp.context["total_arr"] == Decimal("60000.00")  # 5000 * 12


@pytest.mark.django_db
def test_contractsubscription_meter_record_list(client_a, cs_meter_record_a):
    url = reverse("sales:usage_meter_record_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert cs_meter_record_a in resp.context["usage_records"]


@pytest.mark.django_db
def test_contractsubscription_obligation_list(client_a, cs_obligation_a):
    url = reverse("sales:contract_obligation_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert cs_obligation_a in resp.context["obligations"]


@pytest.mark.django_db
def test_contractsubscription_generate_renewal_quote_action(client_a, tenant_a, cs_contract_a):
    url = reverse("sales:customer_contract_generate_renewal_quote", kwargs={"pk": cs_contract_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("sales:customer_contract_detail", kwargs={"pk": cs_contract_a.pk})

    # Verify CPQQuote was created with name and total without TypeError
    quote = CPQQuote.objects.filter(tenant=tenant_a, name__icontains=cs_contract_a.title).first()
    assert quote is not None
    assert quote.account == cs_contract_a.account
    expected_total = (cs_contract_a.annual_contract_value * Decimal("1.05")).quantize(Decimal("0.01"))
    assert quote.total == expected_total


@pytest.mark.django_db
def test_contractsubscription_execute_auto_renew_action(client_a, cs_contract_a):
    # Set contract end date to 15 days from now (within notice window)
    today = timezone.localdate()
    cs_contract_a.end_date = today + timezone.timedelta(days=15)
    cs_contract_a.save()

    url = reverse("sales:customer_contract_execute_auto_renew", kwargs={"pk": cs_contract_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302

    cs_contract_a.refresh_from_db()
    # Contract term should have advanced by ~360 days (12 months * 30 days)
    assert cs_contract_a.end_date > today + timezone.timedelta(days=300)
    # TCV should have compounded by 5%
    expected_tcv = (Decimal("120000.00") * Decimal("1.05")).quantize(Decimal("0.01"))
    assert cs_contract_a.total_contract_value == expected_tcv


@pytest.mark.django_db
def test_contractsubscription_pause_and_resume_lifecycle(client_a, cs_subscription_a):
    # 1. Pause active subscription
    pause_url = reverse("sales:customer_subscription_pause", kwargs={"pk": cs_subscription_a.pk})
    resp_pause = client_a.post(pause_url, {"notes": "Customer requested temporary pause"})
    assert resp_pause.status_code == 302
    cs_subscription_a.refresh_from_db()
    assert cs_subscription_a.status == "paused"

    # 2. Resume paused subscription
    resume_url = reverse("sales:customer_subscription_resume", kwargs={"pk": cs_subscription_a.pk})
    resp_resume = client_a.post(resume_url)
    assert resp_resume.status_code == 302
    cs_subscription_a.refresh_from_db()
    assert cs_subscription_a.status == "active"


@pytest.mark.django_db
def test_contractsubscription_meter_calculate_charges_action(client_a, cs_meter_record_a):
    cs_meter_record_a.status = "metering"
    cs_meter_record_a.billable_overage_units = Decimal("0.00")
    cs_meter_record_a.overage_total_charge = Decimal("0.00")
    cs_meter_record_a.save()

    url = reverse("sales:usage_meter_record_calculate", kwargs={"pk": cs_meter_record_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302

    cs_meter_record_a.refresh_from_db()
    assert cs_meter_record_a.status == "calculated"
    assert cs_meter_record_a.billable_overage_units == Decimal("50000.00")
    assert cs_meter_record_a.overage_total_charge == Decimal("100.00")


@pytest.mark.django_db
def test_contractsubscription_obligation_fulfill_action(client_a, cs_obligation_a):
    url = reverse("sales:contract_obligation_fulfill", kwargs={"pk": cs_obligation_a.pk})
    resp = client_a.post(url, {"fulfillment_evidence": "Audit report #8899 validated 99.95% uptime."})
    assert resp.status_code == 302

    cs_obligation_a.refresh_from_db()
    assert cs_obligation_a.status == "fulfilled"
    assert cs_obligation_a.fulfilled_at is not None
    assert "Audit report #8899" in cs_obligation_a.fulfillment_evidence
