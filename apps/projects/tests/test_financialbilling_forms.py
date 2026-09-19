"""Projects 7.15 Financial & Billing Management — FORM tests.
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.projects.forms import (
    BillingRunDispatchForm,
    ContactLogForm,
    PaymentPromiseForm,
    ProjectBillingRunForm,
    ProjectPaymentRecordForm,
    ProjectRateCardForm,
    ProjectRevenueScheduleForm,
    RevenueScheduleRecognizeForm,
)
from apps.projects.tests.conftest import (
    _financialbilling_billing_run,
    _financialbilling_rate_card,
    _financialbilling_today,
)


# ==============================================================================================
# Excluded System & View-Owned Fields
# ==============================================================================================

@pytest.mark.django_db
def test_financialbilling_forms_exclude_system_and_view_owned_fields():
    rc_fields = ProjectRateCardForm.Meta.fields
    assert "tenant" not in rc_fields
    assert "number" not in rc_fields

    br_fields = ProjectBillingRunForm.Meta.fields
    assert "tenant" not in br_fields
    assert "number" not in br_fields
    assert "status" not in br_fields
    assert "subtotal" not in br_fields
    assert "tax_amount" not in br_fields
    assert "total_amount" not in br_fields

    prs_fields = ProjectRevenueScheduleForm.Meta.fields
    assert "tenant" not in prs_fields
    assert "number" not in prs_fields
    assert "status" not in prs_fields

    ppr_fields = ProjectPaymentRecordForm.Meta.fields
    assert "tenant" not in ppr_fields
    assert "number" not in ppr_fields
    assert "status" not in ppr_fields
    assert "stage" not in ppr_fields


# ==============================================================================================
# Valid Form Submissions
# ==============================================================================================

@pytest.mark.django_db
def test_financialbilling_rate_card_form_valid(
    tenant_a,
    financialbilling_project_a,
    financialbilling_party_a,
    projectinitiation_currency,
):
    form = ProjectRateCardForm(
        data={
            "name": "Principal Architect 2026",
            "project": financialbilling_project_a.pk,
            "client": financialbilling_party_a.pk,
            "role_name": "Principal Architect",
            "activity_code": "architecture",
            "hourly_rate": "225.00",
            "expense_markup_pct": "15.00",
            "currency": projectinitiation_currency.pk,
            "effective_from": _financialbilling_today().isoformat(),
            "effective_to": (_financialbilling_today() + timezone.timedelta(days=180)).isoformat(),
            "is_active": True,
            "notes": "Premium rate card",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_financialbilling_billing_run_form_valid(
    tenant_a,
    financialbilling_project_a,
    financialbilling_party_a,
    projectinitiation_currency,
):
    form = ProjectBillingRunForm(
        data={
            "project": financialbilling_project_a.pk,
            "client": financialbilling_party_a.pk,
            "billing_type": "time_and_materials",
            "run_date": _financialbilling_today().isoformat(),
            "cutoff_date": _financialbilling_today().isoformat(),
            "labor_amount": "8000.00",
            "expense_amount": "1200.00",
            "fee_amount": "300.00",
            "exchange_rate": "1.00000000",
            "currency": projectinitiation_currency.pk,
            "delivery_channel": "email",
            "recipient_email": "billing@client.com",
            "notes": "Monthly billing",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors


# ==============================================================================================
# Cross-Tenant Rejections
# ==============================================================================================

@pytest.mark.django_db
def test_financialbilling_rate_card_form_rejects_foreign_tenant_project(
    tenant_a,
    financialbilling_project_b,
    financialbilling_party_a,
    projectinitiation_currency,
):
    form = ProjectRateCardForm(
        data={
            "name": "Invalid Rate",
            "project": financialbilling_project_b.pk,
            "client": financialbilling_party_a.pk,
            "role_name": "Engineer",
            "hourly_rate": "100.00",
            "currency": projectinitiation_currency.pk,
            "is_active": True,
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "project" in form.errors


# ==============================================================================================
# Cross-Record Integrity Validation
# ==============================================================================================

@pytest.mark.django_db
def test_financialbilling_billing_run_form_rejects_mismatched_project_and_sow(
    tenant_a,
    financialbilling_project_a,
    financialbilling_project_b,
    financialbilling_party_a,
    projectinitiation_currency,
):
    from apps.projects.models import StatementOfWork
    foreign_sow = StatementOfWork.objects.create(
        tenant=tenant_a,
        project=financialbilling_project_b,
        client=financialbilling_party_a,
        title="Foreign Project SOW",
        status="active",
        effective_date=_financialbilling_today(),
        currency=projectinitiation_currency,
    )
    form = ProjectBillingRunForm(
        data={
            "project": financialbilling_project_a.pk,
            "client": financialbilling_party_a.pk,
            "sow": foreign_sow.pk,
            "billing_type": "fixed_fee",
            "run_date": _financialbilling_today().isoformat(),
            "cutoff_date": _financialbilling_today().isoformat(),
            "labor_amount": "1000.00",
            "exchange_rate": "1.00000000",
            "currency": projectinitiation_currency.pk,
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "sow" in form.errors


# ==============================================================================================
# Secondary Action Forms
# ==============================================================================================

def test_financialbilling_billing_run_dispatch_form_validation():
    form = BillingRunDispatchForm(data={"recipient_email": "invalid-email"})
    assert not form.is_valid()
    assert "recipient_email" in form.errors

    valid_form = BillingRunDispatchForm(data={"recipient_email": "client@example.com", "notes": "Dispatched"})
    assert valid_form.is_valid()


def test_financialbilling_payment_promise_form_rejects_negative_amount():
    form = PaymentPromiseForm(data={"promised_payment_date": "2026-10-01", "promised_amount": "-50.00"})
    assert not form.is_valid()
    assert "promised_amount" in form.errors

    valid_form = PaymentPromiseForm(data={"promised_payment_date": "2026-10-01", "promised_amount": "500.00"})
    assert valid_form.is_valid()


def test_financialbilling_contact_log_form_requires_notes():
    form = ContactLogForm(data={"contact_date": "2026-10-01", "notes": ""})
    assert not form.is_valid()
    assert "notes" in form.errors
