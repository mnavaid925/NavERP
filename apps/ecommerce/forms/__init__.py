from apps.ecommerce.forms._common import TenantUniqueMixin, reject_foreign
from apps.ecommerce.forms.CartCheckout.Carts import CartForm, CartItemForm
from apps.ecommerce.forms.CartCheckout.CheckoutSessions import CheckoutSessionForm
from apps.ecommerce.forms.CartCheckout.PaymentMethods import PaymentMethodConfigForm
from apps.ecommerce.forms.CartCheckout.ShippingMethods import ShippingMethodConfigForm
from apps.ecommerce.forms.CustomerProfile.CustomerAccountProfiles import CustomerAccountProfileForm
from apps.ecommerce.forms.CustomerProfile.CustomerAddressPreferences import CustomerAddressPreferenceForm
from apps.ecommerce.forms.CustomerProfile.CustomerPrivacyRequests import CustomerPrivacyRequestForm
from apps.ecommerce.forms.CustomerProfile.CustomerWishlists import CustomerWishlistForm, CustomerWishlistItemForm
from apps.ecommerce.forms.InventoryStock.BackorderPolicies import BackorderPolicyForm
from apps.ecommerce.forms.InventoryStock.ChannelInventorySyncs import ChannelInventorySyncForm
from apps.ecommerce.forms.InventoryStock.FulfillmentCenters import FulfillmentCenterForm
from apps.ecommerce.forms.InventoryStock.InventoryAllocations import (
    InventoryAllocationForm,
    StockAdjustmentActionForm,
)
from apps.ecommerce.forms.MarketingCampaign.AffiliatePartners import AffiliatePartnerForm
from apps.ecommerce.forms.MarketingCampaign.AffiliateReferralConversions import AffiliateReferralConversionForm
from apps.ecommerce.forms.MarketingCampaign.MarketingCampaigns import MarketingCampaignForm
from apps.ecommerce.forms.MarketingCampaign.SeoMetadataRules import SeoMetadataRuleForm
from apps.ecommerce.forms.Marketplace.MarketplaceVendorForms import (
    MarketplaceVendorForm,
    VendorKycVerificationForm,
    VendorSuspensionForm,
)
from apps.ecommerce.forms.Marketplace.VendorPayoutForms import (
    PayoutApprovalForm,
    VendorPayoutForm,
)
from apps.ecommerce.forms.Marketplace.VendorProductListingForms import (
    ListingModerationForm,
    VendorProductListingForm,
)
from apps.ecommerce.forms.Marketplace.VendorSubOrderForms import (
    SubOrderDisputeForm,
    SubOrderFulfillmentForm,
    SubOrderReviewForm,
    VendorSubOrderForm,
)
from apps.ecommerce.forms.OrderManagement.EcommerceOrders import EcommerceOrderForm, EcommerceOrderLineForm
from apps.ecommerce.forms.OrderManagement.OrderFulfillments import OrderFulfillmentForm
from apps.ecommerce.forms.OrderManagement.OrderRoutingRules import OrderRoutingRuleForm
from apps.ecommerce.forms.OrderManagement.ReturnMerchandiseAuthorizations import ReturnMerchandiseAuthorizationForm
from apps.ecommerce.forms.Personalization.AudienceSegments import AudienceSegmentForm
from apps.ecommerce.forms.Personalization.PersonalizedExperiences import PersonalizedExperienceForm
from apps.ecommerce.forms.Personalization.RecommendationStrategies import RecommendationStrategyForm
from apps.ecommerce.forms.Personalization.ShopperBehaviorEvents import ShopperBehaviorEventFilterForm
from apps.ecommerce.forms.PricingPromotion.CompetitorPriceMonitors import CompetitorPriceMonitorForm
from apps.ecommerce.forms.PricingPromotion.CouponPromotions import CouponPromotionForm
from apps.ecommerce.forms.PricingPromotion.DynamicPriceRules import DynamicPriceRuleForm
from apps.ecommerce.forms.PricingPromotion.FlashSales import FlashSaleForm
from apps.ecommerce.forms.ProductCatalog.BulkOperations import ProductImportForm
from apps.ecommerce.forms.ProductCatalog.CatalogProducts import CatalogProductForm
from apps.ecommerce.forms.ProductCatalog.ProductRelationships import (
    ProductRelationshipForm,
)
from apps.ecommerce.forms.ProductCatalog.ProductVariants import ProductVariantForm
from apps.ecommerce.forms.ProductCatalog.StoreCategories import StoreCategoryForm
from apps.ecommerce.forms.SearchDiscovery.SearchFacetConfigs import SearchFacetConfigForm
from apps.ecommerce.forms.SearchDiscovery.SearchMerchandisingRules import SearchMerchandisingRuleForm
from apps.ecommerce.forms.SearchDiscovery.SearchQueryLogs import (
    SearchQueryLogFilterForm,
    SearchQueryLogForm,
)
from apps.ecommerce.forms.SearchDiscovery.SearchSynonyms import SearchSynonymForm
from apps.ecommerce.forms.CustomerSupport.CustomerSatisfactionSurveys import CustomerSatisfactionSurveyForm
from apps.ecommerce.forms.CustomerSupport.CustomerSupportTickets import CustomerSupportTicketForm
from apps.ecommerce.forms.CustomerSupport.KnowledgeBaseArticles import KnowledgeBaseArticleForm
from apps.ecommerce.forms.CustomerSupport.OrderIssueClaims import OrderIssueClaimForm
from apps.ecommerce.forms.ReviewUgc.ProductQuestionAnswers import (
    ProductQuestionAnswerForm,
    ProductQuestionAnswerResponseForm,
)
from apps.ecommerce.forms.ReviewUgc.ProductReviews import (
    ProductReviewForm,
    ProductReviewModerationForm,
)
from apps.ecommerce.forms.ReviewUgc.ReviewSentimentSummaries import (
    ReviewSentimentSummaryForm,
)
from apps.ecommerce.forms.ReviewUgc.VisualUgcMedia import (
    VisualUgcMediaForm,
)
from apps.ecommerce.forms.SubscriptionCommerce.CustomerSubscriptions import CustomerSubscriptionForm
from apps.ecommerce.forms.SubscriptionCommerce.SubscriptionBoxCurations import SubscriptionBoxCurationForm
from apps.ecommerce.forms.SubscriptionCommerce.SubscriptionPlans import SubscriptionPlanForm
from apps.ecommerce.forms.SubscriptionCommerce.SubscriptionRetentionActions import SubscriptionRetentionActionForm
from apps.ecommerce.forms.ContentManagement.BlogArticles import BlogArticleForm
from apps.ecommerce.forms.ContentManagement.CmsPages import CmsPageForm
from apps.ecommerce.forms.ContentManagement.ContentBlocks import ContentBlockForm
from apps.ecommerce.forms.ContentManagement.MediaAssets import MediaAssetForm
from apps.ecommerce.forms.AnalyticsBi.DailySalesSnapshots import DailySalesSnapshotForm
from apps.ecommerce.forms.AnalyticsBi.CustomerCohortMetrics import CustomerCohortMetricForm
from apps.ecommerce.forms.AnalyticsBi.ProductMerchandisingMetrics import ProductMerchandisingMetricForm
from apps.ecommerce.forms.AnalyticsBi.AttributionTouchpoints import AttributionTouchpointForm
from apps.ecommerce.forms.MobileCommerce.MobileAppConfigs import MobileAppConfigForm
from apps.ecommerce.forms.MobileCommerce.MobileDeviceRegistrations import MobileDeviceRegistrationForm
from apps.ecommerce.forms.MobileCommerce.MobilePushCampaigns import MobilePushCampaignForm
from apps.ecommerce.forms.MobileCommerce.MobileLocationRules import MobileLocationRuleForm
from apps.ecommerce.forms.B2bWholesale.B2bCompanyAccounts import B2bCompanyAccountForm
from apps.ecommerce.forms.B2bWholesale.B2bCompanyUsers import B2bCompanyUserForm
from apps.ecommerce.forms.B2bWholesale.B2bQuoteRequests import B2bQuoteRequestForm
from apps.ecommerce.forms.B2bWholesale.B2bQuickOrderTemplates import B2bQuickOrderTemplateForm
from apps.ecommerce.forms.FraudRisk.FraudRules import FraudRuleForm
from apps.ecommerce.forms.FraudRisk.TransactionRiskAssessments import TransactionRiskAssessmentForm
from apps.ecommerce.forms.FraudRisk.ChargebackDisputes import ChargebackDisputeForm
from apps.ecommerce.forms.FraudRisk.AccountSecurityAlerts import AccountSecurityAlertForm
from apps.ecommerce.forms.IntegrationApi.EcommerceConnectors import EcommerceConnectorForm
from apps.ecommerce.forms.IntegrationApi.IntegrationSyncJobs import IntegrationSyncJobForm
from apps.ecommerce.forms.IntegrationApi.WebhookSubscriptions import WebhookSubscriptionForm
from apps.ecommerce.forms.IntegrationApi.ApiCredentials import ApiCredentialForm
from apps.ecommerce.forms.MultiStore.StorefrontInstances import StorefrontInstanceForm
from apps.ecommerce.forms.MultiStore.StorefrontCatalogAssignments import StorefrontCatalogAssignmentForm
from apps.ecommerce.forms.MultiStore.PlatformEnvironments import PlatformEnvironmentForm
from apps.ecommerce.forms.MultiStore.DeploymentPipelines import DeploymentPipelineForm

