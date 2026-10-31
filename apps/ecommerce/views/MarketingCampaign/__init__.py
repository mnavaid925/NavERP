from apps.ecommerce.views.MarketingCampaign.AffiliatePartners import (
    affiliatepartner_approve,
    affiliatepartner_create,
    affiliatepartner_delete,
    affiliatepartner_detail,
    affiliatepartner_edit,
    affiliatepartner_list,
)
from apps.ecommerce.views.MarketingCampaign.AffiliateReferralConversions import (
    affiliatereferralconversion_approve,
    affiliatereferralconversion_create,
    affiliatereferralconversion_delete,
    affiliatereferralconversion_detail,
    affiliatereferralconversion_edit,
    affiliatereferralconversion_list,
    affiliatereferralconversion_void,
)
from apps.ecommerce.views.MarketingCampaign.MarketingCampaigns import (
    marketingcampaign_create,
    marketingcampaign_delete,
    marketingcampaign_detail,
    marketingcampaign_edit,
    marketingcampaign_list,
    marketingcampaign_send,
)
from apps.ecommerce.views.MarketingCampaign.MarketingDashboards import (
    marketing_dashboard,
    social_commerce_feed,
)
from apps.ecommerce.views.MarketingCampaign.SeoMetadataRules import (
    seometadatarule_create,
    seometadatarule_delete,
    seometadatarule_detail,
    seometadatarule_edit,
    seometadatarule_list,
    seometadatarule_toggle,
)

__all__ = [
    # Campaign Views
    "marketingcampaign_list",
    "marketingcampaign_detail",
    "marketingcampaign_create",
    "marketingcampaign_edit",
    "marketingcampaign_delete",
    "marketingcampaign_send",
    # Affiliate Partner Views
    "affiliatepartner_list",
    "affiliatepartner_detail",
    "affiliatepartner_create",
    "affiliatepartner_edit",
    "affiliatepartner_delete",
    "affiliatepartner_approve",
    # Referral Conversion Views
    "affiliatereferralconversion_list",
    "affiliatereferralconversion_detail",
    "affiliatereferralconversion_create",
    "affiliatereferralconversion_edit",
    "affiliatereferralconversion_delete",
    "affiliatereferralconversion_approve",
    "affiliatereferralconversion_void",
    # SEO Metadata Rule Views
    "seometadatarule_list",
    "seometadatarule_detail",
    "seometadatarule_create",
    "seometadatarule_edit",
    "seometadatarule_delete",
    "seometadatarule_toggle",
    # Marketing Dashboard & Feeds
    "marketing_dashboard",
    "social_commerce_feed",
]
