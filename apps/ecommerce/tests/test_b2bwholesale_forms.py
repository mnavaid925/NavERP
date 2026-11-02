"""Tests for eCommerce 9.17 B2B & Wholesale Commerce Forms."""
from decimal import Decimal
import pytest
from django import forms
from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.core.models.Party import Party
from apps.ecommerce.forms.B2bWholesale import (
    B2bCompanyAccountForm,
    B2bCompanyUserForm,
    B2bQuoteRequestForm,
    B2bQuickOrderTemplateForm,
)
from apps.ecommerce.tests.conftest import (
    _b2bwholesale_company_account,
    _b2bwholesale_company_user,
    _b2bwholesale_quote_request,
    _b2bwholesale_quick_order_template,
)


@pytest.mark.django_db
def test_b2bwholesale_company_account_form_valid(tenant_a, user_a):
    """Test valid company account form binding and saving."""
    party = Party.objects.create(tenant=tenant_a, name="Apex Industrial Corp", kind="organization")
    currency = Currency.objects.filter(code="USD").first() or Currency.objects.create(code="USD", name="US Dollar", symbol="$")
    data = {
        "company_name": "Apex Industrial Corp",
        "company_party": party.pk,
        "primary_contact": user_a.pk,
        "preferred_currency": currency.pk,
        "company_tax_id": "US-998877665",
        "credit_limit": "75000.00",
        "payment_terms": "net_30",
        "credit_status": "good_standing",
        "approval_threshold_amount": "5000.00",
        "wholesale_discount_percent": "12.50",
        "status": "active",
        "punchout_protocol": "cxml",
        "punchout_shared_secret": "SuperSecretPassword123!",
    }
    form = B2bCompanyAccountForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.company_name == "Apex Industrial Corp"
    assert instance.credit_limit == Decimal("75000.00")
    assert instance.punchout_shared_secret == "SuperSecretPassword123!"


@pytest.mark.django_db
def test_b2bwholesale_company_account_form_password_widget_and_retention(tenant_a, user_a):
    """Test PasswordInput widget and retention of existing secret on blank edit (C6)."""
    co = _b2bwholesale_company_account(
        tenant_a,
        primary_contact=user_a,
        punchout_shared_secret="ExistingSecretValue456!",
    )
    form = B2bCompanyAccountForm(instance=co, tenant=tenant_a)
    assert isinstance(form.fields["punchout_shared_secret"].widget, forms.PasswordInput)

    # Submit edit with empty password field
    data = {
        "company_name": co.company_name,
        "company_party": co.company_party_id,
        "preferred_currency": co.preferred_currency_id,
        "credit_limit": "60000.00",
        "payment_terms": "net_30",
        "credit_status": "good_standing",
        "approval_threshold_amount": "5000.00",
        "wholesale_discount_percent": "10.00",
        "status": "active",
        "punchout_protocol": "none",
        "punchout_shared_secret": "",  # Blank edit
    }
    edit_form = B2bCompanyAccountForm(data=data, instance=co, tenant=tenant_a)
    assert edit_form.is_valid(), edit_form.errors
    saved = edit_form.save()
    assert saved.punchout_shared_secret == "ExistingSecretValue456!"


@pytest.mark.django_db
def test_b2bwholesale_company_account_form_reject_foreign(tenant_a, tenant_b, user_a):
    """Test cross-tenant rejection of foreign FKs in company account form."""
    party_b = Party.objects.create(tenant=tenant_b, name="Foreign Party Corp", kind="organization")
    currency = Currency.objects.filter(code="USD").first() or Currency.objects.create(code="USD", name="US Dollar", symbol="$")
    data = {
        "company_name": "Foreign Account Corp",
        "company_party": party_b.pk,  # Belongs to tenant_b
        "primary_contact": user_a.pk,
        "preferred_currency": currency.pk,
        "credit_limit": "50000.00",
        "payment_terms": "net_30",
        "credit_status": "good_standing",
        "wholesale_discount_percent": "10.00",
        "status": "active",
        "punchout_protocol": "none",
    }
    form = B2bCompanyAccountForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "company_party" in form.errors