__all__ = [
    "TenantUniqueMixin",
    "reject_foreign",
    # 9.1 Product Catalog
    "StoreCategoryForm",
    "CatalogProductForm",
    "ProductVariantForm",
    "ProductRelationshipForm",
    "ProductImportForm",
    # 9.2 Inventory & Stock Management
    "FulfillmentCenterForm",
    "InventoryAllocationForm",
    "StockAdjustmentActionForm",
    "BackorderPolicyForm",
    "ChannelInventorySyncForm",
    # 9.3 Pricing & Promotion Engine
    "DynamicPriceRuleForm",
    "CouponPromotionForm",
    "FlashSaleForm",
    "CompetitorPriceMonitorForm",
    # 9.4 Shopping Cart & Checkout
    "CartForm",
    "CartItemForm",
    "CheckoutSessionForm",
    "ShippingMethodConfigForm",
    "PaymentMethodConfigForm",
    # 9.5 Order Management System (OMS)
    "EcommerceOrderForm",
    "EcommerceOrderLineForm",
    "OrderRoutingRuleForm",
    "OrderFulfillmentForm",
    "ReturnMerchandiseAuthorizationForm",
    # 9.6 Customer Account & Profile
    "CustomerAccountProfileForm",
    "CustomerAddressPreferenceForm",
    "CustomerWishlistForm",
    "CustomerWishlistItemForm",
    "CustomerPrivacyRequestForm",
    # 9.7 Search & Product Discovery
    "SearchSynonymForm",
    "SearchFacetConfigForm",
    "SearchMerchandisingRuleForm",
    "SearchQueryLogForm",
    "SearchQueryLogFilterForm",
    # 9.8 Personalization & Recommendation Engine
    "AudienceSegmentForm",
    "RecommendationStrategyForm",
    "PersonalizedExperienceForm",
    "ShopperBehaviorEventFilterForm",
    # 9.10 Marketing & Campaign Management
    "MarketingCampaignForm",
    "AffiliatePartnerForm",
    "AffiliateReferralConversionForm",
    "SeoMetadataRuleForm",
    # 9.11 Marketplace & Multi-Vendor
    "MarketplaceVendorForm",
    "VendorKycVerificationForm",
    "VendorSuspensionForm",
    "VendorProductListingForm",
    "ListingModerationForm",
    "VendorSubOrderForm",
    "SubOrderFulfillmentForm",
    "SubOrderDisputeForm",
    "SubOrderReviewForm",
    "VendorPayoutForm",
    "PayoutApprovalForm",
    # 9.12 Subscription & Recurring Commerce
    "SubscriptionPlanForm",
    "CustomerSubscriptionForm",
    "SubscriptionBoxCurationForm",
    "SubscriptionRetentionActionForm",
    # 9.13 Reviews & User-Generated Content
    "ProductReviewForm",
    "ProductReviewModerationForm",
    "ProductQuestionAnswerForm",
    "ProductQuestionAnswerResponseForm",
    "VisualUgcMediaForm",
    "ReviewSentimentSummaryForm",
    # 9.14 Customer Service & Support
    "CustomerSupportTicketForm",
    "KnowledgeBaseArticleForm",
    "OrderIssueClaimForm",
    "CustomerSatisfactionSurveyForm",
    # 9.9 Content Management System (CMS)
    "CmsPageForm",
    "BlogArticleForm",
    "MediaAssetForm",
    "ContentBlockForm",
    # 9.15 Analytics & Business Intelligence
    "DailySalesSnapshotForm",
    "CustomerCohortMetricForm",
    "ProductMerchandisingMetricForm",
    "AttributionTouchpointForm",
    # 9.16 Mobile Commerce
    "MobileAppConfigForm",
    "MobileDeviceRegistrationForm",
    "MobilePushCampaignForm",
    "MobileLocationRuleForm",
    # 9.17 B2B & Wholesale Commerce
    "B2bCompanyAccountForm",
    "B2bCompanyUserForm",
    "B2bQuoteRequestForm",
    "B2bQuickOrderTemplateForm",
    # 9.18 Fraud & Risk Management
    "FraudRuleForm",
    "TransactionRiskAssessmentForm",
    "ChargebackDisputeForm",
    "AccountSecurityAlertForm",
    # 9.19 Integration & API Ecosystem
    "EcommerceConnectorForm",
    "IntegrationSyncJobForm",
    "WebhookSubscriptionForm",
    "ApiCredentialForm",
    # 9.20 Multi-Store & Platform Operations
    "StorefrontInstanceForm",
    "StorefrontCatalogAssignmentForm",
    "PlatformEnvironmentForm",
    "DeploymentPipelineForm",
]
