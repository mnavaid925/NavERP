"""Unit and invariant tests for eCommerce 9.10 Marketing & Campaign Management models.

Covers:
- MarketingCampaign
- AffiliatePartner
- AffiliateReferralConversion
- SeoMetadataRule

Naming conventions enforced:
- Test functions: test_marketingcampaign_*
- Module-level helpers: _marketingcampaign_*
"""
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import Party
from apps.ecommerce.models import (
    MarketingCampaign,
    AffiliatePartner,
    AffiliateReferralConversion,
    SeoMetadataRule,
    EcommerceOrder,
    CatalogProduct,
    StoreCategory,
    AudienceSegment,
)
from apps.ecommerce.tests.conftest import (
    _marketing_campaign,
    _affiliate_partner,
    _affiliate_conversion,
    _seo_rule,
    MARKETINGCAMPAIGN_MODEL_FIELDS,
    MARKETINGCAMPAIGN_CHOICES,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# MarketingCampaign Model Tests
# ==============================================================================

def test_marketingcampaign_model_fields_contract():
    actual_fields = {f.name for f in MarketingCampaign._meta.get_fields()}
    for expected in MARKETINGCAMPAIGN_MODEL_FIELDS["MarketingCampaign"]:
        assert expected in actual_fields, f"Missing field {expected} on MarketingCampaign"


def test_marketingcampaign_creation_and_auto_number(tenant_a):
    campaign = _marketing_campaign(tenant_a, name="Black Friday Blast", code="BF-2026")
    assert campaign.pk is not None
    assert campaign.number.startswith("EMCP-")
    assert campaign.name == "Black Friday Blast"
    assert campaign.code == "BF-2026"
    assert campaign.status == "draft"
    assert str(campaign) == f"{campaign.name} ({campaign.number})"


def test_marketingcampaign_status_and_channel_choices():
    channel_keys = [c[0] for c in MarketingCampaign.CHANNEL_CHOICES]
    assert "email" in channel_keys
    assert "sms" in channel_keys
    assert "push" in channel_keys
    assert "omnichannel" in channel_keys

    type_keys = [c[0] for c in MarketingCampaign.CAMPAIGN_TYPE_CHOICES]
    assert "newsletter_broadcast" in type_keys
    assert "abandoned_cart" in type_keys
    assert "promotional_flash" in type_keys

    status_keys = [c[0] for c in MarketingCampaign.STATUS_CHOICES]
    assert "draft" in status_keys
    assert "scheduled" in status_keys
    assert "sent" in status_keys
    assert "cancelled" in status_keys


def test_marketingcampaign_metrics_properties(tenant_a):
    campaign = _marketing_campaign(
        tenant_a,
        recipient_count=1000,
        delivered_count=950,
        opened_count=380,
        clicked_count=190,
    )
    # open_rate = 380 / 950 * 100 = 40.0
    assert campaign.open_rate == Decimal("40.0")
    # click_rate = 190 / 950 * 100 = 20.0
    assert campaign.click_rate == Decimal("20.0")


def test_marketingcampaign_metrics_properties_zero_division_safe(tenant_a):
    campaign = _marketing_campaign(
        tenant_a,
        recipient_count=0,
        delivered_count=0,
        opened_count=0,
        clicked_count=0,
    )
    assert campaign.open_rate == Decimal("0.0")
    assert campaign.click_rate == Decimal("0.0")


def test_marketingcampaign_clean_validations(tenant_a):
    campaign = _marketing_campaign(tenant_a, channel="sms", content_body="X" * 1601)
    with pytest.raises(ValidationError) as exc_info:
        campaign.clean()
    assert "content_body" in exc_info.value.message_dict

    campaign.content_body = "Short SMS text"
    campaign.clean()
    assert campaign.code is not None



# ==============================================================================
# AffiliatePartner Model Tests
# ==============================================================================

def test_affiliatepartner_model_fields_contract():
    actual_fields = {f.name for f in AffiliatePartner._meta.get_fields()}
    for expected in MARKETINGCAMPAIGN_MODEL_FIELDS["AffiliatePartner"]:
        assert expected in actual_fields, f"Missing field {expected} on AffiliatePartner"


def test_affiliatepartner_creation_and_auto_number(tenant_a):
    partner = _affiliate_partner(tenant_a, name="Sarah Tech Reviews", referral_code="SARAH10")
    assert partner.pk is not None
    assert partner.number.startswith("EAFF-")
    assert partner.name == "Sarah Tech Reviews"
    assert partner.referral_code == "SARAH10"
    assert partner.status == "pending_approval"
    assert str(partner) == f"{partner.name} [{partner.referral_code}]"


def test_affiliatepartner_choices():
    partner_types = [c[0] for c in AffiliatePartner.PARTNER_TYPE_CHOICES]
    assert "affiliate" in partner_types
    assert "influencer" in partner_types
    assert "brand_ambassador" in partner_types

    commission_types = [c[0] for c in AffiliatePartner.COMMISSION_TYPE_CHOICES]
    assert "percentage_net_sales" in commission_types
    assert "flat_per_order" in commission_types
    assert "tiered" in commission_types

    statuses = [c[0] for c in AffiliatePartner.STATUS_CHOICES]
    assert "pending_approval" in statuses
    assert "active" in statuses
    assert "suspended" in statuses
    assert "inactive" in statuses


def test_affiliatepartner_unpaid_commission_and_eligibility(tenant_a):
    partner = _affiliate_partner(
        tenant_a,
        total_commission_earned=Decimal("150.00"),
        total_commission_paid=Decimal("50.00"),
        payout_threshold=Decimal("75.00"),
    )
    assert partner.unpaid_commission == Decimal("100.00")
    assert partner.is_eligible_for_payout is True

    partner.payout_threshold = Decimal("200.00")
    assert partner.is_eligible_for_payout is False

    partner.total_commission_paid = Decimal("160.00")
    assert partner.unpaid_commission == Decimal("0.00")


def test_affiliatepartner_clean_negative_rates(tenant_a):
    partner = _affiliate_partner(tenant_a)
    partner.commission_rate = Decimal("-2.50")
    with pytest.raises(ValidationError):
        partner.full_clean()

    partner.commission_rate = Decimal("10.00")
    partner.payout_threshold = Decimal("-10.00")
    with pytest.raises(ValidationError):
        partner.full_clean()


# ==============================================================================
# AffiliateReferralConversion Model Tests
# ==============================================================================

def test_affiliatereferralconversion_model_fields_contract():
    actual_fields = {f.name for f in AffiliateReferralConversion._meta.get_fields()}
    for expected in MARKETINGCAMPAIGN_MODEL_FIELDS["AffiliateReferralConversion"]:
        assert expected in actual_fields, f"Missing field {expected} on AffiliateReferralConversion"


def test_affiliatereferralconversion_creation_and_auto_number(tenant_a):
    conversion = _affiliate_conversion(
        tenant_a,
        order_amount=Decimal("200.00"),
        commission_rate_applied=Decimal("15.00"),
        commission_amount=Decimal("30.00"),
    )
    assert conversion.pk is not None
    assert conversion.number.startswith("EARC-")
    assert conversion.order_amount == Decimal("200.00")
    assert conversion.commission_amount == Decimal("30.00")
    assert conversion.status == "pending_review"
    assert str(conversion) == f"Conversion {conversion.number}"


def test_affiliatereferralconversion_choices():
    attribution_types = [c[0] for c in AffiliateReferralConversion.ATTRIBUTION_TYPE_CHOICES]
    assert "referral_link" in attribution_types
    assert "coupon_code" in attribution_types
    assert "manual_credit" in attribution_types

    statuses = [c[0] for c in AffiliateReferralConversion.STATUS_CHOICES]
    assert "pending_review" in statuses
    assert "approved" in statuses
    assert "paid" in statuses
    assert "voided_refund" in statuses


def test_affiliatereferralconversion_clean_validation(tenant_a):
    conversion = _affiliate_conversion(tenant_a)
    conversion.order_amount = Decimal("-50.00")
    with pytest.raises(ValidationError):
        conversion.full_clean()

    conversion.order_amount = Decimal("100.00")
    conversion.commission_rate_applied = Decimal("-1.00")
    with pytest.raises(ValidationError):
        conversion.full_clean()



# ==============================================================================
# SeoMetadataRule Model Tests
# ==============================================================================

def test_seometadatarule_model_fields_contract():
    actual_fields = {f.name for f in SeoMetadataRule._meta.get_fields()}
    for expected in MARKETINGCAMPAIGN_MODEL_FIELDS["SeoMetadataRule"]:
        assert expected in actual_fields, f"Missing field {expected} on SeoMetadataRule"


def test_seometadatarule_creation_and_auto_number(tenant_a):
    rule = _seo_rule(tenant_a, name="Default Storefront SEO")
    assert rule.pk is not None
    assert rule.number.startswith("ESEO-")
    assert rule.name == "Default Storefront SEO"
    assert rule.rule_type == "global_default"
    assert rule.is_active is True
    assert str(rule) == f"{rule.name} [{rule.get_rule_type_display()}]"


def test_seometadatarule_choices():
    rules = [c[0] for c in SeoMetadataRule.RULE_TYPE_CHOICES]
    assert "global_default" in rules
    assert "category_template" in rules
    assert "product_template" in rules
    assert "custom_url" in rules

    schemas = [c[0] for c in SeoMetadataRule.SCHEMA_TYPE_CHOICES]
    assert "Product" in schemas
    assert "BreadcrumbList" in schemas
    assert "WebSite" in schemas

    robots = [c[0] for c in SeoMetadataRule.ROBOTS_CHOICES]
    assert "index_follow" in robots
    assert "noindex_nofollow" in robots

    changefreq = [c[0] for c in SeoMetadataRule.CHANGEFREQ_CHOICES]
    assert "daily" in changefreq
    assert "weekly" in changefreq


def test_seometadatarule_token_replacement(tenant_a):
    rule = _seo_rule(
        tenant_a,
        meta_title_template="{title} by {brand} | Best Price",
        meta_description_template="Shop {title} in {category} for only {price} at {store_name}."
    )
    context = {
        "title": "WH-1000XM5",
        "brand": "Sony",
        "category": "Audio",
        "price": "$399.99",
        "store_name": "SoundHub",
    }
    rendered_title = rule.render_title(context)
    rendered_desc = rule.render_description(context)
    assert "WH-1000XM5 by Sony | Best Price" == rendered_title
    assert "Shop WH-1000XM5 in Audio for only $399.99 at SoundHub." == rendered_desc



def test_seometadatarule_clean_sitemap_priority_range(tenant_a):
    rule = _seo_rule(tenant_a)
    rule.sitemap_priority = Decimal("1.50")
    with pytest.raises(ValidationError):
        rule.full_clean()

    rule.sitemap_priority = Decimal("-0.10")
    with pytest.raises(ValidationError):
        rule.full_clean()

    rule.sitemap_priority = Decimal("0.85")
    rule.full_clean()  # should not raise
