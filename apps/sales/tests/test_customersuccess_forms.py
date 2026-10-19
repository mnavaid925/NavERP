"""Sub-module 8.11 Customer Success & Account Management -- Form Tests.

Covers:
1. Field presence and contract verification:
   - Exclusions: tenant, number must never be exposed (mass-assignment prevention).
   - Exclusions: time_to_value_days must not be exposed (derived on CustomerOnboarding).
2. Tenant-scoped querysets:
   - Form __init__(tenant=tenant) scopes FK dropdowns strictly to the user's tenant.
   - Tenant B records never appear in Tenant A form dropdowns.
3. Cross-tenant injection rejection (_reject_foreign):
   - Submitting foreign PKs fails form validation with field-level errors.
4. Validation rules and bounds in forms.
5. Successful instance creation and save.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounting.models import Currency
from apps.accounts.models import User
from apps.core.models import Party, PartyRole, Tenant
from apps.crm.models import Opportunity
from apps.sales.forms.CustomerSuccess.CustomerBusinessReviews import CustomerBusinessReviewForm
from apps.sales.forms.CustomerSuccess.CustomerHealthScores import CustomerHealthScoreForm
from apps.sales.forms.CustomerSuccess.CustomerOnboardings import CustomerOnboardingForm
from apps.sales.forms.CustomerSuccess.CustomerRenewals import CustomerRenewalForm
from apps.sales.models import (
    AccountPlan,
    CustomerBusinessReview,
    CustomerHealthScore,
    CustomerOnboarding,
    CustomerRenewal,
)
from apps.sales.tests.conftest import (
    _customersuccess_party,
    _customersuccess_renewal,
)
from apps.scm.models import SalesOrder

pytestmark = pytest.mark.django_db


# ============================================================================
# Helpers
# ============================================================================

def _customersuccess_customer_party(tenant, name="Customer Corp"):
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.create(tenant=tenant, party=party, role="customer")
    return party


def _customersuccess_sales_order(tenant, customer, total=Decimal("50000.00")):
    return SalesOrder.objects.create(
        tenant=tenant,
        customer=customer,
        source_channel="direct",
        status="confirmed",
        subtotal=total,
        tax_total=Decimal("0.00"),
        total=total,
    )


def _customersuccess_account_plan(tenant, account, owner):
    return AccountPlan.objects.create(
        tenant=tenant,
        account=account,
        title=f"{account.name} Strategic Plan",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        status="active",
        owner=owner,
    )


# ============================================================================
# 1. Field Exclusions & Security Contract
# ============================================================================

def test_customersuccess_form_field_exclusions():
    """Verify tenant and number are excluded from all Customer Success ModelForms."""
    forms_to_check = [
        CustomerHealthScoreForm,
        CustomerRenewalForm,
        CustomerOnboardingForm,
        CustomerBusinessReviewForm,
    ]

    for form_cls in forms_to_check:
        form = form_cls()
        fields = form.fields.keys()
        assert "tenant" not in fields, f"{form_cls.__name__} must not expose tenant field"
        assert "number" not in fields, f"{form_cls.__name__} must not expose number field"

    # Specific derived field exclusion
    onb_form = CustomerOnboardingForm()
    assert "time_to_value_days" not in onb_form.fields, "CustomerOnboardingForm must not expose time_to_value_days"


# ============================================================================
# 2. Tenant-Scoped Querysets
# ============================================================================

def test_customersuccess_health_score_form_tenant_scoping(tenant_a, tenant_b):
    """CustomerHealthScoreForm scopes customer accounts strictly to current tenant."""
    cust_a = _customersuccess_customer_party(tenant_a, name="Acme Customer")
    cust_b = _customersuccess_customer_party(tenant_b, name="Globex Customer")

    form_a = CustomerHealthScoreForm(tenant=tenant_a)
    account_qs_a = form_a.fields["account"].queryset
    assert cust_a in account_qs_a
    assert cust_b not in account_qs_a


def test_customersuccess_renewal_form_tenant_scoping(
    tenant_a, tenant_b, admin_user, admin_b, icm_currency
):
    """CustomerRenewalForm scopes account, owner, original_order, and expansion_opportunity."""
    cust_a = _customersuccess_customer_party(tenant_a, name="Acme Customer")
    cust_b = _customersuccess_customer_party(tenant_b, name="Globex Customer")
    order_a = _customersuccess_sales_order(tenant_a, cust_a)
    order_b = _customersuccess_sales_order(tenant_b, cust_b)
    opp_a = Opportunity.objects.create(tenant=tenant_a, name="Acme Expansion", amount=Decimal("10000.00"))
    opp_b = Opportunity.objects.create(tenant=tenant_b, name="Globex Expansion", amount=Decimal("15000.00"))

    form_a = CustomerRenewalForm(tenant=tenant_a)
    assert cust_a in form_a.fields["account"].queryset
    assert cust_b not in form_a.fields["account"].queryset
    assert admin_user in form_a.fields["owner"].queryset
    assert admin_b not in form_a.fields["owner"].queryset
    assert order_a in form_a.fields["original_order"].queryset
    assert order_b not in form_a.fields["original_order"].queryset
    assert opp_a in form_a.fields["expansion_opportunity"].queryset
    assert opp_b not in form_a.fields["expansion_opportunity"].queryset


def test_customersuccess_onboarding_form_tenant_scoping(
    tenant_a, tenant_b, admin_user, admin_b
):
    """CustomerOnboardingForm scopes account, lead_csm, and sales_order."""
    cust_a = _customersuccess_customer_party(tenant_a, name="Acme Customer")
    cust_b = _customersuccess_customer_party(tenant_b, name="Globex Customer")
    order_a = _customersuccess_sales_order(tenant_a, cust_a)
    order_b = _customersuccess_sales_order(tenant_b, cust_b)

    form_a = CustomerOnboardingForm(tenant=tenant_a)
    assert cust_a in form_a.fields["account"].queryset
    assert cust_b not in form_a.fields["account"].queryset
    assert admin_user in form_a.fields["lead_csm"].queryset
    assert admin_b not in form_a.fields["lead_csm"].queryset
    assert order_a in form_a.fields["sales_order"].queryset
    assert order_b not in form_a.fields["sales_order"].queryset


def test_customersuccess_business_review_form_tenant_scoping(
    tenant_a, tenant_b, admin_user, admin_b
):
    """CustomerBusinessReviewForm scopes account, lead_csm, and account_plan."""
    cust_a = _customersuccess_customer_party(tenant_a, name="Acme Customer")
    cust_b = _customersuccess_customer_party(tenant_b, name="Globex Customer")
    plan_a = _customersuccess_account_plan(tenant_a, cust_a, admin_user)
    plan_b = _customersuccess_account_plan(tenant_b, cust_b, admin_b)

    form_a = CustomerBusinessReviewForm(tenant=tenant_a)
    assert cust_a in form_a.fields["account"].queryset
    assert cust_b not in form_a.fields["account"].queryset
    assert admin_user in form_a.fields["lead_csm"].queryset
    assert admin_b not in form_a.fields["lead_csm"].queryset
    assert plan_a in form_a.fields["account_plan"].queryset
    assert plan_b not in form_a.fields["account_plan"].queryset


# ============================================================================
# 3. Cross-Tenant Rejection (_reject_foreign)
# ============================================================================

def test_customersuccess_health_score_form_reject_foreign_account(tenant_a, tenant_b):
    """Submitting foreign tenant customer account triggers _reject_foreign error."""
    cust_b = _customersuccess_customer_party(tenant_b, name="Globex Customer")
    form_data = {
        "account": cust_b.pk,
        "evaluation_date": "2026-03-01",
        "overall_score": 80,
        "health_band": "green",
        "score_trend": "stable",
        "risk_level": "low",
        "product_usage_score": 80,
        "support_ticket_score": 80,
        "nps_sentiment_score": 80,
        "relationship_score": 80,
        "renewal_risk_score": 80,
        "license_utilization_pct": "80.00",
        "open_support_tickets": 0,
    }
    form = CustomerHealthScoreForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "account" in form.errors


def test_customersuccess_renewal_form_reject_foreign_fks(
    tenant_a, tenant_b, admin_user, admin_b, icm_currency
):
    """Submitting foreign FKs triggers _reject_foreign error on renewal form."""
    cust_a = _customersuccess_customer_party(tenant_a, name="Acme Customer")
    cust_b = _customersuccess_customer_party(tenant_b, name="Globex Customer")
    order_b = _customersuccess_sales_order(tenant_b, cust_b)

    form_data = {
        "account": cust_a.pk,
        "owner": admin_b.pk,  # foreign user
        "original_order": order_b.pk,  # foreign order
        "renewal_name": "Renewal Attempt",
        "current_arr": "100000.00",
        "projected_renewal_arr": "100000.00",
        "expansion_amount": "0.00",
        "currency": icm_currency.pk,
        "renewal_date": "2026-06-01",
        "target_close_date": "2026-05-15",
        "stage": "upcoming",
        "churn_risk_flag": "low",
        "renewal_probability_pct": 80,
    }
    form = CustomerRenewalForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "owner" in form.errors or "original_order" in form.errors


def test_customersuccess_onboarding_form_reject_foreign_csm(
    tenant_a, tenant_b, admin_b
):
    """Submitting foreign lead CSM fails validation."""
    cust_a = _customersuccess_customer_party(tenant_a, name="Acme Customer")
    form_data = {
        "account": cust_a.pk,
        "lead_csm": admin_b.pk,  # foreign user
        "title": "Onboarding Test",
        "playbook_template": "enterprise_high_touch",
        "stage": "kickoff",
        "status": "in_progress",
        "kickoff_date": "2026-01-01",
        "target_go_live_date": "2026-03-31",
        "progress_pct": 10,
    }
    form = CustomerOnboardingForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "lead_csm" in form.errors


def test_customersuccess_business_review_form_reject_foreign_plan(
    tenant_a, tenant_b, admin_user, admin_b
):
    """Submitting foreign account plan fails validation."""
    cust_a = _customersuccess_customer_party(tenant_a, name="Acme Customer")
    cust_b = _customersuccess_customer_party(tenant_b, name="Globex Customer")
    plan_b = _customersuccess_account_plan(tenant_b, cust_b, admin_b)

    form_data = {
        "account": cust_a.pk,
        "lead_csm": admin_user.pk,
        "account_plan": plan_b.pk,  # foreign plan
        "title": "Q1 Review",
        "review_period": "q1",
        "review_year": 2026,
        "scheduled_date": "2026-03-15",
        "status": "scheduled",
        "template_type": "executive_value",
        "case_study_status": "none",
    }
    form = CustomerBusinessReviewForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "account_plan" in form.errors


# ============================================================================
# 4. Valid Form Submission & Save
# ============================================================================

def test_customersuccess_health_score_form_valid_save(tenant_a):
    """CustomerHealthScoreForm saves instance with tenant isolation."""
    cust = _customersuccess_customer_party(tenant_a, name="Valid Customer")
    form_data = {
        "account": cust.pk,
        "evaluation_date": "2026-03-01",
        "overall_score": 88,
        "health_band": "green",
        "previous_score": 82,
        "score_trend": "improving",
        "risk_level": "low",
        "product_usage_score": 90,
        "support_ticket_score": 85,
        "nps_sentiment_score": 88,
        "relationship_score": 90,
        "renewal_risk_score": 87,
        "license_utilization_pct": "85.50",
        "open_support_tickets": 1,
        "latest_nps": 60,
        "notes": "Top tier health status",
    }
    form = CustomerHealthScoreForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.overall_score == 88
    assert instance.number.startswith("CHS-")


def test_customersuccess_renewal_form_valid_save(tenant_a, admin_user, icm_currency):
    """CustomerRenewalForm saves instance with tenant isolation."""
    cust = _customersuccess_customer_party(tenant_a, name="Renewal Customer")
    form_data = {
        "account": cust.pk,
        "owner": admin_user.pk,
        "renewal_name": "Acme SaaS 2026 Renewal",
        "contract_reference": "CNT-2026-001",
        "current_arr": "150000.00",
        "projected_renewal_arr": "175000.00",
        "expansion_amount": "25000.00",
        "currency": icm_currency.pk,
        "renewal_date": "2026-06-30",
        "target_close_date": "2026-05-31",
        "stage": "engagement",
        "churn_risk_flag": "low",
        "renewal_probability_pct": 85,
        "auto_renewal": True,
        "notice_period_days": 90,
        "notes": "High probability expansion",
    }
    form = CustomerRenewalForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.number.startswith("CRN-")
    assert instance.current_arr == Decimal("150000.00")


def test_customersuccess_onboarding_form_valid_save(tenant_a, admin_user):
    """CustomerOnboardingForm saves instance with tenant isolation."""
    cust = _customersuccess_customer_party(tenant_a, name="Onboarding Customer")
    form_data = {
        "account": cust.pk,
        "lead_csm": admin_user.pk,
        "title": "Acme Cloud Rollout",
        "playbook_template": "enterprise_high_touch",
        "stage": "configuration",
        "status": "in_progress",
        "kickoff_date": "2026-01-15",
        "target_go_live_date": "2026-04-15",
        "progress_pct": 35,
        "executive_sponsor_name": "Jane Doe",
        "executive_sponsor_email": "jane@acme.example.com",
        "success_criteria": "Seamless migration of 500 seats",
    }
    form = CustomerOnboardingForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.number.startswith("COB-")
    assert instance.progress_pct == 35


def test_customersuccess_business_review_form_valid_save(tenant_a, admin_user):
    """CustomerBusinessReviewForm saves instance with tenant isolation."""
    cust = _customersuccess_customer_party(tenant_a, name="Review Customer")
    form_data = {
        "account": cust.pk,
        "lead_csm": admin_user.pk,
        "title": "Acme Q2 Strategic Review",
        "review_period": "q2",
        "review_year": 2026,
        "scheduled_date": "2026-06-15",
        "status": "scheduled",
        "template_type": "executive_value",
        "health_score_at_review": 88,
        "case_study_status": "identified",
        "is_referenceable": True,
        "key_achievements": "20% increase in productivity",
    }
    form = CustomerBusinessReviewForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.number.startswith("QBR-")
    assert instance.is_referenceable is True