@pytest.mark.django_db
def test_b2bwholesale_company_user_form_valid(tenant_a, ecom_b2b_company_a, user_a):
    """Test valid company user form submission."""
    data = {
        "company": ecom_b2b_company_a.pk,
        "user": user_a.pk,
        "role": "buyer",
        "job_title": "Regional Purchasing Lead",
        "department": "Supply Chain",
        "order_spend_limit": "15000.00",
        "monthly_spend_limit": "50000.00",
        "can_place_orders": True,
        "can_request_quotes": True,
        "can_view_invoices": False,
        "can_manage_users": False,
        "can_approve_orders": False,
        "status": "active",
    }
    form = B2bCompanyUserForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    cu = form.save()
    assert cu.role == "buyer"
    assert cu.order_spend_limit == Decimal("15000.00")


@pytest.mark.django_db
def test_b2bwholesale_company_user_form_approver_cross_company(tenant_a, ecom_b2b_company_a, user_a):
    """Test designated approver must belong to same company (I3)."""
    co_other = _b2bwholesale_company_account(tenant_a, company_name="Other Wholesale Inc")
    approver_other = _b2bwholesale_company_user(
        tenant_a, co_other, user_a, role="company_admin", can_approve_orders=True
    )
    data = {
        "company": ecom_b2b_company_a.pk,
        "user": user_a.pk,
        "role": "buyer",
        "order_spend_limit": "5000.00",
        "monthly_spend_limit": "20000.00",
        "reports_to_approver": approver_other.pk,
        "status": "active",
    }
    form = B2bCompanyUserForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "reports_to_approver" in form.errors
    assert "same wholesale company" in form.errors["reports_to_approver"][0]


@pytest.mark.django_db
def test_b2bwholesale_company_user_form_reject_foreign(tenant_a, tenant_b, ecom_b2b_company_b, user_a):
    """Test cross-tenant rejection in company user form."""
    data = {
        "company": ecom_b2b_company_b.pk,  # Tenant B company
        "user": user_a.pk,
        "role": "buyer",
        "order_spend_limit": "5000.00",
        "monthly_spend_limit": "20000.00",
        "status": "active",
    }
    form = B2bCompanyUserForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "company" in form.errors


@pytest.mark.django_db
def test_b2bwholesale_quote_request_form_excludes(tenant_a, ecom_b2b_company_a, user_a):
    """Test mass assignment protection: status and financial totals are excluded (C4)."""
    form = B2bQuoteRequestForm(tenant=tenant_a)
    excluded = ["status", "original_subtotal", "quoted_discount_percent", "quoted_total"]
    for field in excluded:
        assert field not in form.fields


@pytest.mark.django_db
def test_b2bwholesale_quote_request_form_valid(tenant_a, ecom_b2b_company_a, user_a):
    """Test valid quote request form submission."""
    currency = Currency.objects.filter(code="USD").first() or Currency.objects.create(code="USD", name="US Dollar", symbol="$")
    data = {
        "company": ecom_b2b_company_a.pk,
        "requested_by": user_a.pk,
        "currency": currency.pk,
        "target_budget": "25000.00",
        "tax_amount": "0.00",
        "shipping_estimate": "350.00",
        "buyer_notes": "Special freight packaging required.",
    }
    form = B2bQuoteRequestForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    qr = form.save()
    assert qr.target_budget == Decimal("25000.00")
    assert qr.buyer_notes == "Special freight packaging required."


@pytest.mark.django_db
def test_b2bwholesale_quick_order_template_form_valid(tenant_a, ecom_b2b_company_a, user_a):
    """Test valid quick order template form submission."""
    data = {
        "name": "Fast Requisition Kit",
        "company": ecom_b2b_company_a.pk,
        "created_by": user_a.pk,
        "description": "Standard recurring parts list.",
        "scope": "company_shared",
        "cadence": "weekly",
        "is_active": True,
    }
    form = B2bQuickOrderTemplateForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    tmpl = form.save()
    assert tmpl.name == "Fast Requisition Kit"
    assert tmpl.scope == "company_shared"
    assert tmpl.cadence == "weekly"
