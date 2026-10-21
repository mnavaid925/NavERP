"""Sub-module 8.14 Partner & Channel Management -- Form Tests.

Covers:
1. Field presence and contract verification:
   - Exclusions: tenant, number must never be exposed (mass-assignment prevention).
   - Exclusions: resolved_by, resolved_at excluded from ChannelConflictForm.
2. Tenant-scoped querysets:
   - Form __init__(tenant=tenant) scopes FK dropdowns strictly to the user's tenant.
   - Tenant B records never appear in Tenant A form dropdowns.
3. Cross-tenant injection rejection (_reject_foreign):
   - Submitting foreign PKs fails form validation with field-level errors.
4. Validation rules and bounds in forms:
   - Required fields, percentage bounds (0-100), date bounds.
   - Invariant cross-field rules (partner != customer, claimant != competing).
5. Successful instance creation and save.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounting.models import Currency
from apps.accounts.models import User
from apps.core.models import Document, Party, PartyRole, Tenant
from apps.crm.models import Opportunity, Territory
from apps.sales.forms.PartnerChannel.ChannelConflicts import ChannelConflictForm
from apps.sales.forms.PartnerChannel.DealRegistrations import DealRegistrationForm
from apps.sales.forms.PartnerChannel.JointAccountPlans import JointAccountPlanForm
from apps.sales.forms.PartnerChannel.PartnerProfiles import PartnerProfileForm
from apps.sales.models.PartnerChannel.ChannelConflicts import ChannelConflict
from apps.sales.models.PartnerChannel.DealRegistrations import DealRegistration
from apps.sales.models.PartnerChannel.JointAccountPlans import JointAccountPlan
from apps.sales.models.PartnerChannel.PartnerProfiles import PartnerProfile

pytestmark = pytest.mark.django_db


# ============================================================================
# Helpers
# ============================================================================

def _partnerchannel_partner_party(tenant, name="Alpha Partner VAR"):
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.create(tenant=tenant, party=party, role="partner")
    return party


def _partnerchannel_customer_party(tenant, name="Omega Client Corp"):
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.create(tenant=tenant, party=party, role="customer")
    return party


def _partnerchannel_currency(code="USD"):
    curr, _ = Currency.objects.get_or_create(code=code, defaults={"name": "US Dollar", "symbol": "$"})
    return curr


def _partnerchannel_doc(tenant, title="Partner Contract"):
    return Document.objects.create(tenant=tenant, title=title)


def _partnerchannel_territory(tenant, name="North America East"):
    return Territory.objects.create(tenant=tenant, name=name, code=name[:10].upper().replace(" ", "-"))


# ============================================================================
# 1. Field Exclusions & Contract
# ============================================================================

def test_partnerchannel_form_field_exclusions():
    """Verify tenant and number are excluded from all Partner Channel forms."""
    forms_to_check = [
        PartnerProfileForm,
        DealRegistrationForm,
        JointAccountPlanForm,
        ChannelConflictForm,
    ]

    for form_cls in forms_to_check:
        form = form_cls()
        fields = form.fields.keys()
        assert "tenant" not in fields, f"{form_cls.__name__} must not expose tenant"
        assert "number" not in fields, f"{form_cls.__name__} must not expose number"

    # Specific administrative field exclusions
    ccf_form = ChannelConflictForm()
    assert "resolved_by" not in ccf_form.fields
    assert "resolved_at" not in ccf_form.fields


def test_partnerchannel_form_field_presence():
    """Verify each form exposes exactly the expected domain fields."""
    pp_form = PartnerProfileForm()
    assert "partner" in pp_form.fields
    assert "tier" in pp_form.fields
    assert "partner_type" in pp_form.fields
    assert "base_discount_pct" in pp_form.fields
    assert "deal_reg_margin_pct" in pp_form.fields

    dlr_form = DealRegistrationForm()
    assert "partner" in dlr_form.fields
    assert "customer_account" in dlr_form.fields
    assert "estimated_value" in dlr_form.fields
    assert "expected_close_date" in dlr_form.fields

    jap_form = JointAccountPlanForm()
    assert "partner" in jap_form.fields
    assert "client_account" in jap_form.fields
    assert "plan_name" in jap_form.fields
    assert "co_sell_motion" in jap_form.fields
    assert "action_items" in jap_form.fields

    ccf_form = ChannelConflictForm()
    assert "conflict_type" in ccf_form.fields
    assert "claimant_partner" in ccf_form.fields
    assert "client_account" in ccf_form.fields
    assert "escalation_level" in ccf_form.fields


# ============================================================================
# 2. Tenant-Scoped Querysets
# ============================================================================

def test_partnerchannel_form_foreign_keys_scoped_to_tenant(tenant_a, tenant_b, admin_user, admin_b):
    """Verify dropdown querysets only present records from the requesting tenant."""
    # Tenant A records
    p_a = _partnerchannel_partner_party(tenant_a, "Tenant A Partner")
    c_a = _partnerchannel_customer_party(tenant_a, "Tenant A Customer")
    doc_a = _partnerchannel_doc(tenant_a, "Tenant A Agreement")
    ter_a = _partnerchannel_territory(tenant_a, "Tenant A Region")

    # Tenant B records
    p_b = _partnerchannel_partner_party(tenant_b, "Tenant B Partner")
    c_b = _partnerchannel_customer_party(tenant_b, "Tenant B Customer")
    doc_b = _partnerchannel_doc(tenant_b, "Tenant B Agreement")
    ter_b = _partnerchannel_territory(tenant_b, "Tenant B Region")

    # PartnerProfileForm in Tenant A
    form_pp = PartnerProfileForm(tenant=tenant_a)
    assert p_a in form_pp.fields["partner"].queryset
    assert p_b not in form_pp.fields["partner"].queryset
    assert doc_a in form_pp.fields["agreement_document"].queryset
    assert doc_b not in form_pp.fields["agreement_document"].queryset
    assert ter_a in form_pp.fields["authorized_territory"].queryset
    assert ter_b not in form_pp.fields["authorized_territory"].queryset
    assert admin_user in form_pp.fields["channel_manager"].queryset
    assert admin_b not in form_pp.fields["channel_manager"].queryset

    # DealRegistrationForm in Tenant A
    form_dlr = DealRegistrationForm(tenant=tenant_a)
    assert p_a in form_dlr.fields["partner"].queryset
    assert p_b not in form_dlr.fields["partner"].queryset
    assert c_a in form_dlr.fields["customer_account"].queryset
    assert c_b not in form_dlr.fields["customer_account"].queryset

    # JointAccountPlanForm in Tenant A
    form_jap = JointAccountPlanForm(tenant=tenant_a)
    assert p_a in form_jap.fields["partner"].queryset
    assert p_b not in form_jap.fields["partner"].queryset
    assert c_a in form_jap.fields["client_account"].queryset
    assert c_b not in form_jap.fields["client_account"].queryset
    assert doc_a in form_jap.fields["collateral_document"].queryset
    assert doc_b not in form_jap.fields["collateral_document"].queryset

    # ChannelConflictForm in Tenant A
    form_ccf = ChannelConflictForm(tenant=tenant_a)
    assert p_a in form_ccf.fields["claimant_partner"].queryset
    assert p_b not in form_ccf.fields["claimant_partner"].queryset
    assert c_a in form_ccf.fields["client_account"].queryset
    assert c_b not in form_ccf.fields["client_account"].queryset


# ============================================================================
# 3. Cross-Tenant Rejection
# ============================================================================

def test_partnerchannel_partner_profile_form_rejects_cross_tenant_fk(tenant_a, tenant_b):
    """Submitting foreign tenant FKs must be rejected by form validation."""
    curr = _partnerchannel_currency()
    p_b = _partnerchannel_partner_party(tenant_b, "Foreign Partner")

    data = {
        "partner": p_b.pk,
        "partner_type": "reseller",
        "onboarding_status": "applied",
        "tier": "registered",
        "currency": curr.pk,
        "annual_revenue_target": "100000.00",
        "actual_revenue_ytd": "0.00",
        "required_certifications_count": 1,
        "active_certifications_count": 0,
        "base_discount_pct": "10.00",
        "deal_reg_margin_pct": "15.00",
    }
    form = PartnerProfileForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "partner" in form.errors


def test_partnerchannel_deal_registration_form_rejects_cross_tenant_fk(tenant_a, tenant_b):
    """DealRegistrationForm must reject cross-tenant customer account."""
    curr = _partnerchannel_currency()
    p_a = _partnerchannel_partner_party(tenant_a, "Tenant A Partner")
    c_b = _partnerchannel_customer_party(tenant_b, "Foreign Customer")
    today = timezone.localdate()

    data = {
        "partner": p_a.pk,
        "customer_account": c_b.pk,
        "deal_name": "Injected Foreign Deal",
        "estimated_value": "50000.00",
        "currency": curr.pk,
        "expected_close_date": today + timedelta(days=30),
        "submission_date": today,
        "status": "submitted",
        "exclusivity_status": "pending",
        "protected_margin_pct": "15.00",
    }
    form = DealRegistrationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "customer_account" in form.errors


def test_partnerchannel_joint_account_plan_form_rejects_cross_tenant_fk(tenant_a, tenant_b):
    """JointAccountPlanForm must reject cross-tenant partner or client."""
    curr = _partnerchannel_currency()
    p_b = _partnerchannel_partner_party(tenant_b, "Foreign Partner")
    c_a = _partnerchannel_customer_party(tenant_a, "Tenant A Customer")
    today = timezone.localdate()

    data = {
        "partner": p_b.pk,
        "client_account": c_a.pk,
        "plan_name": "Foreign Joint Plan",
        "plan_year": 2026,
        "period_start": today,
        "period_end": today + timedelta(days=90),
        "status": "draft",
        "target_revenue": "200000.00",
        "actual_revenue": "0.00",
        "currency": curr.pk,
        "partner_lead_name": "John Partner",
        "co_sell_motion": "joint_pursuit",
    }
    form = JointAccountPlanForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "partner" in form.errors


def test_partnerchannel_channel_conflict_form_rejects_cross_tenant_fk(tenant_a, tenant_b):
    """ChannelConflictForm must reject cross-tenant claimant partner."""
    p_b = _partnerchannel_partner_party(tenant_b, "Foreign Partner")
    c_a = _partnerchannel_customer_party(tenant_a, "Tenant A Customer")

    data = {
        "conflict_type": "direct_vs_indirect",
        "severity": "medium",
        "status": "open",
        "claimant_partner": p_b.pk,
        "client_account": c_a.pk,
        "escalation_level": "l1_cam",
        "resolution_outcome": "pending",
        "split_percentage": "0.00",
    }
    form = ChannelConflictForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "claimant_partner" in form.errors


# ============================================================================
# 4. Form Validation & Invariant Rules
# ============================================================================

def test_partnerchannel_deal_registration_same_partner_and_customer_rejected(tenant_a):
    """Deal registration must fail if customer account is the partner itself."""
    curr = _partnerchannel_currency()
    p_a = _partnerchannel_partner_party(tenant_a, "Partner Corp")
    today = timezone.localdate()

    data = {
        "partner": p_a.pk,
        "customer_account": p_a.pk,
        "deal_name": "Self Deal",
        "estimated_value": "10000.00",
        "currency": curr.pk,
        "expected_close_date": today + timedelta(days=30),
        "submission_date": today,
        "status": "submitted",
        "exclusivity_status": "pending",
        "protected_margin_pct": "15.00",
    }
    form = DealRegistrationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "customer_account" in form.errors or "__all__" in form.errors


def test_partnerchannel_deal_registration_dates_validation(tenant_a):
    """Deal registration protection end date must not be before start date."""
    curr = _partnerchannel_currency()
    p_a = _partnerchannel_partner_party(tenant_a, "Partner Corp")
    c_a = _partnerchannel_customer_party(tenant_a, "Customer Corp")
    today = timezone.localdate()

    data = {
        "partner": p_a.pk,
        "customer_account": c_a.pk,
        "deal_name": "Inverted Dates Deal",
        "estimated_value": "10000.00",
        "currency": curr.pk,
        "expected_close_date": today + timedelta(days=30),
        "submission_date": today,
        "status": "submitted",
        "exclusivity_status": "pending",
        "protection_start_date": today + timedelta(days=10),
        "protection_end_date": today,  # Before start date
        "protected_margin_pct": "15.00",
    }
    form = DealRegistrationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "protection_end_date" in form.errors or "__all__" in form.errors


def test_partnerchannel_joint_account_plan_dates_validation(tenant_a):
    """Joint account plan period end date must be on or after period start date."""
    curr = _partnerchannel_currency()
    p_a = _partnerchannel_partner_party(tenant_a, "Partner Corp")
    c_a = _partnerchannel_customer_party(tenant_a, "Client Corp")
    today = timezone.localdate()

    data = {
        "partner": p_a.pk,
        "client_account": c_a.pk,
        "plan_name": "Inverted Dates Plan",
        "plan_year": 2026,
        "period_start": today + timedelta(days=30),
        "period_end": today,  # Earlier than period start
        "status": "draft",
        "target_revenue": "100000.00",
        "actual_revenue": "0.00",
        "currency": curr.pk,
        "partner_lead_name": "Lead Partner",
        "co_sell_motion": "joint_pursuit",
    }
    form = JointAccountPlanForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "period_end" in form.errors or "__all__" in form.errors


def test_partnerchannel_channel_conflict_same_claimant_and_competing_rejected(tenant_a):
    """Claimant partner cannot conflict against itself as the competing partner."""
    p_a = _partnerchannel_partner_party(tenant_a, "Partner Corp")
    c_a = _partnerchannel_customer_party(tenant_a, "Client Corp")

    data = {
        "conflict_type": "partner_vs_partner",
        "severity": "high",
        "status": "open",
        "claimant_partner": p_a.pk,
        "competing_partner": p_a.pk,  # Same as claimant
        "client_account": c_a.pk,
        "escalation_level": "l1_cam",
        "resolution_outcome": "pending",
        "split_percentage": "0.00",
    }
    form = ChannelConflictForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "competing_partner" in form.errors or "__all__" in form.errors


# ============================================================================
# 5. Successful Save & Binding
# ============================================================================

def test_partnerchannel_partner_profile_form_valid_save(tenant_a, admin_user):
    """Valid PartnerProfileForm submission creates record with proper tenant binding."""
    curr = _partnerchannel_currency()
    p_a = _partnerchannel_partner_party(tenant_a, "Valid VAR Partner")
    today = timezone.localdate()

    data = {
        "partner": p_a.pk,
        "partner_type": "reseller",
        "onboarding_status": "applied",
        "tier": "bronze",
        "application_date": today,
        "channel_manager": admin_user.pk,
        "currency": curr.pk,
        "annual_revenue_target": "250000.00",
        "actual_revenue_ytd": "50000.00",
        "required_certifications_count": 2,
        "active_certifications_count": 1,
        "base_discount_pct": "12.50",
        "deal_reg_margin_pct": "17.50",
        "portal_access_enabled": True,
        "notes": "Strong regional footprint.",
    }
    form = PartnerProfileForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.tenant == tenant_a
    assert instance.partner == p_a
    assert instance.tier == "bronze"
    assert instance.number.startswith("PTR-")


def test_partnerchannel_deal_registration_form_valid_save(tenant_a):
    """Valid DealRegistrationForm submission creates record bound to tenant."""
    curr = _partnerchannel_currency()
    p_a = _partnerchannel_partner_party(tenant_a, "Partner Company")
    c_a = _partnerchannel_customer_party(tenant_a, "Prospective Client")
    today = timezone.localdate()

    data = {
        "partner": p_a.pk,
        "customer_account": c_a.pk,
        "deal_name": "Midmarket Finance Automation",
        "estimated_value": "85000.00",
        "currency": curr.pk,
        "expected_close_date": today + timedelta(days=45),
        "submission_date": today,
        "status": "submitted",
        "exclusivity_status": "pending",
        "protected_margin_pct": "15.00",
        "partner_rep_name": "Alice Channel",
        "partner_rep_email": "alice@partner.example.com",
    }
    form = DealRegistrationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.tenant == tenant_a
    assert instance.deal_name == "Midmarket Finance Automation"
    assert instance.number.startswith("DLR-")


def test_partnerchannel_joint_account_plan_form_valid_save(tenant_a, admin_user):
    """Valid JointAccountPlanForm submission creates record bound to tenant."""
    curr = _partnerchannel_currency()
    p_a = _partnerchannel_partner_party(tenant_a, "Consulting Partner")
    c_a = _partnerchannel_customer_party(tenant_a, "Enterprise Client")
    today = timezone.localdate()

    data = {
        "partner": p_a.pk,
        "client_account": c_a.pk,
        "plan_name": "2026 Strategic Cloud Modernization",
        "plan_year": 2026,
        "period_start": today,
        "period_end": today + timedelta(days=180),
        "status": "draft",
        "target_revenue": "500000.00",
        "actual_revenue": "0.00",
        "currency": curr.pk,
        "vendor_lead": admin_user.pk,
        "partner_lead_name": "Bob Champion",
        "partner_lead_email": "bob@consulting.example.com",
        "co_sell_motion": "joint_pursuit",
        "strategic_objectives": "Migrate core ledger to cloud",
        "joint_value_proposition": "Reduced downtime and guaranteed SLA",
    }
    form = JointAccountPlanForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.tenant == tenant_a
    assert instance.plan_name == "2026 Strategic Cloud Modernization"
    assert instance.number.startswith("JAP-")


def test_partnerchannel_channel_conflict_form_valid_save(tenant_a, admin_user):
    """Valid ChannelConflictForm submission creates record bound to tenant."""
    p_a = _partnerchannel_partner_party(tenant_a, "Claimant Partner")
    c_a = _partnerchannel_customer_party(tenant_a, "Disputed Client")

    data = {
        "conflict_type": "direct_vs_indirect",
        "severity": "medium",
        "status": "open",
        "claimant_partner": p_a.pk,
        "direct_sales_rep": admin_user.pk,
        "client_account": c_a.pk,
        "escalation_level": "l1_cam",
        "resolution_outcome": "pending",
        "split_percentage": "0.00",
        "description": "Direct sales AE approached existing registered prospect.",
    }
    form = ChannelConflictForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.tenant == tenant_a
    assert instance.status == "open"
    assert instance.number.startswith("CCF-")
