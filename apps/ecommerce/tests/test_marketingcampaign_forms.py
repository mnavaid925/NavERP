"""Form validation and foreign-key isolation tests for eCommerce 9.10 Marketing forms.

Covers:
- MarketingCampaignForm
- AffiliatePartnerForm
- AffiliateReferralConversionForm
- SeoMetadataRuleForm

Naming conventions enforced:
- Test functions: test_marketingcampaign_*
- Module-level helpers: _marketingcampaign_*
"""
from decimal import Decimal
import pytest

from apps.core.models import Party
from apps.ecommerce.models import (
    MarketingCampaign,
    AffiliatePartner,
    AffiliateReferralConversion,
    SeoMetadataRule,
    StoreCategory,
    CatalogProduct,
    AudienceSegment,
    CustomerAccountProfile,
    EcommerceOrder,
)
from apps.ecommerce.forms import (
    MarketingCampaignForm,
    AffiliatePartnerForm,
    AffiliateReferralConversionForm,
    SeoMetadataRuleForm,
)
from apps.ecommerce.tests.conftest import (
    _marketing_campaign,
    _affiliate_partner,
    _ordermanagement_order,
    MARKETINGCAMPAIGN_FORM_FIELDS,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# MarketingCampaignForm Tests
# ==============================================================================

def test_marketingcampaign_form_excluded_fields():
    form = MarketingCampaignForm()
    # Security/Mass-assignment invariants: status, tenant, number, and counters must be excluded
    for excluded in ["tenant", "number", "status", "revenue_attributed", "recipient_count", "delivered_count", "opened_count", "clicked_count", "bounced_count", "unsubscribed_count", "complaint_count", "sent_at"]:
        assert excluded not in form.fields, f"Field '{excluded}' unexpectedly exposed in MarketingCampaignForm"


def test_marketingcampaign_form_valid(tenant_a):
    cat = StoreCategory.objects.create(tenant=tenant_a, name="Apparel", slug="apparel")
    product = CatalogProduct.objects.create(tenant=tenant_a, name="T-Shirt", slug="t-shirt", primary_category=cat)
    segment = AudienceSegment.objects.create(tenant=tenant_a, name="VIP Buyers")

    form_data = {
        "name": "Summer VIP Flash",
        "code": "SUMMER-VIP",
        "campaign_type": "promotional_flash",
        "channel": "email",
        "target_segment": segment.pk,
        "target_product": product.pk,
        "subject": "50% Off Today Only",
        "preview_text": "Exclusive flash discount",
        "content_body": "<p>Limited time offer!</p>",
        "sender_name": "Acme Deals",
        "sender_address": "deals@acme.com",
        "send_throttle_window_hours": 12,
        "geofence_latitude": "",
        "geofence_longitude": "",
        "geofence_radius_km": "",
    }
    form = MarketingCampaignForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    campaign = form.save(commit=False)
    campaign.tenant = tenant_a
    campaign.save()
    assert campaign.pk is not None
    assert campaign.status == "draft"


def test_marketingcampaign_form_cross_tenant_foreign_key_rejected(tenant_a, tenant_b):
    cat_b = StoreCategory.objects.create(tenant=tenant_b, name="Globex Shoes", slug="globex-shoes")
    product_b = CatalogProduct.objects.create(tenant=tenant_b, name="Sneakers", slug="sneakers", primary_category=cat_b)
    segment_b = AudienceSegment.objects.create(tenant=tenant_b, name="Globex Audience")

    form_data = {
        "name": "Intruder Campaign",
        "code": "INTRUDER",
        "campaign_type": "newsletter_broadcast",
        "channel": "email",
        "target_segment": segment_b.pk,
        "target_product": product_b.pk,
        "subject": "Cross-tenant attempt",
    }
    form = MarketingCampaignForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_segment" in form.errors or "target_product" in form.errors


def test_marketingcampaign_form_sms_length_validation(tenant_a):
    form_data = {
        "name": "Long SMS",
        "code": "LONG-SMS",
        "campaign_type": "order_alert",
        "channel": "sms",
        "content_body": "A" * 1601,
        "sender_name": "Alerts",
    }
    form = MarketingCampaignForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "content_body" in form.errors


# ==============================================================================
# AffiliatePartnerForm Tests
# ==============================================================================

def test_affiliatepartner_form_excluded_fields():
    form = AffiliatePartnerForm()
    # status, tenant, number, and payout totals must be excluded
    for excluded in ["tenant", "number", "status", "total_orders_referred", "total_revenue_generated", "total_commission_earned", "total_commission_paid"]:
        assert excluded not in form.fields, f"Field '{excluded}' unexpectedly exposed in AffiliatePartnerForm"


def test_affiliatepartner_form_valid(tenant_a):
    party = Party.objects.create(tenant=tenant_a, name="Apex Influencer LLC", kind="organization")
    profile = CustomerAccountProfile.objects.create(tenant=tenant_a, customer=party)

    form_data = {
        "name": "Apex Influencer",
        "party": party.pk,
        "customer_profile": profile.pk,
        "partner_type": "influencer",
        "referral_code": "APEX2026",
        "referral_link_slug": "apex",
        "commission_type": "percentage_net_sales",
        "commission_rate": "15.00",
        "cookie_duration_days": 45,
        "payout_threshold": "100.00",
        "payment_email": "apex@payout.com",
    }
    form = AffiliatePartnerForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    partner = form.save(commit=False)
    partner.tenant = tenant_a
    partner.save()
    assert partner.pk is not None
    assert partner.status == "pending_approval"


def test_affiliatepartner_form_cross_tenant_rejected(tenant_a, tenant_b):
    party_b = Party.objects.create(tenant=tenant_b, name="Competitor Partner", kind="person")
    form_data = {
        "name": "Malicious Partner",
        "party": party_b.pk,
        "partner_type": "affiliate",
        "referral_code": "EVIL01",
        "commission_type": "flat_per_order",
        "commission_rate": "5.00",
    }
    form = AffiliatePartnerForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "party" in form.errors


def test_affiliatepartner_form_negative_rates_rejected(tenant_a):
    party = Party.objects.create(tenant=tenant_a, name="Valid Party", kind="person")
    form_data = {
        "name": "Bad Rates Partner",
        "party": party.pk,
        "partner_type": "affiliate",
        "referral_code": "BADRATES",
        "commission_type": "percentage_net_sales",
        "commission_rate": "-10.00",
        "payout_threshold": "-50.00",
    }
    form = AffiliatePartnerForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "commission_rate" in form.errors or "payout_threshold" in form.errors


# ==============================================================================
# AffiliateReferralConversionForm Tests
# ==============================================================================

def test_affiliatereferralconversion_form_excluded_fields():
    form = AffiliateReferralConversionForm()
    for excluded in ["tenant", "number", "status", "payout_reference", "paid_at"]:
        assert excluded not in form.fields, f"Field '{excluded}' unexpectedly exposed in AffiliateReferralConversionForm"


def test_affiliatereferralconversion_form_valid(tenant_a):
    partner = _affiliate_partner(tenant_a)
    order = _ordermanagement_order(tenant_a, total_amount=Decimal("250.00"))

    form_data = {
        "affiliate": partner.pk,
        "order": order.pk,
        "attribution_type": "referral_link",
        "order_amount": "250.00",
        "commission_rate_applied": "10.00",
        "notes": "Generated via summer campaign link",
    }
    form = AffiliateReferralConversionForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    conversion = form.save(commit=False)
    conversion.tenant = tenant_a
    conversion.commission_amount = Decimal("25.00")
    conversion.save()
    assert conversion.pk is not None
    assert conversion.status == "pending_review"


def test_affiliatereferralconversion_form_cross_tenant_rejected(tenant_a, tenant_b):
    partner_b = _affiliate_partner(tenant_b)
    order_b = _ordermanagement_order(tenant_b, total_amount=Decimal("100.00"))

    form_data = {
        "affiliate": partner_b.pk,
        "order": order_b.pk,
        "attribution_type": "coupon_code",
        "order_amount": "100.00",
        "commission_rate_applied": "5.00",
    }
    form = AffiliateReferralConversionForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "affiliate" in form.errors or "order" in form.errors


def test_affiliatereferralconversion_form_negative_amount_rejected(tenant_a):
    partner = _affiliate_partner(tenant_a)
    order = _ordermanagement_order(tenant_a)

    form_data = {
        "affiliate": partner.pk,
        "order": order.pk,
        "attribution_type": "manual_credit",
        "order_amount": "-50.00",
        "commission_rate_applied": "10.00",
    }
    form = AffiliateReferralConversionForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "order_amount" in form.errors


# ==============================================================================
# SeoMetadataRuleForm Tests
# ==============================================================================

def test_seometadatarule_form_excluded_fields():
    form = SeoMetadataRuleForm()
    for excluded in ["tenant", "number", "tracked_rank_position", "rank_tracked_at"]:
        assert excluded not in form.fields, f"Field '{excluded}' unexpectedly exposed in SeoMetadataRuleForm"


def test_seometadatarule_form_valid(tenant_a):
    cat = StoreCategory.objects.create(tenant=tenant_a, name="Laptops", slug="laptops")
    form_data = {
        "name": "Laptops Category Dynamic SEO",
        "rule_type": "category_template",
        "target_category": cat.pk,
        "meta_title_template": "{title} | Best Laptops",
        "meta_description_template": "Browse top {title} options with fast delivery.",
        "json_ld_schema_type": "BreadcrumbList",
        "robots_directive": "index_follow",
        "sitemap_included": True,
        "sitemap_priority": "0.75",
        "sitemap_changefreq": "weekly",
        "target_keyword": "gaming laptops",
        "is_active": True,
    }
    form = SeoMetadataRuleForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    rule = form.save(commit=False)
    rule.tenant = tenant_a
    rule.save()
    assert rule.pk is not None


def test_seometadatarule_form_cross_tenant_rejected(tenant_a, tenant_b):
    cat_b = StoreCategory.objects.create(tenant=tenant_b, name="Globex Audio", slug="globex-audio")
    form_data = {
        "name": "Cross Tenant Category SEO",
        "rule_type": "category_template",
        "target_category": cat_b.pk,
        "meta_title_template": "{title} | Bad",
        "meta_description_template": "Bad description",
        "json_ld_schema_type": "None",
        "robots_directive": "index_follow",
        "sitemap_priority": "0.50",
        "sitemap_changefreq": "daily",
        "is_active": True,
    }
    form = SeoMetadataRuleForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_category" in form.errors


def test_seometadatarule_form_sitemap_priority_range(tenant_a):
    form_data = {
        "name": "Out of Range Priority",
        "rule_type": "global_default",
        "meta_title_template": "Store Title",
        "meta_description_template": "Store Description",
        "json_ld_schema_type": "WebSite",
        "robots_directive": "index_follow",
        "sitemap_priority": "1.50",
        "sitemap_changefreq": "daily",
        "is_active": True,
    }
    form = SeoMetadataRuleForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "sitemap_priority" in form.errors
