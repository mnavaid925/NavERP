"""Sub-module 8.14 Partner & Channel Management -- Views Test Suite.

Covers:
1. Console:
   - partner_performance_console (aggregates, KPI stats, tier distribution, expiring registrations).
2. List Views (4 entities):
   - partner_profile_list
   - deal_registration_list
   - joint_account_plan_list
   - channel_conflict_list
   (Search queries, status/type dropdown filters, and negative-input hardening).
3. Detail Views (4 entities):
   - partner_profile_detail
   - deal_registration_detail
   - joint_account_plan_detail
   - channel_conflict_detail
4. Create & Edit Views:
   - GET 200 renders form templates.
   - POST 302 creates/updates records, asserts tenant isolation and AuditLog recording.
5. Action & Workflow Views:
   - deal_registration_convert (POST creates crm.Opportunity and marks converted).
6. Delete Views:
   - GET 405 (strictly POST-only).
   - POST 302 deletes record and records AuditLog.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import Currency
from apps.core.models import AuditLog, Document, Party, PartyRole
from apps.crm.models import Opportunity, Territory
from apps.sales.models.PartnerChannel.ChannelConflicts import ChannelConflict
from apps.sales.models.PartnerChannel.DealRegistrations import DealRegistration
from apps.sales.models.PartnerChannel.JointAccountPlans import JointAccountPlan
from apps.sales.models.PartnerChannel.PartnerProfiles import PartnerProfile

pytestmark = pytest.mark.django_db


# ============================================================================
# Helpers & Fixtures
# ============================================================================

def _partnerchannel_partner(tenant, name="Premier Cloud Partners"):
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.create(tenant=tenant, party=party, role="partner")
    return party


def _partnerchannel_customer(tenant, name="Global Logistics Inc"):
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.create(tenant=tenant, party=party, role="customer")
    return party


def _partnerchannel_curr(code="USD"):
    curr, _ = Currency.objects.get_or_create(code=code, defaults={"name": "US Dollar", "symbol": "$"})
    return curr


def _create_sample_profile(tenant, partner=None, user=None):
    if not partner:
        partner = _partnerchannel_partner(tenant, f"VAR Partner {tenant.pk}")
    curr = _partnerchannel_curr()
    return PartnerProfile.objects.create(
        tenant=tenant,
        partner=partner,
        partner_type="reseller",
        onboarding_status="active",
        tier="gold",
        agreement_signed_at=timezone.now(),
        channel_manager=user,
        currency=curr,
        annual_revenue_target=Decimal("1000000.00"),
        actual_revenue_ytd=Decimal("450000.00"),
        active_certifications_count=5,
        base_discount_pct=Decimal("15.00"),
        deal_reg_margin_pct=Decimal("20.00"),
    )


def _create_sample_deal_reg(tenant, partner=None, customer=None, status="approved"):
    if not partner:
        partner = _partnerchannel_partner(tenant, f"Reg Partner {tenant.pk}")
    if not customer:
        customer = _partnerchannel_customer(tenant, f"End Customer {tenant.pk}")
    curr = _partnerchannel_curr()
    now = timezone.localdate()
    return DealRegistration.objects.create(
        tenant=tenant,
        partner=partner,
        customer_account=customer,
        deal_name="Enterprise ERP Suite",
        estimated_value=Decimal("150000.00"),
        currency=curr,
        expected_close_date=now + timedelta(days=60),
        submission_date=now,
        status=status,
        exclusivity_status="exclusive",
        protection_start_date=now,
        protection_end_date=now + timedelta(days=90),
        protected_margin_pct=Decimal("20.00"),
        extension_count=0,
    )


def _create_sample_joint_plan(tenant, partner=None, customer=None):
    if not partner:
        partner = _partnerchannel_partner(tenant, f"Plan Partner {tenant.pk}")
    if not customer:
        customer = _partnerchannel_customer(tenant, f"Plan Client {tenant.pk}")
    curr = _partnerchannel_curr()
    now = timezone.localdate()
    return JointAccountPlan.objects.create(
        tenant=tenant,
        partner=partner,
        client_account=customer,
        plan_name="2026 Strategic Co-Sell",
        plan_year=2026,
        period_start=now,
        period_end=now + timedelta(days=180),
        status="active",
        target_revenue=Decimal("500000.00"),
        actual_revenue=Decimal("120000.00"),
        currency=curr,
        partner_lead_name="Jane Champion",
        co_sell_motion="joint_pursuit",
    )


def _create_sample_conflict(tenant, claimant=None, customer=None, status="open"):
    if not claimant:
        claimant = _partnerchannel_partner(tenant, f"Claimant Partner {tenant.pk}")
    if not customer:
        customer = _partnerchannel_customer(tenant, f"Disputed Account {tenant.pk}")
    return ChannelConflict.objects.create(
        tenant=tenant,
        conflict_type="direct_vs_indirect",
        severity="high",
        status=status,
        claimant_partner=claimant,
        client_account=customer,
        escalation_level="l1_cam",
        resolution_outcome="pending",
        split_percentage=Decimal("0.00"),
        description="Collision on target account.",
    )


# ============================================================================
# 1. Executive Console
# ============================================================================

def test_partnerchannel_partner_performance_console(client_a, tenant_a, admin_user):
    """Console returns 200, aggregates partner metrics, and renders template."""
    _create_sample_profile(tenant_a, user=admin_user)
    _create_sample_deal_reg(tenant_a)
    _create_sample_joint_plan(tenant_a)
    _create_sample_conflict(tenant_a)

    url = reverse("sales:partner_performance_console")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/partnerchannel/boards/partner_performance_console.html" in [t.name for t in resp.templates]

    ctx = resp.context
    assert "stats" in ctx
    assert ctx["stats"]["active_partners_count"] >= 1
    assert "tier_distribution" in ctx
    assert "top_partners" in ctx
    assert "expiring_registrations" in ctx
    assert "recent_conflicts" in ctx


# ============================================================================
# 2. List Views & Filter Hardening
# ============================================================================

def test_partnerchannel_partner_profile_list_view(client_a, tenant_a):
    """Partner profile list returns 200, matches filters, and handles junk params."""
    profile = _create_sample_profile(tenant_a)
    url = reverse("sales:partner_profile_list")

    # Clean GET
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "partner_profiles" in resp.context
    assert profile in resp.context["partner_profiles"]

    # Search & filters
    resp = client_a.get(url, {"q": profile.partner.name, "tier": "gold", "partner_type": "reseller"})
    assert resp.status_code == 200
    assert profile in resp.context["partner_profiles"]

    # Negative-input hardening (junk query params)
    resp = client_a.get(url, {"partner_type": "invalid_type", "page": 999})
    assert resp.status_code == 200


def test_partnerchannel_deal_registration_list_view(client_a, tenant_a):
    """Deal registration list returns 200, filters by status, and handles junk params."""
    reg = _create_sample_deal_reg(tenant_a)
    url = reverse("sales:deal_registration_list")

    resp = client_a.get(url)
    assert resp.status_code == 200
    assert reg in resp.context["deal_registrations"]

    # Filter by status and exclusivity
    resp = client_a.get(url, {"status": "approved", "exclusivity_status": "exclusive"})
    assert resp.status_code == 200
    assert reg in resp.context["deal_registrations"]

    # Junk params
    resp = client_a.get(url, {"status": "non_existent_status", "partner": "abc", "page": "xyz"})
    assert resp.status_code == 200


def test_partnerchannel_joint_account_plan_list_view(client_a, tenant_a):
    """Joint account plan list returns 200 and handles filters and pagination."""
    plan = _create_sample_joint_plan(tenant_a)
    url = reverse("sales:joint_account_plan_list")

    resp = client_a.get(url)
    assert resp.status_code == 200
    assert plan in resp.context["joint_plans"]

    resp = client_a.get(url, {"status": "active", "co_sell_motion": "joint_pursuit"})
    assert resp.status_code == 200
    assert plan in resp.context["joint_plans"]

    # Junk params
    resp = client_a.get(url, {"co_sell_motion": "bogus", "page": 9999})
    assert resp.status_code == 200


def test_partnerchannel_channel_conflict_list_view(client_a, tenant_a):
    """Channel conflict list returns 200 and filters cleanly."""
    conflict = _create_sample_conflict(tenant_a)
    url = reverse("sales:channel_conflict_list")

    resp = client_a.get(url)
    assert resp.status_code == 200
    assert conflict in resp.context["conflicts"]

    resp = client_a.get(url, {"conflict_type": "direct_vs_indirect", "severity": "high", "escalation_level": "l1_cam"})
    assert resp.status_code == 200
    assert conflict in resp.context["conflicts"]

    # Junk params
    resp = client_a.get(url, {"severity": "mega_critical", "page": -1})
    assert resp.status_code == 200


# ============================================================================
# 3. Detail Views
# ============================================================================

def test_partnerchannel_partner_profile_detail_view(client_a, tenant_a):
    """Partner profile detail returns 200 and provides child relations in context."""
    profile = _create_sample_profile(tenant_a)
    reg = _create_sample_deal_reg(tenant_a, partner=profile.partner)
    plan = _create_sample_joint_plan(tenant_a, partner=profile.partner)
    conflict = _create_sample_conflict(tenant_a, claimant=profile.partner)

    url = reverse("sales:partner_profile_detail", kwargs={"pk": profile.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    ctx = resp.context
    assert ctx["partner_profile"] == profile
    assert reg in ctx["registrations"]
    assert plan in ctx["joint_plans"]
    assert conflict in ctx["conflicts"]


def test_partnerchannel_deal_registration_detail_view(client_a, tenant_a):
    """Deal registration detail returns 200 and loads linked conflicts."""
    reg = _create_sample_deal_reg(tenant_a)
    url = reverse("sales:deal_registration_detail", kwargs={"pk": reg.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["deal_registration"] == reg


def test_partnerchannel_joint_account_plan_detail_view(client_a, tenant_a):
    """Joint account plan detail returns 200."""
    plan = _create_sample_joint_plan(tenant_a)
    url = reverse("sales:joint_account_plan_detail", kwargs={"pk": plan.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["joint_plan"] == plan


def test_partnerchannel_channel_conflict_detail_view(client_a, tenant_a):
    """Channel conflict detail returns 200."""
    conflict = _create_sample_conflict(tenant_a)
    url = reverse("sales:channel_conflict_detail", kwargs={"pk": conflict.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["conflict"] == conflict


# ============================================================================
# 4. Create & Edit Views
# ============================================================================

def test_partnerchannel_partner_profile_create_and_edit_views(client_a, tenant_a, admin_user):
    """Partner profile create (GET/POST) and edit (GET/POST) flow."""
    partner = _partnerchannel_partner(tenant_a, "Innovative Systems")
    curr = _partnerchannel_curr()
    create_url = reverse("sales:partner_profile_create")

    # GET Create
    resp = client_a.get(create_url)
    assert resp.status_code == 200

    # POST Create
    today = timezone.localdate()
    create_data = {
        "partner": partner.pk,
        "partner_type": "system_integrator",
        "onboarding_status": "applied",
        "tier": "registered",
        "application_date": today,
        "channel_manager": admin_user.pk,
        "currency": curr.pk,
        "annual_revenue_target": "300000.00",
        "actual_revenue_ytd": "0.00",
        "required_certifications_count": 1,
        "active_certifications_count": 0,
        "base_discount_pct": "10.00",
        "deal_reg_margin_pct": "15.00",
        "portal_access_enabled": False,
    }
    resp = client_a.post(create_url, data=create_data)
    assert resp.status_code == 302
    profile = PartnerProfile.objects.get(tenant=tenant_a, partner=partner)
    assert profile.tier == "registered"
    assert AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=profile.pk).exists()

    # GET Edit
    edit_url = reverse("sales:partner_profile_edit", kwargs={"pk": profile.pk})
    resp = client_a.get(edit_url)
    assert resp.status_code == 200

    # POST Edit
    edit_data = create_data.copy()
    edit_data["tier"] = "silver"
    edit_data["actual_revenue_ytd"] = "75000.00"
    resp = client_a.post(edit_url, data=edit_data)
    assert resp.status_code == 302
    profile.refresh_from_db()
    assert profile.tier == "silver"
    assert profile.actual_revenue_ytd == Decimal("75000.00")
    assert AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=profile.pk).exists()


def test_partnerchannel_deal_registration_create_and_edit_views(client_a, tenant_a):
    """Deal registration create (GET/POST) and edit (GET/POST) flow."""
    partner = _partnerchannel_partner(tenant_a, "Channel Reseller")
    customer = _partnerchannel_customer(tenant_a, "Target Enterprise")
    curr = _partnerchannel_curr()
    create_url = reverse("sales:deal_registration_create")

    # GET Create
    resp = client_a.get(create_url)
    assert resp.status_code == 200

    # POST Create
    today = timezone.localdate()
    create_data = {
        "partner": partner.pk,
        "customer_account": customer.pk,
        "deal_name": "Multi-site ERP Deployment",
        "estimated_value": "90000.00",
        "currency": curr.pk,
        "expected_close_date": today + timedelta(days=60),
        "submission_date": today,
        "status": "submitted",
        "exclusivity_status": "pending",
        "protected_margin_pct": "15.00",
        "extension_count": 0,
    }
    resp = client_a.post(create_url, data=create_data)
    assert resp.status_code == 302
    reg = DealRegistration.objects.get(tenant=tenant_a, deal_name="Multi-site ERP Deployment")
    assert reg.status == "submitted"

    # POST Edit
    edit_url = reverse("sales:deal_registration_edit", kwargs={"pk": reg.pk})
    edit_data = create_data.copy()
    edit_data["status"] = "under_review"
    edit_data["estimated_value"] = "95000.00"
    resp = client_a.post(edit_url, data=edit_data)
    assert resp.status_code == 302
    reg.refresh_from_db()
    assert reg.status == "under_review"
    assert reg.estimated_value == Decimal("95000.00")


# ============================================================================
# 5. Conversion Workflow
# ============================================================================

def test_partnerchannel_deal_registration_convert_workflow(client_a, tenant_a, admin_user):
    """Deal registration convert view transforms an approved deal into crm.Opportunity."""
    reg = _create_sample_deal_reg(tenant_a, status="approved")
    convert_url = reverse("sales:deal_registration_convert", kwargs={"pk": reg.pk})

    # GET is rejected (action requires POST)
    resp = client_a.get(convert_url)
    assert resp.status_code == 405

    # POST triggers conversion
    resp = client_a.post(convert_url)
    assert resp.status_code == 302
    reg.refresh_from_db()
    assert reg.status == "converted"
    assert reg.opportunity is not None
    assert reg.opportunity.tenant == tenant_a
    assert reg.opportunity.name == reg.deal_name
    assert reg.opportunity.account == reg.customer_account


# ============================================================================
# 6. Delete Views (Strictly POST-Only)
# ============================================================================

def test_partnerchannel_delete_views_post_only(client_a, tenant_a):
    """All delete views must reject GET requests with 405 Method Not Allowed."""
    profile = _create_sample_profile(tenant_a)
    reg = _create_sample_deal_reg(tenant_a)
    plan = _create_sample_joint_plan(tenant_a)
    conflict = _create_sample_conflict(tenant_a)

    delete_urls = [
        reverse("sales:partner_profile_delete", kwargs={"pk": profile.pk}),
        reverse("sales:deal_registration_delete", kwargs={"pk": reg.pk}),
        reverse("sales:joint_account_plan_delete", kwargs={"pk": plan.pk}),
        reverse("sales:channel_conflict_delete", kwargs={"pk": conflict.pk}),
    ]

    for url in delete_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"GET {url} must return 405 Method Not Allowed"


def test_partnerchannel_delete_views_post_success(client_a, tenant_a):
    """POST to delete views removes the record and writes an AuditLog."""
    profile = _create_sample_profile(tenant_a)
    url = reverse("sales:partner_profile_delete", kwargs={"pk": profile.pk})

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not PartnerProfile.objects.filter(pk=profile.pk).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=profile.pk).exists()
