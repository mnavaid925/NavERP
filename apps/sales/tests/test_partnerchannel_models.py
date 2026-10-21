"""Sub-module 8.14 Partner & Channel Management -- Model Tests.

Covers:
1. Field presence and contract verification against PARTNERCHANNEL_MODEL_FIELDS.
2. Choices contract verification against PARTNERCHANNEL_CHOICES.
3. String representations (__str__) for all 4 models:
   - PartnerProfile (PTR-#####)
   - DealRegistration (DLR-#####)
   - JointAccountPlan (JAP-#####)
   - ChannelConflict (CCF-#####)
4. Auto-numbering prefixes and multi-tenant sequence isolation.
5. Invariant & cross-tenant validation guards in clean():
   - PartnerProfile: cross-tenant channel_manager / territory / document / partner, active requires agreement_signed_at.
   - DealRegistration: cross-tenant party / opportunity, customer != partner, protection_end >= protection_start, approved requires protection dates.
   - JointAccountPlan: cross-tenant party / document, client != partner, period_end >= period_start.
   - ChannelConflict: cross-tenant parties / territory / deal reg / opp, claimant != competing partner, claimant != client account, resolved requirements.
6. Computed properties & badges:
   - revenue_attainment_pct, certification_compliance_pct, days_remaining, is_protection_active.
   - tier_badge_class, status_badge_class, exclusivity_badge_class, severity_badge_class, escalation_badge_class.
7. Constraints & Meta options:
   - Unique constraints on (tenant, number) and (tenant, partner).
   - Range validation on split_percentage, base_discount_pct, protected_margin_pct.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.core.models import Document, Party
from apps.crm.models import Opportunity, Territory as CrmTerritory
from apps.sales.models import (
    ChannelConflict,
    DealRegistration,
    JointAccountPlan,
    PartnerProfile,
)
from apps.sales.tests.conftest import (
    PARTNERCHANNEL_CHOICES,
    PARTNERCHANNEL_MODEL_FIELDS,
    _partnerchannel_channel_conflict,
    _partnerchannel_deal_registration,
    _partnerchannel_joint_account_plan,
    _partnerchannel_partner_profile,
    _partnerchannel_party,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Module Helpers (must be prefixed with _partnerchannel_)
# ==============================================================================

def _partnerchannel_document(tenant, name="Partnership Agreement"):
    return Document.objects.create(
        tenant=tenant,
        name=name,
        file="agreements/sample.pdf",
    )


def _partnerchannel_territory(tenant, name="North America Channel"):
    return CrmTerritory.objects.create(
        tenant=tenant,
        name=name,
    )


def _partnerchannel_opportunity(tenant, name="Q4 Cloud Expansion"):
    return Opportunity.objects.create(
        tenant=tenant,
        name=name,
        amount=Decimal("150000.00"),
        stage="prospecting",
    )


# ==============================================================================
# 1. Contract Adherence Tests
# ==============================================================================

def test_partnerchannel_models_contract_fields():
    """Verify all 4 models declare all expected fields from PARTNERCHANNEL_MODEL_FIELDS."""
    model_map = {
        "PartnerProfile": PartnerProfile,
        "DealRegistration": DealRegistration,
        "JointAccountPlan": JointAccountPlan,
        "ChannelConflict": ChannelConflict,
    }
    for model_name, expected_fields in PARTNERCHANNEL_MODEL_FIELDS.items():
        model_cls = model_map[model_name]
        actual_fields = {f.name for f in model_cls._meta.get_fields()}
        missing = set(expected_fields) - actual_fields
        assert not missing, f"{model_name} is missing fields: {missing}"


def test_partnerchannel_models_contract_choices():
    """Verify all model choices match the declared choices in PARTNERCHANNEL_CHOICES."""
    model_map = {
        "PartnerProfile": PartnerProfile,
        "DealRegistration": DealRegistration,
        "JointAccountPlan": JointAccountPlan,
        "ChannelConflict": ChannelConflict,
    }
    for model_name, choices_dict in PARTNERCHANNEL_CHOICES.items():
        model_cls = model_map[model_name]
        for field_name, expected_pairs in choices_dict.items():
            field = model_cls._meta.get_field(field_name)
            actual_pairs = tuple(field.choices)
            assert actual_pairs == expected_pairs, (
                f"Mismatch in {model_name}.{field_name} choices:\n"
                f"Expected: {expected_pairs}\nActual: {actual_pairs}"
            )


# ==============================================================================
# 2. PartnerProfile Model Tests
# ==============================================================================

def test_partnerchannel_models_partner_profile_numbering_and_str(pc_profile_a):
    """Verify numbering prefix 'PTR' and __str__ formatting."""
    assert pc_profile_a.NUMBER_PREFIX == "PTR"
    assert pc_profile_a.number.startswith("PTR-")
    expected_str = f"{pc_profile_a.number} — {pc_profile_a.partner.name} ({pc_profile_a.get_tier_display()})"
    assert str(pc_profile_a) == expected_str


def test_partnerchannel_models_partner_profile_defaults(tenant_a, pc_partner_a, pc_currency):
    """Verify field defaults on newly created PartnerProfile."""
    profile = PartnerProfile(
        tenant=tenant_a,
        partner=pc_partner_a,
        currency=pc_currency,
    )
    assert profile.partner_type == "reseller"
    assert profile.onboarding_status == "applied"
    assert profile.tier == "registered"
    assert profile.annual_revenue_target == Decimal("0.00")
    assert profile.actual_revenue_ytd == Decimal("0.00")
    assert profile.required_certifications_count == 1
    assert profile.active_certifications_count == 0
    assert profile.base_discount_pct == Decimal("10.00")
    assert profile.deal_reg_margin_pct == Decimal("15.00")
    assert profile.portal_access_enabled is False


def test_partnerchannel_models_partner_profile_badges(pc_profile_a):
    """Verify tier_badge_class and status_badge_class mappings."""
    # Test tier badges
    tier_expectations = {
        "platinum": "badge-green",
        "gold": "badge-amber",
        "silver": "badge-slate",
        "bronze": "badge-info",
        "registered": "badge-muted",
        "unknown_tier": "badge-muted",
    }
    for tier, expected_badge in tier_expectations.items():
        pc_profile_a.tier = tier
        assert pc_profile_a.tier_badge_class == expected_badge

    # Test status badges
    status_expectations = {
        "active": "badge-green",
        "onboarding": "badge-info",
        "agreement_pending": "badge-amber",
        "under_review": "badge-slate",
        "applied": "badge-muted",
        "suspended": "badge-amber",
        "terminated": "badge-red",
        "unknown_status": "badge-slate",
    }
    for status, expected_badge in status_expectations.items():
        pc_profile_a.onboarding_status = status
        assert pc_profile_a.status_badge_class == expected_badge


def test_partnerchannel_models_partner_profile_properties(pc_profile_a):
    """Verify revenue attainment and certification compliance percentages."""
    pc_profile_a.annual_revenue_target = Decimal("1000000.00")
    pc_profile_a.actual_revenue_ytd = Decimal("450000.00")
    assert pc_profile_a.revenue_attainment_pct == Decimal("45.0")

    # Zero target returns Decimal("0.0")
    pc_profile_a.annual_revenue_target = Decimal("0.00")
    assert pc_profile_a.revenue_attainment_pct == Decimal("0.0")

    # Certification compliance
    pc_profile_a.required_certifications_count = 5
    pc_profile_a.active_certifications_count = 3
    assert pc_profile_a.certification_compliance_pct == 60

    # Capped at 100%
    pc_profile_a.active_certifications_count = 10
    assert pc_profile_a.certification_compliance_pct == 100

    # Zero required certifications returns 100%
    pc_profile_a.required_certifications_count = 0
    assert pc_profile_a.certification_compliance_pct == 100


def test_partnerchannel_models_partner_profile_clean_active_requires_agreement(
    tenant_a, pc_currency
):
    """Verify active certified partner must have agreement_signed_at timestamp."""
    party = _partnerchannel_party(tenant_a, name="New Unsigned Partner")
    profile = PartnerProfile(
        tenant=tenant_a,
        partner=party,
        currency=pc_currency,
        onboarding_status="active",
        agreement_signed_at=None,
    )
    with pytest.raises(ValidationError) as exc:
        profile.clean()
    assert "agreement_signed_at" in exc.value.message_dict

    # Set timestamp -> validation passes
    profile.agreement_signed_at = timezone.now()
    profile.clean()


def test_partnerchannel_models_partner_profile_clean_cross_tenant_channel_manager(
    tenant_a, pc_partner_a, pc_currency, admin_b
):
    """Verify channel manager from tenant_b is rejected on tenant_a profile."""
    profile = PartnerProfile(
        tenant=tenant_a,
        partner=pc_partner_a,
        currency=pc_currency,
        channel_manager=admin_b,
    )
    with pytest.raises(ValidationError) as exc:
        profile.clean()
    assert "channel_manager" in exc.value.message_dict


def test_partnerchannel_models_partner_profile_clean_cross_tenant_relations(
    tenant_a, tenant_b, pc_currency
):
    """Verify cross-tenant partner, authorized_territory, and agreement_document are rejected."""
    # Cross-tenant partner
    foreign_partner = _partnerchannel_party(tenant_b, name="Foreign Partner")
    profile1 = PartnerProfile(
        tenant=tenant_a,
        partner=foreign_partner,
        currency=pc_currency,
    )
    with pytest.raises(ValidationError) as exc:
        profile1.clean()
    assert "partner" in exc.value.message_dict

    # Cross-tenant territory
    local_partner = _partnerchannel_party(tenant_a, name="Local Partner")
    foreign_territory = _partnerchannel_territory(tenant_b, name="Foreign Territory")
    profile2 = PartnerProfile(
        tenant=tenant_a,
        partner=local_partner,
        currency=pc_currency,
        authorized_territory=foreign_territory,
    )
    with pytest.raises(ValidationError) as exc:
        profile2.clean()
    assert "authorized_territory" in exc.value.message_dict

    # Cross-tenant document
    foreign_doc = _partnerchannel_document(tenant_b, name="Foreign Document")
    profile3 = PartnerProfile(
        tenant=tenant_a,
        partner=local_partner,
        currency=pc_currency,
        agreement_document=foreign_doc,
    )
    with pytest.raises(ValidationError) as exc:
        profile3.clean()
    assert "agreement_document" in exc.value.message_dict


def test_partnerchannel_models_partner_profile_unique_number(pc_profile_a, tenant_a, pc_currency):
    """Verify unique constraint on (tenant, number)."""
    other_partner = _partnerchannel_party(tenant_a, name="Duplicate Num Partner")
    dup = PartnerProfile(
        tenant=tenant_a,
        partner=other_partner,
        currency=pc_currency,
        number=pc_profile_a.number,
    )
    with pytest.raises(IntegrityError):
        dup.save()


def test_partnerchannel_models_partner_profile_unique_partner(pc_profile_a, tenant_a, pc_currency):
    """Verify unique constraint on (tenant, partner) prevents multiple profiles for same party."""
    dup = PartnerProfile(
        tenant=tenant_a,
        partner=pc_profile_a.partner,
        currency=pc_currency,
    )
    with pytest.raises(IntegrityError):
        dup.save()


# ==============================================================================
# 3. DealRegistration Model Tests
# ==============================================================================

def test_partnerchannel_models_deal_registration_numbering_and_str(pc_deal_reg_a):
    """Verify numbering prefix 'DLR' and __str__ formatting."""
    assert pc_deal_reg_a.NUMBER_PREFIX == "DLR"
    assert pc_deal_reg_a.number.startswith("DLR-")
    expected_str = f"{pc_deal_reg_a.number} — {pc_deal_reg_a.deal_name} ({pc_deal_reg_a.partner.name})"
    assert str(pc_deal_reg_a) == expected_str


def test_partnerchannel_models_deal_registration_badges(pc_deal_reg_a):
    """Verify status_badge_class and exclusivity_badge_class mappings."""
    status_expectations = {
        "approved": "badge-green",
        "converted": "badge-green",
        "under_review": "badge-info",
        "submitted": "badge-muted",
        "conflicted": "badge-amber",
        "expired": "badge-slate",
        "rejected": "badge-red",
        "unknown": "badge-slate",
    }
    for status, expected_badge in status_expectations.items():
        pc_deal_reg_a.status = status
        assert pc_deal_reg_a.status_badge_class == expected_badge

    exclusivity_expectations = {
        "exclusive": "badge-green",
        "non_exclusive": "badge-info",
        "pending": "badge-muted",
        "expired": "badge-slate",
        "revoked": "badge-red",
        "unknown": "badge-slate",
    }
    for excl, expected_badge in exclusivity_expectations.items():
        pc_deal_reg_a.exclusivity_status = excl
        assert pc_deal_reg_a.exclusivity_badge_class == expected_badge


def test_partnerchannel_models_deal_registration_properties(pc_deal_reg_a):
    """Verify days_remaining and is_protection_active properties."""
    today = timezone.localdate()
    pc_deal_reg_a.status = "approved"
    pc_deal_reg_a.protection_start_date = today - timedelta(days=10)
    pc_deal_reg_a.protection_end_date = today + timedelta(days=20)
    assert pc_deal_reg_a.is_protection_active is True
    assert pc_deal_reg_a.days_remaining == 20

    # Expired protection
    pc_deal_reg_a.protection_end_date = today - timedelta(days=1)
    assert pc_deal_reg_a.is_protection_active is False
    assert pc_deal_reg_a.days_remaining == 0

    # Non-approved status is not active even if future date
    pc_deal_reg_a.status = "rejected"
    pc_deal_reg_a.protection_end_date = today + timedelta(days=20)
    assert pc_deal_reg_a.is_protection_active is False

    # Missing end date returns 0 days
    pc_deal_reg_a.protection_end_date = None
    assert pc_deal_reg_a.days_remaining == 0


def test_partnerchannel_models_deal_registration_clean_cross_tenant_party(
    tenant_a, tenant_b, pc_partner_a, pc_customer_a, pc_currency
):
    """Verify cross-tenant partner or customer is rejected."""
    foreign_customer = _partnerchannel_party(tenant_b, name="Globex Account", role="customer")
    reg = DealRegistration(
        tenant=tenant_a,
        partner=pc_partner_a,
        customer_account=foreign_customer,
        deal_name="Invalid Cross-Tenant Deal",
        estimated_value=Decimal("50000.00"),
        currency=pc_currency,
        expected_close_date=timezone.localdate() + timedelta(days=30),
    )
    with pytest.raises(ValidationError) as exc:
        reg.clean()
    assert "customer_account" in exc.value.message_dict

    foreign_partner = _partnerchannel_party(tenant_b, name="Globex Partner", role="partner")
    reg2 = DealRegistration(
        tenant=tenant_a,
        partner=foreign_partner,
        customer_account=pc_customer_a,
        deal_name="Invalid Cross-Tenant Partner",
        estimated_value=Decimal("50000.00"),
        currency=pc_currency,
        expected_close_date=timezone.localdate() + timedelta(days=30),
    )
    with pytest.raises(ValidationError) as exc:
        reg2.clean()
    assert "partner" in exc.value.message_dict


def test_partnerchannel_models_deal_registration_clean_customer_not_equal_partner(
    tenant_a, pc_partner_a, pc_currency
):
    """Verify partner cannot register itself as the client account."""
    reg = DealRegistration(
        tenant=tenant_a,
        partner=pc_partner_a,
        customer_account=pc_partner_a,
        deal_name="Self Registration",
        estimated_value=Decimal("50000.00"),
        currency=pc_currency,
        expected_close_date=timezone.localdate() + timedelta(days=30),
    )
    with pytest.raises(ValidationError) as exc:
        reg.clean()
    assert "customer_account" in exc.value.message_dict


def test_partnerchannel_models_deal_registration_clean_protection_dates(
    tenant_a, pc_partner_a, pc_customer_a, pc_currency
):
    """Verify protection_end_date >= protection_start_date and approved status requires dates."""
    today = timezone.localdate()
    # End before start
    reg = DealRegistration(
        tenant=tenant_a,
        partner=pc_partner_a,
        customer_account=pc_customer_a,
        deal_name="Inverted Dates Deal",
        estimated_value=Decimal("50000.00"),
        currency=pc_currency,
        expected_close_date=today + timedelta(days=30),
        protection_start_date=today,
        protection_end_date=today - timedelta(days=5),
    )
    with pytest.raises(ValidationError) as exc:
        reg.clean()
    assert "protection_end_date" in exc.value.message_dict

    # Approved without dates
    reg.status = "approved"
    reg.protection_start_date = None
    reg.protection_end_date = None
    with pytest.raises(ValidationError) as exc:
        reg.clean()
    assert "protection_start_date" in exc.value.message_dict


def test_partnerchannel_models_deal_registration_clean_cross_tenant_opportunity(
    tenant_a, tenant_b, pc_partner_a, pc_customer_a, pc_currency
):
    """Verify linked opportunity must belong to the same tenant."""
    foreign_opp = _partnerchannel_opportunity(tenant_b, name="Foreign Opp")
    reg = DealRegistration(
        tenant=tenant_a,
        partner=pc_partner_a,
        customer_account=pc_customer_a,
        deal_name="Cross-Tenant Opp Deal",
        estimated_value=Decimal("50000.00"),
        currency=pc_currency,
        expected_close_date=timezone.localdate() + timedelta(days=30),
        opportunity=foreign_opp,
    )
    with pytest.raises(ValidationError) as exc:
        reg.clean()
    assert "opportunity" in exc.value.message_dict


def test_partnerchannel_models_deal_registration_unique_number(
    pc_deal_reg_a, tenant_a, pc_partner_a, pc_customer_a, pc_currency
):
    """Verify unique constraint on (tenant, number)."""
    dup = DealRegistration(
        tenant=tenant_a,
        partner=pc_partner_a,
        customer_account=pc_customer_a,
        deal_name="Duplicate Num Deal",
        estimated_value=Decimal("25000.00"),
        currency=pc_currency,
        expected_close_date=timezone.localdate() + timedelta(days=40),
        number=pc_deal_reg_a.number,
    )
    with pytest.raises(IntegrityError):
        dup.save()


# ==============================================================================
# 4. JointAccountPlan Model Tests
# ==============================================================================

def test_partnerchannel_models_joint_account_plan_numbering_and_str(pc_joint_plan_a):
    """Verify numbering prefix 'JAP' and __str__ formatting."""
    assert pc_joint_plan_a.NUMBER_PREFIX == "JAP"
    assert pc_joint_plan_a.number.startswith("JAP-")
    expected_str = (
        f"{pc_joint_plan_a.number} — {pc_joint_plan_a.plan_name} "
        f"({pc_joint_plan_a.partner.name} + {pc_joint_plan_a.client_account.name})"
    )
    assert str(pc_joint_plan_a) == expected_str


def test_partnerchannel_models_joint_account_plan_badges(pc_joint_plan_a):
    """Verify status_badge_class mapping on JointAccountPlan."""
    status_expectations = {
        "active": "badge-green",
        "achieved": "badge-green",
        "draft": "badge-muted",
        "underperforming": "badge-amber",
        "closed": "badge-slate",
        "unknown": "badge-slate",
    }
    for status, expected_badge in status_expectations.items():
        pc_joint_plan_a.status = status
        assert pc_joint_plan_a.status_badge_class == expected_badge


def test_partnerchannel_models_joint_account_plan_revenue_progress(pc_joint_plan_a):
    """Verify revenue attainment progress calculation."""
    pc_joint_plan_a.target_revenue = Decimal("500000.00")
    pc_joint_plan_a.actual_revenue = Decimal("125000.00")
    assert pc_joint_plan_a.revenue_attainment_pct == Decimal("25.0")

    # Zero target returns Decimal("0.0")
    pc_joint_plan_a.target_revenue = Decimal("0.00")
    assert pc_joint_plan_a.revenue_attainment_pct == Decimal("0.0")


def test_partnerchannel_models_joint_account_plan_clean_cross_tenant_party(
    tenant_a, tenant_b, pc_partner_a, pc_customer_a, pc_currency
):
    """Verify cross-tenant partner, client_account, or collateral_document are rejected."""
    foreign_client = _partnerchannel_party(tenant_b, name="Globex Enterprise", role="customer")
    plan = JointAccountPlan(
        tenant=tenant_a,
        partner=pc_partner_a,
        client_account=foreign_client,
        plan_name="Cross-Tenant Plan",
        period_start=timezone.localdate(),
        period_end=timezone.localdate() + timedelta(days=90),
        currency=pc_currency,
        partner_lead_name="Lead Rep",
    )
    with pytest.raises(ValidationError) as exc:
        plan.clean()
    assert "client_account" in exc.value.message_dict

    foreign_partner = _partnerchannel_party(tenant_b, name="Globex SI", role="partner")
    plan2 = JointAccountPlan(
        tenant=tenant_a,
        partner=foreign_partner,
        client_account=pc_customer_a,
        plan_name="Cross-Tenant Partner Plan",
        period_start=timezone.localdate(),
        period_end=timezone.localdate() + timedelta(days=90),
        currency=pc_currency,
        partner_lead_name="Lead Rep",
    )
    with pytest.raises(ValidationError) as exc:
        plan2.clean()
    assert "partner" in exc.value.message_dict

    # Foreign collateral document
    foreign_doc = _partnerchannel_document(tenant_b, name="Foreign Presentation")
    plan3 = JointAccountPlan(
        tenant=tenant_a,
        partner=pc_partner_a,
        client_account=pc_customer_a,
        plan_name="Foreign Collateral Plan",
        period_start=timezone.localdate(),
        period_end=timezone.localdate() + timedelta(days=90),
        currency=pc_currency,
        partner_lead_name="Lead Rep",
        collateral_document=foreign_doc,
    )
    with pytest.raises(ValidationError) as exc:
        plan3.clean()
    assert "collateral_document" in exc.value.message_dict


def test_partnerchannel_models_joint_account_plan_clean_client_not_equal_partner(
    tenant_a, pc_partner_a, pc_currency
):
    """Verify partner cannot create a joint account plan targeting itself as the client."""
    plan = JointAccountPlan(
        tenant=tenant_a,
        partner=pc_partner_a,
        client_account=pc_partner_a,
        plan_name="Self Targeting Plan",
        period_start=timezone.localdate(),
        period_end=timezone.localdate() + timedelta(days=90),
        currency=pc_currency,
        partner_lead_name="Lead Rep",
    )
    with pytest.raises(ValidationError) as exc:
        plan.clean()
    assert "client_account" in exc.value.message_dict


def test_partnerchannel_models_joint_account_plan_clean_period_dates(
    tenant_a, pc_partner_a, pc_customer_a, pc_currency
):
    """Verify period_end cannot be earlier than period_start."""
    today = timezone.localdate()
    plan = JointAccountPlan(
        tenant=tenant_a,
        partner=pc_partner_a,
        client_account=pc_customer_a,
        plan_name="Invalid Dates Plan",
        period_start=today,
        period_end=today - timedelta(days=1),
        currency=pc_currency,
        partner_lead_name="Lead Rep",
    )
    with pytest.raises(ValidationError) as exc:
        plan.clean()
    assert "period_end" in exc.value.message_dict


def test_partnerchannel_models_joint_account_plan_unique_number(
    pc_joint_plan_a, tenant_a, pc_partner_a, pc_customer_a, pc_currency
):
    """Verify unique constraint on (tenant, number)."""
    dup = JointAccountPlan(
        tenant=tenant_a,
        partner=pc_partner_a,
        client_account=pc_customer_a,
        plan_name="Duplicate Num Plan",
        period_start=timezone.localdate(),
        period_end=timezone.localdate() + timedelta(days=60),
        currency=pc_currency,
        partner_lead_name="Lead Rep",
        number=pc_joint_plan_a.number,
    )
    with pytest.raises(IntegrityError):
        dup.save()


# ==============================================================================
# 5. ChannelConflict Model Tests
# ==============================================================================

def test_partnerchannel_models_channel_conflict_numbering_and_str(pc_conflict_a):
    """Verify numbering prefix 'CCF' and __str__ formatting."""
    assert pc_conflict_a.NUMBER_PREFIX == "CCF"
    assert pc_conflict_a.number.startswith("CCF-")
    expected_str = (
        f"{pc_conflict_a.number} — {pc_conflict_a.get_conflict_type_display()} "
        f"({pc_conflict_a.claimant_partner.name} vs. {pc_conflict_a.client_account.name})"
    )
    assert str(pc_conflict_a) == expected_str


def test_partnerchannel_models_channel_conflict_badges(pc_conflict_a):
    """Verify status, severity, and escalation badge class mappings."""
    # Status badges
    status_expectations = {
        "resolved": "badge-green",
        "in_mediation": "badge-info",
        "open": "badge-amber",
        "escalated": "badge-red",
        "dismissed": "badge-slate",
        "unknown": "badge-slate",
    }
    for status, expected_badge in status_expectations.items():
        pc_conflict_a.status = status
        assert pc_conflict_a.status_badge_class == expected_badge

    # Severity badges
    severity_expectations = {
        "low": "badge-slate",
        "medium": "badge-info",
        "high": "badge-amber",
        "critical": "badge-red",
        "unknown": "badge-slate",
    }
    for sev, expected_badge in severity_expectations.items():
        pc_conflict_a.severity = sev
        assert pc_conflict_a.severity_badge_class == expected_badge

    # Escalation badges
    escalation_expectations = {
        "l1_cam": "badge-slate",
        "l2_channel_chief": "badge-amber",
        "l3_executive_cro": "badge-red",
        "unknown": "badge-slate",
    }
    for esc, expected_badge in escalation_expectations.items():
        pc_conflict_a.escalation_level = esc
        assert pc_conflict_a.escalation_badge_class == expected_badge


def test_partnerchannel_models_channel_conflict_clean_cross_tenant_parties(
    tenant_a, tenant_b, pc_partner_a, pc_customer_a
):
    """Verify cross-tenant claimant_partner, competing_partner, and client_account are rejected."""
    foreign_claimant = _partnerchannel_party(tenant_b, name="Globex Claimant", role="partner")
    c1 = ChannelConflict(
        tenant=tenant_a,
        claimant_partner=foreign_claimant,
        client_account=pc_customer_a,
    )
    with pytest.raises(ValidationError) as exc:
        c1.clean()
    assert "claimant_partner" in exc.value.message_dict

    foreign_competing = _partnerchannel_party(tenant_b, name="Globex Competing", role="partner")
    c2 = ChannelConflict(
        tenant=tenant_a,
        claimant_partner=pc_partner_a,
        competing_partner=foreign_competing,
        client_account=pc_customer_a,
    )
    with pytest.raises(ValidationError) as exc:
        c2.clean()
    assert "competing_partner" in exc.value.message_dict

    foreign_client = _partnerchannel_party(tenant_b, name="Globex Client", role="customer")
    c3 = ChannelConflict(
        tenant=tenant_a,
        claimant_partner=pc_partner_a,
        client_account=foreign_client,
    )
    with pytest.raises(ValidationError) as exc:
        c3.clean()
    assert "client_account" in exc.value.message_dict


def test_partnerchannel_models_channel_conflict_clean_competing_not_equal_claimant(
    tenant_a, pc_partner_a, pc_customer_a
):
    """Verify competing partner cannot be identical to claimant partner."""
    conflict = ChannelConflict(
        tenant=tenant_a,
        claimant_partner=pc_partner_a,
        competing_partner=pc_partner_a,
        client_account=pc_customer_a,
    )
    with pytest.raises(ValidationError) as exc:
        conflict.clean()
    assert "competing_partner" in exc.value.message_dict


def test_partnerchannel_models_channel_conflict_clean_client_not_equal_claimant(
    tenant_a, pc_partner_a
):
    """Verify claimant partner cannot lodge a conflict against itself as the client."""
    conflict = ChannelConflict(
        tenant=tenant_a,
        claimant_partner=pc_partner_a,
        client_account=pc_partner_a,
    )
    with pytest.raises(ValidationError) as exc:
        conflict.clean()
    assert "client_account" in exc.value.message_dict


def test_partnerchannel_models_channel_conflict_clean_resolved_requirements(
    tenant_a, pc_partner_a, pc_customer_a, admin_user
):
    """Verify resolved conflicts must specify resolution_outcome and resolved_at."""
    conflict = ChannelConflict(
        tenant=tenant_a,
        claimant_partner=pc_partner_a,
        client_account=pc_customer_a,
        status="resolved",
        resolution_outcome="pending",
    )
    with pytest.raises(ValidationError) as exc:
        conflict.clean()
    assert "resolution_outcome" in exc.value.message_dict

    conflict.resolution_outcome = "partner_favored"
    conflict.resolved_at = None
    with pytest.raises(ValidationError) as exc:
        conflict.clean()
    assert "resolved_at" in exc.value.message_dict

    # Valid resolved state
    conflict.resolved_at = timezone.now()
    conflict.resolved_by = admin_user
    conflict.clean()


def test_partnerchannel_models_channel_conflict_split_percentage_validation(
    tenant_a, pc_partner_a, pc_customer_a
):
    """Verify split_percentage validator enforces 0-100 range."""
    conflict = ChannelConflict(
        tenant=tenant_a,
        claimant_partner=pc_partner_a,
        client_account=pc_customer_a,
        split_percentage=Decimal("-5.00"),
    )
    with pytest.raises(ValidationError) as exc:
        conflict.full_clean()
    assert "split_percentage" in exc.value.message_dict

    conflict.split_percentage = Decimal("105.00")
    with pytest.raises(ValidationError) as exc:
        conflict.full_clean()
    assert "split_percentage" in exc.value.message_dict

    conflict.split_percentage = Decimal("50.00")
    conflict.full_clean()


def test_partnerchannel_models_channel_conflict_unique_number(
    pc_conflict_a, tenant_a, pc_partner_a, pc_customer_a
):
    """Verify unique constraint on (tenant, number)."""
    dup = ChannelConflict(
        tenant=tenant_a,
        claimant_partner=pc_partner_a,
        client_account=pc_customer_a,
        number=pc_conflict_a.number,
    )
    with pytest.raises(IntegrityError):
        dup.save()


# ==============================================================================
# 6. Tenant Sequence Isolation
# ==============================================================================

def test_partnerchannel_models_tenant_numbering_sequence_isolated(
    pc_profile_a, pc_profile_b,
    pc_deal_reg_a, pc_deal_reg_b,
    pc_joint_plan_a, pc_joint_plan_b,
    pc_conflict_a, pc_conflict_b,
):
    """Verify tenant_a and tenant_b have independent numbering sequences starting at 00001."""
    assert pc_profile_a.number == "PTR-00001"
    assert pc_profile_b.number == "PTR-00001"

    assert pc_deal_reg_a.number == "DLR-00001"
    assert pc_deal_reg_b.number == "DLR-00001"

    assert pc_joint_plan_a.number == "JAP-00001"
    assert pc_joint_plan_b.number == "JAP-00001"

    assert pc_conflict_a.number == "CCF-00001"
    assert pc_conflict_b.number == "CCF-00001"
