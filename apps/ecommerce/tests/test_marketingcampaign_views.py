"""Comprehensive view, route, filter, and CRUD tests for eCommerce 9.10 Marketing & Campaign Management.

Covers:
- Marketing Dashboard & Social Commerce Feed
- MarketingCampaign CRUD + Send Action
- AffiliatePartner CRUD + Approve Action
- AffiliateReferralConversion CRUD + Approve & Void Actions
- SeoMetadataRule CRUD + Toggle Action

Naming conventions enforced:
- Test functions: test_marketingcampaign_*
- Module-level helpers: _marketingcampaign_*
"""
from decimal import Decimal
import json
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Party
from apps.ecommerce.models import (
    MarketingCampaign,
    AffiliatePartner,
    AffiliateReferralConversion,
    SeoMetadataRule,
    StoreCategory,
    CatalogProduct,
    AudienceSegment,
)
from apps.ecommerce.tests.conftest import (
    _marketing_campaign,
    _affiliate_partner,
    _affiliate_conversion,
    _seo_rule,
    _ordermanagement_order,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Dashboard & Syndication Feed Views
# ==============================================================================

def test_marketingcampaign_dashboard_view(client_a, tenant_a, ecom_campaign_a, ecom_affiliate_a):
    url = reverse("ecommerce:marketing_dashboard")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "kpis" in resp.context
    kpis = resp.context["kpis"]
    assert kpis["total_campaigns"] >= 1
    assert kpis["total_affiliates"] >= 1
    assert "recent_campaigns" in resp.context
    assert "top_affiliates" in resp.context
    assert resp.context["active_tab"] == "overview"

    # Tab switching
    resp_tab = client_a.get(url, {"tab": "campaigns"})
    assert resp_tab.status_code == 200
    assert resp_tab.context["active_tab"] == "campaigns"


def test_marketingcampaign_social_commerce_feed_view(client_a, tenant_a):
    cat = StoreCategory.objects.create(tenant=tenant_a, name="Catalog Category", slug="catalog-cat")
    prod = CatalogProduct.objects.create(
        tenant=tenant_a,
        name="Feed Product",
        slug="feed-prod",
        primary_category=cat,
        status="active",
        brand="AcmeBrand",
    )
    url = reverse("ecommerce:social_commerce_feed")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/json"
    data = json.loads(resp.content)
    assert "channel" in data
    assert "items" in data
    assert data["tenant_id"] == tenant_a.pk
    item_titles = [i["title"] for i in data["items"]]
    assert prod.name in item_titles


# ==============================================================================
# MarketingCampaign Views
# ==============================================================================

def test_marketingcampaign_list_view(client_a, tenant_a, ecom_campaign_a):
    _marketing_campaign(tenant_a, name="SMS Flash", channel="sms", status="draft")
    url = reverse("ecommerce:marketingcampaign_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "campaigns" in resp.context
    assert "channel_choices" in resp.context
    assert "status_choices" in resp.context
    assert len(resp.context["campaigns"]) >= 2

    # Filter by channel
    resp_sms = client_a.get(url, {"channel": "sms"})
    assert resp_sms.status_code == 200
    assert any(c.channel == "sms" for c in resp_sms.context["campaigns"])

    # Search filter
    resp_search = client_a.get(url, {"q": "SMS Flash"})
    assert resp_search.status_code == 200
    assert len(resp_search.context["campaigns"]) == 1


def test_marketingcampaign_create_view(client_a, tenant_a):
    url = reverse("ecommerce:marketingcampaign_create")
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context

    post_data = {
        "name": "New Year Campaign",
        "code": "NY-2027",
        "campaign_type": "newsletter_broadcast",
        "channel": "email",
        "subject": "Happy New Year",
        "content_body": "<p>Wishing you the best</p>",
        "sender_name": "Acme Team",
        "sender_address": "team@acme.com",
        "send_throttle_window_hours": 16,
    }
    resp_post = client_a.post(url, post_data)
    if resp_post.status_code == 200 and "form" in resp_post.context:
        assert not resp_post.context["form"].errors, f"Form errors: {resp_post.context['form'].errors}"
    assert resp_post.status_code == 302
    created = MarketingCampaign.objects.filter(tenant=tenant_a, code="NY-2027").first()
    assert created is not None
    assert created.status == "draft"


def test_marketingcampaign_detail_and_edit_view(client_a, tenant_a, ecom_campaign_a):
    detail_url = reverse("ecommerce:marketingcampaign_detail", args=[ecom_campaign_a.pk])
    resp_detail = client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert resp_detail.context["campaign"].pk == ecom_campaign_a.pk

    edit_url = reverse("ecommerce:marketingcampaign_edit", args=[ecom_campaign_a.pk])
    resp_edit_get = client_a.get(edit_url)
    assert resp_edit_get.status_code == 200

    resp_edit_post = client_a.post(edit_url, {
        "name": "Updated Campaign Name",
        "code": ecom_campaign_a.code,
        "campaign_type": ecom_campaign_a.campaign_type,
        "channel": ecom_campaign_a.channel,
        "subject": "Updated Subject",
        "content_body": "Updated content body",
        "sender_name": ecom_campaign_a.sender_name,
        "sender_address": ecom_campaign_a.sender_address,
        "send_throttle_window_hours": 16,
    })
    assert resp_edit_post.status_code == 302
    ecom_campaign_a.refresh_from_db()
    assert ecom_campaign_a.name == "Updated Campaign Name"


def test_marketingcampaign_send_action(client_a, tenant_a, ecom_campaign_a):
    segment = AudienceSegment.objects.create(tenant=tenant_a, name="Segment 100", cached_member_count=100)
    ecom_campaign_a.target_segment = segment
    ecom_campaign_a.status = "draft"
    ecom_campaign_a.save()

    send_url = reverse("ecommerce:marketingcampaign_send", args=[ecom_campaign_a.pk])
    resp = client_a.post(send_url)
    assert resp.status_code == 302
    ecom_campaign_a.refresh_from_db()
    assert ecom_campaign_a.status == "sent"
    assert ecom_campaign_a.sent_at is not None
    assert ecom_campaign_a.recipient_count == 100
    assert ecom_campaign_a.delivered_count == 98
    assert ecom_campaign_a.bounced_count == 2


def test_marketingcampaign_delete_view(client_a, tenant_a, ecom_campaign_a):
    delete_url = reverse("ecommerce:marketingcampaign_delete", args=[ecom_campaign_a.pk])
    resp = client_a.post(delete_url)
    assert resp.status_code == 302
    assert not MarketingCampaign.objects.filter(pk=ecom_campaign_a.pk).exists()


# ==============================================================================
# AffiliatePartner Views
# ==============================================================================

def test_affiliatepartner_list_view(client_a, tenant_a, ecom_affiliate_a):
    _affiliate_partner(tenant_a, name="Top Blogger", partner_type="influencer", status="active")
    url = reverse("ecommerce:affiliatepartner_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "partners" in resp.context
    assert "partner_type_choices" in resp.context
    assert "status_choices" in resp.context
    assert len(resp.context["partners"]) >= 2

    # Filter by type
    resp_filtered = client_a.get(url, {"partner_type": "influencer"})
    assert resp_filtered.status_code == 200
    assert all(p.partner_type == "influencer" for p in resp_filtered.context["partners"])


def test_affiliatepartner_create_and_approve_view(client_a, tenant_a):
    party = Party.objects.create(tenant=tenant_a, name="New Partner Org", kind="organization")
    create_url = reverse("ecommerce:affiliatepartner_create")
    resp = client_a.post(create_url, {
        "name": "Affiliate Org",
        "party": party.pk,
        "partner_type": "affiliate",
        "referral_code": "ORG10",
        "referral_link_slug": "org10",
        "commission_type": "percentage_net_sales",
        "commission_rate": "10.00",
        "cookie_duration_days": 30,
        "payout_threshold": "50.00",
        "payment_email": "pay@org.com",
    })
    assert resp.status_code == 302
    partner = AffiliatePartner.objects.filter(tenant=tenant_a, referral_code="ORG10").first()
    assert partner is not None
    assert partner.status == "pending_approval"

    # Approve partner
    approve_url = reverse("ecommerce:affiliatepartner_approve", args=[partner.pk])
    resp_app = client_a.post(approve_url)
    assert resp_app.status_code == 302
    partner.refresh_from_db()
    assert partner.status == "active"


def test_affiliatepartner_detail_and_delete_view(client_a, tenant_a, ecom_affiliate_a):
    detail_url = reverse("ecommerce:affiliatepartner_detail", args=[ecom_affiliate_a.pk])
    resp_detail = client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert resp_detail.context["partner"].pk == ecom_affiliate_a.pk

    delete_url = reverse("ecommerce:affiliatepartner_delete", args=[ecom_affiliate_a.pk])
    resp_del = client_a.post(delete_url)
    assert resp_del.status_code == 302
    assert not AffiliatePartner.objects.filter(pk=ecom_affiliate_a.pk).exists()


# ==============================================================================
# AffiliateReferralConversion Views
# ==============================================================================

def test_affiliatereferralconversion_list_and_create_view(client_a, tenant_a, ecom_affiliate_a):
    order = _ordermanagement_order(tenant_a, total_amount=Decimal("300.00"))
    create_url = reverse("ecommerce:affiliatereferralconversion_create")
    resp_post = client_a.post(create_url, {
        "affiliate": ecom_affiliate_a.pk,
        "order": order.pk,
        "attribution_type": "referral_link",
        "order_amount": "300.00",
        "commission_rate_applied": "10.00",
        "notes": "Test order conversion",
    })
    assert resp_post.status_code == 302
    conversion = AffiliateReferralConversion.objects.filter(tenant=tenant_a, order=order).first()
    assert conversion is not None
    assert conversion.status == "pending_review"

    # List view
    list_url = reverse("ecommerce:affiliatereferralconversion_list")
    resp_list = client_a.get(list_url)
    assert resp_list.status_code == 200
    assert "conversions" in resp_list.context
    assert len(resp_list.context["conversions"]) >= 1


def test_affiliatereferralconversion_approve_and_void_lifecycle(client_a, tenant_a, ecom_affiliate_a):
    conversion = _affiliate_conversion(
        tenant_a,
        affiliate=ecom_affiliate_a,
        order_amount=Decimal("100.00"),
        commission_rate_applied=Decimal("10.00"),
        commission_amount=Decimal("10.00"),
        status="pending_review",
    )
    ecom_affiliate_a.refresh_from_db()
    initial_earned = ecom_affiliate_a.total_commission_earned

    # 1. Approve conversion -> credits partner total_commission_earned
    approve_url = reverse("ecommerce:affiliatereferralconversion_approve", args=[conversion.pk])
    resp_app = client_a.post(approve_url)
    assert resp_app.status_code == 302
    conversion.refresh_from_db()
    assert conversion.status == "approved"
    ecom_affiliate_a.refresh_from_db()
    assert ecom_affiliate_a.total_commission_earned == initial_earned + Decimal("10.00")

    # 2. Void conversion -> claws back partner total_commission_earned
    void_url = reverse("ecommerce:affiliatereferralconversion_void", args=[conversion.pk])
    resp_void = client_a.post(void_url)
    assert resp_void.status_code == 302
    conversion.refresh_from_db()
    assert conversion.status == "voided_refund"
    ecom_affiliate_a.refresh_from_db()
    assert ecom_affiliate_a.total_commission_earned == initial_earned


def test_affiliatereferralconversion_delete_view(client_a, tenant_a, ecom_conversion_a):
    delete_url = reverse("ecommerce:affiliatereferralconversion_delete", args=[ecom_conversion_a.pk])
    resp = client_a.post(delete_url)
    assert resp.status_code == 302
    assert not AffiliateReferralConversion.objects.filter(pk=ecom_conversion_a.pk).exists()


# ==============================================================================
# SeoMetadataRule Views
# ==============================================================================

def test_seometadatarule_list_and_create_view(client_a, tenant_a):
    create_url = reverse("ecommerce:seometadatarule_create")
    resp_post = client_a.post(create_url, {
        "name": "Global SEO Rule 2",
        "rule_type": "global_default",
        "meta_title_template": "{title} | Best Store",
        "meta_description_template": "Shop {title} online",
        "json_ld_schema_type": "WebSite",
        "robots_directive": "index_follow",
        "sitemap_included": True,
        "sitemap_priority": "0.90",
        "sitemap_changefreq": "daily",
        "is_active": True,
    })
    assert resp_post.status_code == 302
    rule = SeoMetadataRule.objects.filter(tenant=tenant_a, name="Global SEO Rule 2").first()
    assert rule is not None

    list_url = reverse("ecommerce:seometadatarule_list")
    resp_list = client_a.get(list_url)
    assert resp_list.status_code == 200
    assert "rules" in resp_list.context
    assert len(resp_list.context["rules"]) >= 1


def test_seometadatarule_toggle_and_delete_view(client_a, tenant_a, ecom_seo_rule_a):
    assert ecom_seo_rule_a.is_active is True
    toggle_url = reverse("ecommerce:seometadatarule_toggle", args=[ecom_seo_rule_a.pk])
    resp_toggle = client_a.post(toggle_url)
    assert resp_toggle.status_code == 302
    ecom_seo_rule_a.refresh_from_db()
    assert ecom_seo_rule_a.is_active is False

    delete_url = reverse("ecommerce:seometadatarule_delete", args=[ecom_seo_rule_a.pk])
    resp_del = client_a.post(delete_url)
    assert resp_del.status_code == 302
    assert not SeoMetadataRule.objects.filter(pk=ecom_seo_rule_a.pk).exists()
