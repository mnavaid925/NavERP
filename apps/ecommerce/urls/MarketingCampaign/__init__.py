from apps.ecommerce.urls.MarketingCampaign.AffiliatePartners import (
    urlpatterns as affiliate_partner_urls,
)
from apps.ecommerce.urls.MarketingCampaign.AffiliateReferralConversions import (
    urlpatterns as affiliate_referral_conversion_urls,
)
from apps.ecommerce.urls.MarketingCampaign.MarketingCampaigns import (
    urlpatterns as marketing_campaign_urls,
)
from apps.ecommerce.urls.MarketingCampaign.MarketingDashboards import (
    urlpatterns as marketing_dashboard_urls,
)
from apps.ecommerce.urls.MarketingCampaign.SeoMetadataRules import (
    urlpatterns as seo_metadata_rule_urls,
)

urlpatterns = (
    marketing_dashboard_urls
    + marketing_campaign_urls
    + affiliate_partner_urls
    + affiliate_referral_conversion_urls
    + seo_metadata_rule_urls
)
