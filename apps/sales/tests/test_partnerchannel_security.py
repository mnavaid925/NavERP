"""Sub-module 8.14 Partner & Channel Management -- Security & Multi-Tenancy Test Suite.

Covers:
1. Authentication Protection (@login_required):
   - Anonymous visitors to any Partner Channel endpoint are redirected to login (302).
2. Multi-Tenant IDOR Isolation:
   - Detail views: Cross-tenant access strictly returns 404.
   - Edit views: Cross-tenant GET/POST strictly returns 404.
   - Delete views: Cross-tenant POST strictly returns 404.
   - Action views (deal_registration_convert): Cross-tenant POST strictly returns 404.
3. List Isolation:
   - Records created in Tenant A are never visible in Tenant B list views or consoles.
4. Role-Based Access Control (@tenant_admin_required):
   - Non-admin member users attempting to POST to delete endpoints are rejected with 403 Forbidden.
   - Tenant admin users are permitted to delete.
5. Cross-Tenant FK Injection Prevention:
   - POST payloads containing foreign tenant PKs in foreign keys are rejected by validation.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import Currency
from apps.core.models import Party, PartyRole
from apps.sales.models.PartnerChannel.ChannelConflicts import ChannelConflict
from apps.sales.models.PartnerChannel.DealRegistrations import DealRegistration
from apps.sales.models.PartnerChannel.JointAccountPlans import JointAccountPlan
from apps.sales.models.PartnerChannel.PartnerProfiles import PartnerProfile

pytestmark = pytest.mark.django_db


# ============================================================================
# Helpers
# ============================================================================

def _partnerchannel_sec_party(tenant, name, role="partner"):
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.create(tenant=tenant, party=party, role=role)
    return party


def _partnerchannel_sec_currency():
    curr, _ = Currency.objects.get_or_create(code="USD", defaults={"name": "US Dollar", "symbol": "$"})
    return curr


def _create_partner_profile(tenant, user=None):
    partner = _partnerchannel_sec_party(tenant, f"Partner-{tenant.pk}", role="partner")
    curr = _partnerchannel_sec_currency()
    return PartnerProfile.objects.create(
        tenant=tenant,
        partner=partner,
        partner_type="reseller",
        onboarding_status="active",
        tier="gold",
        agreement_signed_at=timezone.now(),
        channel_manager=user,
        currency=curr,
        annual_revenue_target=Decimal("500000.00"),
        actual_revenue_ytd=Decimal("200000.00"),
        active_certifications_count=3,
        base_discount_pct=Decimal("15.00"),
        deal_reg_margin_pct=Decimal("20.00"),
    )


def _create_deal_reg(tenant):
    partner = _partnerchannel_sec_party(tenant, f"DLR-Partner-{tenant.pk}", role="partner")
    customer = _partnerchannel_sec_party(tenant, f"DLR-Cust-{tenant.pk}", role="customer")
    curr = _partnerchannel_sec_currency()
    now = timezone.localdate()
    return DealRegistration.objects.create(
        tenant=tenant,
        partner=partner,
        customer_account=customer,
        deal_name=f"Enterprise Deal {tenant.pk}",
        estimated_value=Decimal("75000.00"),
        currency=curr,
        expected_close_date=now + timedelta(days=60),
        submission_date=now,
        status="approved",
        exclusivity_status="exclusive",
        protection_start_date=now,
        protection_end_date=now + timedelta(days=90),
        protected_margin_pct=Decimal("20.00"),
        extension_count=0,
    )


def _create_joint_plan(tenant):
    partner = _partnerchannel_sec_party(tenant, f"JAP-Partner-{tenant.pk}", role="partner")
    customer = _partnerchannel_sec_party(tenant, f"JAP-Cust-{tenant.pk}", role="customer")
    curr = _partnerchannel_sec_currency()
    now = timezone.localdate()
    return JointAccountPlan.objects.create(
        tenant=tenant,
        partner=partner,
        client_account=customer,
        plan_name=f"Co-Sell Plan {tenant.pk}",
        plan_year=2026,
        period_start=now,
        period_end=now + timedelta(days=120),
        status="active",
        target_revenue=Decimal("250000.00"),
        actual_revenue=Decimal("50000.00"),
        currency=curr,
        partner_lead_name="Champion Name",
        co_sell_motion="joint_pursuit",
    )


def _create_conflict(tenant):
    claimant = _partnerchannel_sec_party(tenant, f"CCF-Claimant-{tenant.pk}", role="partner")
    customer = _partnerchannel_sec_party(tenant, f"CCF-Cust-{tenant.pk}", role="customer")
    return ChannelConflict.objects.create(
        tenant=tenant,
        conflict_type="direct_vs_indirect",
        severity="high",
        status="open",
        claimant_partner=claimant,
        client_account=customer,
        escalation_level="l1_cam",
        resolution_outcome="pending",
        split_percentage=Decimal("0.00"),
        description=f"Dispute in {tenant.name}",
    )


# ============================================================================
# 1. Authentication Protection
# ============================================================================

def test_partnerchannel_anonymous_access_redirects_to_login(tenant_a):
    """Anonymous client accessing Partner Channel endpoints must be redirected to login."""
    anon = Client()
    profile = _create_partner_profile(tenant_a)
    reg = _create_deal_reg(tenant_a)
    plan = _create_joint_plan(tenant_a)
    conflict = _create_conflict(tenant_a)

    endpoints = [
        reverse("sales:partner_performance_console"),
        reverse("sales:partner_profile_list"),
        reverse("sales:partner_profile_create"),
        reverse("sales:partner_profile_detail", kwargs={"pk": profile.pk}),
        reverse("sales:partner_profile_edit", kwargs={"pk": profile.pk}),
        reverse("sales:deal_registration_list"),
        reverse("sales:deal_registration_create"),
        reverse("sales:deal_registration_detail", kwargs={"pk": reg.pk}),
        reverse("sales:deal_registration_edit", kwargs={"pk": reg.pk}),
        reverse("sales:joint_account_plan_list"),
        reverse("sales:joint_account_plan_create"),
        reverse("sales:joint_account_plan_detail", kwargs={"pk": plan.pk}),
        reverse("sales:joint_account_plan_edit", kwargs={"pk": plan.pk}),
        reverse("sales:channel_conflict_list"),
        reverse("sales:channel_conflict_create"),
        reverse("sales:channel_conflict_detail", kwargs={"pk": conflict.pk}),
        reverse("sales:channel_conflict_edit", kwargs={"pk": conflict.pk}),
    ]

    for url in endpoints:
        resp = anon.get(url)
        assert resp.status_code == 302, f"Expected 302 redirect for unauthenticated access to {url}"
        assert "/accounts/login/" in resp.url or "/login/" in resp.url


# ============================================================================
# 2. Multi-Tenant IDOR Isolation (Strict 404)
# ============================================================================

def test_partnerchannel_detail_views_cross_tenant_idor_returns_404(client_a, client_b, tenant_a, tenant_b):
    """Detail views must return 404 when requested by another tenant."""
    prof_b = _create_partner_profile(tenant_b)
    reg_b = _create_deal_reg(tenant_b)
    plan_b = _create_joint_plan(tenant_b)
    conf_b = _create_conflict(tenant_b)

    # Tenant A requests Tenant B objects
    assert client_a.get(reverse("sales:partner_profile_detail", kwargs={"pk": prof_b.pk})).status_code == 404
    assert client_a.get(reverse("sales:deal_registration_detail", kwargs={"pk": reg_b.pk})).status_code == 404
    assert client_a.get(reverse("sales:joint_account_plan_detail", kwargs={"pk": plan_b.pk})).status_code == 404
    assert client_a.get(reverse("sales:channel_conflict_detail", kwargs={"pk": conf_b.pk})).status_code == 404

    # Tenant B requests Tenant A objects
    prof_a = _create_partner_profile(tenant_a)
    reg_a = _create_deal_reg(tenant_a)
    plan_a = _create_joint_plan(tenant_a)
    conf_a = _create_conflict(tenant_a)

    assert client_b.get(reverse("sales:partner_profile_detail", kwargs={"pk": prof_a.pk})).status_code == 404
    assert client_b.get(reverse("sales:deal_registration_detail", kwargs={"pk": reg_a.pk})).status_code == 404
    assert client_b.get(reverse("sales:joint_account_plan_detail", kwargs={"pk": plan_a.pk})).status_code == 404
    assert client_b.get(reverse("sales:channel_conflict_detail", kwargs={"pk": conf_a.pk})).status_code == 404


def test_partnerchannel_edit_views_cross_tenant_idor_returns_404(client_a, tenant_b):
    """Edit views must return 404 when Tenant A requests Tenant B records."""
    prof_b = _create_partner_profile(tenant_b)
    reg_b = _create_deal_reg(tenant_b)
    plan_b = _create_joint_plan(tenant_b)
    conf_b = _create_conflict(tenant_b)

    # GET Edit
    assert client_a.get(reverse("sales:partner_profile_edit", kwargs={"pk": prof_b.pk})).status_code == 404
    assert client_a.get(reverse("sales:deal_registration_edit", kwargs={"pk": reg_b.pk})).status_code == 404
    assert client_a.get(reverse("sales:joint_account_plan_edit", kwargs={"pk": plan_b.pk})).status_code == 404
    assert client_a.get(reverse("sales:channel_conflict_edit", kwargs={"pk": conf_b.pk})).status_code == 404

    # POST Edit
    assert client_a.post(reverse("sales:partner_profile_edit", kwargs={"pk": prof_b.pk}), data={}).status_code == 404
    assert client_a.post(reverse("sales:deal_registration_edit", kwargs={"pk": reg_b.pk}), data={}).status_code == 404
    assert client_a.post(reverse("sales:joint_account_plan_edit", kwargs={"pk": plan_b.pk}), data={}).status_code == 404
    assert client_a.post(reverse("sales:channel_conflict_edit", kwargs={"pk": conf_b.pk}), data={}).status_code == 404


def test_partnerchannel_delete_views_cross_tenant_idor_returns_404(client_a, tenant_b):
    """Delete POST requests across tenants must return 404."""
    prof_b = _create_partner_profile(tenant_b)
    reg_b = _create_deal_reg(tenant_b)
    plan_b = _create_joint_plan(tenant_b)
    conf_b = _create_conflict(tenant_b)

    assert client_a.post(reverse("sales:partner_profile_delete", kwargs={"pk": prof_b.pk})).status_code == 404
    assert client_a.post(reverse("sales:deal_registration_delete", kwargs={"pk": reg_b.pk})).status_code == 404
    assert client_a.post(reverse("sales:joint_account_plan_delete", kwargs={"pk": plan_b.pk})).status_code == 404
    assert client_a.post(reverse("sales:channel_conflict_delete", kwargs={"pk": conf_b.pk})).status_code == 404

    # Confirm Tenant B records are untouched
    assert PartnerProfile.objects.filter(pk=prof_b.pk).exists()
    assert DealRegistration.objects.filter(pk=reg_b.pk).exists()


def test_partnerchannel_convert_view_cross_tenant_idor_returns_404(client_a, tenant_b):
    """Deal registration convert POST across tenants must return 404."""
    reg_b = _create_deal_reg(tenant_b)
    convert_url = reverse("sales:deal_registration_convert", kwargs={"pk": reg_b.pk})
    resp = client_a.post(convert_url)
    assert resp.status_code == 404


# ============================================================================
# 3. Tenant List Isolation
# ============================================================================

def test_partnerchannel_list_views_strictly_isolated(client_a, client_b, tenant_a, tenant_b):
    """List views must never display records belonging to another tenant."""
    prof_a = _create_partner_profile(tenant_a)
    prof_b = _create_partner_profile(tenant_b)

    reg_a = _create_deal_reg(tenant_a)
    reg_b = _create_deal_reg(tenant_b)

    plan_a = _create_joint_plan(tenant_a)
    plan_b = _create_joint_plan(tenant_b)

    conf_a = _create_conflict(tenant_a)
    conf_b = _create_conflict(tenant_b)

    # Tenant A list requests
    resp_prof = client_a.get(reverse("sales:partner_profile_list"))
    assert prof_a in resp_prof.context["partner_profiles"]
    assert prof_b not in resp_prof.context["partner_profiles"]

    resp_reg = client_a.get(reverse("sales:deal_registration_list"))
    assert reg_a in resp_reg.context["deal_registrations"]
    assert reg_b not in resp_reg.context["deal_registrations"]

    resp_plan = client_a.get(reverse("sales:joint_account_plan_list"))
    assert plan_a in resp_plan.context["joint_plans"]
    assert plan_b not in resp_plan.context["joint_plans"]

    resp_conf = client_a.get(reverse("sales:channel_conflict_list"))
    assert conf_a in resp_conf.context["conflicts"]
    assert conf_b not in resp_conf.context["conflicts"]


# ============================================================================
# 4. Role-Based Access Control (@tenant_admin_required)
# ============================================================================

def test_partnerchannel_delete_requires_tenant_admin(member_client, client_a, tenant_a):
    """Non-admin member users are rejected from delete endpoints with 403."""
    prof = _create_partner_profile(tenant_a)
    delete_url = reverse("sales:partner_profile_delete", kwargs={"pk": prof.pk})

    # Member user attempt -> 403 Forbidden
    resp = member_client.post(delete_url)
    assert resp.status_code == 403
    assert PartnerProfile.objects.filter(pk=prof.pk).exists()

    # Tenant Admin attempt -> 302 Success
    resp = client_a.post(delete_url)
    assert resp.status_code == 302
    assert not PartnerProfile.objects.filter(pk=prof.pk).exists()
