"""Tests for Sales 8.15 Contract & Subscription Management forms."""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.sales.forms.ContractSubscriptionManagement.CustomerContracts import (
    CustomerContractFilterForm,
    CustomerContractForm,
)
from apps.sales.forms.ContractSubscriptionManagement.CustomerSubscriptions import (
    CustomerSubscriptionFilterForm,
    CustomerSubscriptionForm,
    SubscriptionCancelForm,
    SubscriptionPauseForm,
    SubscriptionUpgradeForm,
)
from apps.sales.forms.ContractSubscriptionManagement.UsageMeterRecords import (
    UsageMeterRecordFilterForm,
    UsageMeterRecordForm,
)
from apps.sales.forms.ContractSubscriptionManagement.ContractObligations import (
    ContractObligationFilterForm,
    ContractObligationForm,
    ObligationBreachForm,
    ObligationFulfillForm,
)


@pytest.mark.django_db
def test_contractsubscription_contract_form_valid(tenant_a, cs_account_a, cs_currency, admin_user):
    today = timezone.localdate()
    form = CustomerContractForm(
        data={
            "account": cs_account_a.pk,
            "title": "Software Licensing Agreement",
            "contract_type": "subscription_agreement",
            "status": "draft",
            "currency": cs_currency.pk,
            "total_contract_value": "60000.00",
            "annual_contract_value": "60000.00",
            "start_date": today.isoformat(),
            "end_date": (today + timezone.timedelta(days=365)).isoformat(),
            "auto_renew": True,
            "renewal_term_months": 12,
            "notice_period_days": 30,
            "price_uplift_pct": "3.50",
            "owner": admin_user.pk,
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    contract = form.save(commit=False)
    contract.tenant = tenant_a
    contract.save()
    assert contract.number.startswith("CCT-")
    assert contract.price_uplift_pct == Decimal("3.50")


@pytest.mark.django_db
def test_contractsubscription_contract_form_foreign_party_rejected(tenant_a, cs_account_b, cs_currency):
    today = timezone.localdate()
    form = CustomerContractForm(
        data={
            "account": cs_account_b.pk,  # From tenant_b
            "title": "Foreign Account Agreement",
            "currency": cs_currency.pk,
            "start_date": today.isoformat(),
            "end_date": (today + timezone.timedelta(days=365)).isoformat(),
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "account" in form.errors


@pytest.mark.django_db
def test_contractsubscription_subscription_form_defaults_and_scoping(tenant_a, cs_contract_a, cs_account_a, cs_currency):
    form = CustomerSubscriptionForm(tenant=tenant_a)
    assert form.fields["renewal_notice_days"].initial == 30
    assert not form.fields["renewal_notice_days"].required

    # Account and contract querysets must be tenant-scoped
    assert cs_contract_a in form.fields["contract"].queryset
    assert cs_account_a in form.fields["account"].queryset


@pytest.mark.django_db
def test_contractsubscription_upgrade_form_validation():
    # Valid quantity
    form = SubscriptionUpgradeForm(data={"quantity": 150, "unit_price": "45.00"})
    assert form.is_valid(), form.errors

    # Overly large quantity exceeding ceiling -> rejected
    form_oversized = SubscriptionUpgradeForm(data={"quantity": 2000000, "unit_price": "45.00"})
    assert not form_oversized.is_valid()
    assert "quantity" in form_oversized.errors

    # Non-positive quantity -> rejected
    form_zero = SubscriptionUpgradeForm(data={"quantity": 0, "unit_price": "45.00"})
    assert not form_zero.is_valid()
    assert "quantity" in form_zero.errors


@pytest.mark.django_db
def test_contractsubscription_meter_record_form_scoping(tenant_a, cs_subscription_a):
    form = UsageMeterRecordForm(tenant=tenant_a)
    assert cs_subscription_a in form.fields["subscription"].queryset


@pytest.mark.django_db
def test_contractsubscription_obligation_breach_form_positive_penalty():
    # Positive penalty -> valid
    form_valid = ObligationBreachForm(data={"penalty_amount": "500.00", "penalty_status": "assessed", "notes": "Missed uptime target"})
    assert form_valid.is_valid(), form_valid.errors

    # Zero penalty -> rejected
    form_zero = ObligationBreachForm(data={"penalty_amount": "0.00", "penalty_status": "assessed", "notes": "Zero penalty"})
    assert not form_zero.is_valid()
    assert "penalty_amount" in form_zero.errors


@pytest.mark.django_db
def test_contractsubscription_filter_forms(tenant_a):
    # CustomerContractFilterForm
    c_filter = CustomerContractFilterForm(data={"status": "active", "contract_type": "subscription_agreement"}, tenant=tenant_a)
    assert c_filter.is_valid(), c_filter.errors

    # CustomerSubscriptionFilterForm
    s_filter = CustomerSubscriptionFilterForm(data={"status": "active", "pricing_model": "per_seat"}, tenant=tenant_a)
    assert s_filter.is_valid(), s_filter.errors

    # UsageMeterRecordFilterForm
    u_filter = UsageMeterRecordFilterForm(data={"status": "calculated"})
    assert u_filter.is_valid(), u_filter.errors

    # ContractObligationFilterForm
    o_filter = ContractObligationFilterForm(data={"status": "pending"}, tenant=tenant_a)
    assert o_filter.is_valid(), o_filter.errors
