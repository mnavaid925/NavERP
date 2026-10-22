"""Tests for Sales 8.15 Contract & Subscription Management models."""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.sales.models import (
    CustomerContract,
    CustomerSubscription,
    UsageMeterRecord,
    ContractObligation,
)


@pytest.mark.django_db
def test_contractsubscription_contract_creation_and_str(cs_contract_a):
    assert cs_contract_a.number.startswith("CCT-")
    assert str(cs_contract_a) == f"{cs_contract_a.number} - {cs_contract_a.title}"
    assert cs_contract_a.status == "active"
    assert cs_contract_a.total_contract_value == Decimal("120000.00")


@pytest.mark.django_db
def test_contractsubscription_contract_date_validation(tenant_a, cs_account_a, cs_currency):
    today = timezone.localdate()
    contract = CustomerContract(
        tenant=tenant_a,
        account=cs_account_a,
        title="Invalid Dates Contract",
        currency=cs_currency,
        start_date=today,
        end_date=today - timezone.timedelta(days=10),
    )
    with pytest.raises(ValidationError) as exc_info:
        contract.full_clean()
    assert "end_date" in exc_info.value.message_dict


@pytest.mark.django_db
def test_contractsubscription_contract_foreign_tenant_clean(tenant_a, cs_account_b, cs_currency):
    today = timezone.localdate()
    contract = CustomerContract(
        tenant=tenant_a,
        account=cs_account_b,  # Account belongs to tenant_b
        title="Foreign Tenant Account",
        currency=cs_currency,
        start_date=today,
        end_date=today + timezone.timedelta(days=30),
    )
    with pytest.raises(ValidationError) as exc_info:
        contract.full_clean()
    assert "account" in exc_info.value.message_dict


@pytest.mark.django_db
def test_contractsubscription_subscription_creation_and_mrr(cs_subscription_a):
    assert cs_subscription_a.number.startswith("CSB-")
    assert cs_subscription_a.account.name in str(cs_subscription_a)
    assert cs_subscription_a.calculate_mrr() == Decimal("5000.00")

    # Quarterly cadence (unit_price 30 * qty 10 = 300 / 3 = 100 MRR)
    cs_subscription_a.billing_cadence = "quarterly"
    cs_subscription_a.quantity = 10
    cs_subscription_a.unit_price = Decimal("30.00")
    assert cs_subscription_a.calculate_mrr() == Decimal("100.00")

    # Annual cadence (unit_price 120 * qty 10 = 1200 / 12 = 100 MRR)
    cs_subscription_a.billing_cadence = "annual"
    cs_subscription_a.unit_price = Decimal("120.00")
    assert cs_subscription_a.calculate_mrr() == Decimal("100.00")

    # Semi-annual cadence (unit_price 60 * qty 10 = 600 / 6 = 100 MRR)
    cs_subscription_a.billing_cadence = "semi_annual"
    cs_subscription_a.unit_price = Decimal("60.00")
    assert cs_subscription_a.calculate_mrr() == Decimal("100.00")


@pytest.mark.django_db
def test_contractsubscription_subscription_foreign_contract_clean(tenant_a, cs_contract_b, cs_account_a, cs_currency):
    sub = CustomerSubscription(
        tenant=tenant_a,
        contract=cs_contract_b,  # Contract from tenant_b
        account=cs_account_a,
        subscription_name="Tenant Mismatch Sub",
        currency=cs_currency,
    )
    with pytest.raises(ValidationError) as exc_info:
        sub.full_clean()
    assert "contract" in exc_info.value.message_dict


@pytest.mark.django_db
def test_contractsubscription_meter_record_charges_calculation(tenant_a, cs_subscription_a):
    today = timezone.localdate()
    # Case 1: usage within allowance -> 0 overage
    meter1 = UsageMeterRecord.objects.create(
        tenant=tenant_a,
        subscription=cs_subscription_a,
        meter_name="Compute Hours",
        billing_period_start=today - timezone.timedelta(days=30),
        billing_period_end=today,
        included_allowance=Decimal("500.00"),
        reported_usage=Decimal("450.00"),
        overage_unit_price=Decimal("0.1000"),
    )
    meter1.calculate_charges()
    assert meter1.billable_overage_units == Decimal("0.00")
    assert meter1.overage_total_charge == Decimal("0.00")

    # Case 2: usage exceeds allowance -> billable overage calculated
    meter2 = UsageMeterRecord.objects.create(
        tenant=tenant_a,
        subscription=cs_subscription_a,
        meter_name="Compute Hours",
        billing_period_start=today - timezone.timedelta(days=30),
        billing_period_end=today,
        included_allowance=Decimal("500.00"),
        reported_usage=Decimal("600.00"),
        overage_unit_price=Decimal("0.1000"),
    )
    meter2.calculate_charges()
    assert meter2.billable_overage_units == Decimal("100.00")
    assert meter2.overage_total_charge == Decimal("10.00")


@pytest.mark.django_db
def test_contractsubscription_obligation_cross_contract_constraint(tenant_a, cs_contract_a, cs_subscription_b, cs_account_a):
    from apps.sales.tests.conftest import _contractsubscription_subscription
    # Create subscription belonging to a different contract in same tenant
    contract_other = CustomerContract.objects.create(
        tenant=tenant_a,
        account=cs_account_a,
        title="Other Agreement",
        currency=cs_contract_a.currency,
        start_date=timezone.localdate(),
        end_date=timezone.localdate() + timezone.timedelta(days=180),
    )
    sub_other = _contractsubscription_subscription(
        tenant=tenant_a,
        contract=contract_other,
        account=cs_account_a,
        subscription_name="Other Sub",
        currency=cs_contract_a.currency,
    )
    
    # Obligation pointing to cs_contract_a but linking sub_other -> must raise ValidationError
    obligation = ContractObligation(
        tenant=tenant_a,
        contract=cs_contract_a,
        subscription=sub_other,
        title="Inconsistent SLA",
        target_metric=">= 99.9%",
    )
    with pytest.raises(ValidationError) as exc_info:
        obligation.full_clean()
    assert "subscription" in exc_info.value.message_dict
