"""Projects 7.15 Financial & Billing Management — MODEL tests.
"""
import datetime
from decimal import Decimal
import re

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.projects.models import (
    ProjectRateCard,
    ProjectBillingRun,
    ProjectRevenueSchedule,
    ProjectPaymentRecord,
)
from apps.projects.tests.conftest import (
    _financialbilling_rate_card,
    _financialbilling_billing_run,
    _financialbilling_revenue_schedule,
    _financialbilling_payment_record,
    _financialbilling_today,
)


# ==============================================================================================
# Numbering & Prefixes
# ==============================================================================================

@pytest.mark.django_db
def test_financialbilling_each_model_mints_its_own_prefix(
    tenant_a,
    financialbilling_project_a,
    financialbilling_party_a,
    projectinitiation_currency,
):
    rc = _financialbilling_rate_card(tenant_a, project=financialbilling_project_a, currency=projectinitiation_currency)
    br = _financialbilling_billing_run(tenant_a, financialbilling_project_a, financialbilling_party_a, currency=projectinitiation_currency)
    rs = _financialbilling_revenue_schedule(tenant_a, financialbilling_project_a)
    pr = _financialbilling_payment_record(tenant_a, financialbilling_project_a, financialbilling_party_a)

    assert re.fullmatch(r"RTC-\d{5}", rc.number)
    assert re.fullmatch(r"PBR-\d{5}", br.number)
    assert re.fullmatch(r"PRS-\d{5}", rs.number)
    assert re.fullmatch(r"PPR-\d{5}", pr.number)


@pytest.mark.django_db
def test_financialbilling_numbers_advance_per_tenant(
    tenant_a,
    financialbilling_project_a,
    projectinitiation_currency,
):
    rc1 = _financialbilling_rate_card(tenant_a, project=financialbilling_project_a, currency=projectinitiation_currency, name="Rate 1")
    rc2 = _financialbilling_rate_card(tenant_a, project=financialbilling_project_a, currency=projectinitiation_currency, name="Rate 2")

    n1 = int(rc1.number.split("-")[1])
    n2 = int(rc2.number.split("-")[1])
    assert n2 == n1 + 1


# ==============================================================================================
# RateCard Invariants & Computations
# ==============================================================================================

@pytest.mark.django_db
def test_financialbilling_rate_card_clean_date_validation(tenant_a, projectinitiation_currency):
    rc = _financialbilling_rate_card(
        tenant_a,
        hourly_rate=Decimal("150.00"),
        effective_from=_financialbilling_today(),
        effective_to=_financialbilling_today() - datetime.timedelta(days=1),
        currency=projectinitiation_currency,
    )
    with pytest.raises(ValidationError):
        rc.clean()


@pytest.mark.django_db
def test_financialbilling_rate_card_str(tenant_a, projectinitiation_currency):
    rc = _financialbilling_rate_card(
        tenant_a,
        name="Custom QA Rate",
        currency=projectinitiation_currency,
    )
    assert rc.number in str(rc)
    assert "Custom QA Rate" in rc.name


# ==============================================================================================
# BillingRun Invariants & Computations
# ==============================================================================================

@pytest.mark.django_db
def test_financialbilling_billing_run_totals_calculation(
    tenant_a,
    financialbilling_project_a,
    financialbilling_party_a,
    projectinitiation_currency,
):
    br = _financialbilling_billing_run(
        tenant_a,
        financialbilling_project_a,
        financialbilling_party_a,
        currency=projectinitiation_currency,
        labor_amount=Decimal("10000.00"),
        expense_amount=Decimal("1500.00"),
        fee_amount=Decimal("500.00"),
        tax_rate_pct=Decimal("10.00"),
    )
    assert br.subtotal == Decimal("12000.00")
    assert br.tax_amount == Decimal("1200.00")
    assert br.total_amount == Decimal("13200.00")
    assert br.number in str(br)


# ==============================================================================================
# RevenueSchedule Invariants & Computations
# ==============================================================================================

@pytest.mark.django_db
def test_financialbilling_revenue_schedule_percent_complete_math(
    tenant_a,
    financialbilling_project_a,
):
    rs = _financialbilling_revenue_schedule(
        tenant_a,
        financialbilling_project_a,
        method="percent_complete",
        contract_amount=Decimal("200000.00"),
        completion_percent=Decimal("45.00"),
    )
    assert rs.recognized_amount == Decimal("90000.00")
    assert rs.number in str(rs)


# ==============================================================================================
# PaymentRecord Invariants & Computations
# ==============================================================================================

@pytest.mark.django_db
def test_financialbilling_payment_record_str_and_defaults(
    tenant_a,
    financialbilling_project_a,
    financialbilling_party_a,
    projectinitiation_currency,
):
    pr = _financialbilling_payment_record(
        tenant_a,
        financialbilling_project_a,
        financialbilling_party_a,
    )
    assert pr.stage == "current"
    assert pr.dunning_level == "friendly_reminder"
    assert pr.status == "open"
    assert pr.number in str(pr)
    assert pr.accounting_invoice.total == Decimal("10000.00")


@pytest.mark.django_db
def test_financialbilling_payment_record_clean_rejects_negative_promise(
    tenant_a,
    financialbilling_project_a,
    financialbilling_party_a,
    projectinitiation_currency,
):
    pr = _financialbilling_payment_record(
        tenant_a,
        financialbilling_project_a,
        financialbilling_party_a,
    )
    pr.promised_amount = Decimal("-100.00")
    with pytest.raises(ValidationError):
        pr.full_clean()

