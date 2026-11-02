from django.contrib import admin

from apps.ecommerce.models.CartCheckout.Carts import Cart, CartItem
from apps.ecommerce.models.CartCheckout.CheckoutSessions import CheckoutSession
from apps.ecommerce.models.CartCheckout.PaymentMethods import PaymentMethodConfig
from apps.ecommerce.models.CartCheckout.ShippingMethods import ShippingMethodConfig
from apps.ecommerce.models.CustomerProfile.CustomerAccountProfiles import CustomerAccountProfile
from apps.ecommerce.models.CustomerProfile.CustomerAddressPreferences import CustomerAddressPreference
from apps.ecommerce.models.CustomerProfile.CustomerPrivacyRequests import CustomerPrivacyRequest
from apps.ecommerce.models.CustomerProfile.CustomerWishlists import CustomerWishlist, CustomerWishlistItem
from apps.ecommerce.models.InventoryStock.BackorderPolicies import BackorderPolicy
from apps.ecommerce.models.InventoryStock.ChannelInventorySyncs import ChannelInventorySync
from apps.ecommerce.models.InventoryStock.FulfillmentCenters import FulfillmentCenter
from apps.ecommerce.models.InventoryStock.InventoryAllocations import InventoryAllocation
from apps.ecommerce.models.MarketingCampaign.AffiliatePartners import AffiliatePartner
from apps.ecommerce.models.MarketingCampaign.AffiliateReferralConversions import AffiliateReferralConversion
from apps.ecommerce.models.MarketingCampaign.MarketingCampaigns import MarketingCampaign
from apps.ecommerce.models.MarketingCampaign.SeoMetadataRules import SeoMetadataRule
from apps.ecommerce.models.Marketplace.MarketplaceVendors import MarketplaceVendor
from apps.ecommerce.models.Marketplace.VendorPayouts import VendorPayout
from apps.ecommerce.models.Marketplace.VendorProductListings import VendorProductListing
from apps.ecommerce.models.Marketplace.VendorSubOrders import VendorSubOrder
from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrder, EcommerceOrderLine
from apps.ecommerce.models.OrderManagement.OrderFulfillments import OrderFulfillment
from apps.ecommerce.models.OrderManagement.OrderRoutingRules import OrderRoutingRule
from apps.ecommerce.models.OrderManagement.ReturnMerchandiseAuthorizations import ReturnMerchandiseAuthorization
from apps.ecommerce.models.Personalization.AudienceSegments import AudienceSegment
from apps.ecommerce.models.Personalization.PersonalizedExperiences import PersonalizedExperience
from apps.ecommerce.models.Personalization.RecommendationStrategies import RecommendationStrategy
from apps.ecommerce.models.Personalization.ShopperBehaviorEvents import ShopperBehaviorEvent
from apps.ecommerce.models.PricingPromotion.CompetitorPriceMonitors import CompetitorPriceMonitor
from apps.ecommerce.models.PricingPromotion.CouponPromotions import CouponPromotion
from apps.ecommerce.models.PricingPromotion.DynamicPriceRules import DynamicPriceRule
from apps.ecommerce.models.PricingPromotion.FlashSales import FlashSale
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductRelationships import ProductRelationship
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory
from apps.ecommerce.models.SearchDiscovery.SearchFacetConfigs import SearchFacetConfig
from apps.ecommerce.models.SearchDiscovery.SearchMerchandisingRules import SearchMerchandisingRule
from apps.ecommerce.models.SearchDiscovery.SearchQueryLogs import SearchQueryLog
from apps.ecommerce.models.SearchDiscovery.SearchSynonyms import SearchSynonym
from apps.ecommerce.models.CustomerSupport.CustomerSatisfactionSurveys import CustomerSatisfactionSurvey
from apps.ecommerce.models.CustomerSupport.CustomerSupportTickets import CustomerSupportTicket
from apps.ecommerce.models.CustomerSupport.KnowledgeBaseArticles import KnowledgeBaseArticle
from apps.ecommerce.models.CustomerSupport.OrderIssueClaims import OrderIssueClaim
from apps.ecommerce.models.ReviewUgc.ProductQuestionAnswers import ProductQuestionAnswer
from apps.ecommerce.models.ReviewUgc.ProductReviews import ProductReview
from apps.ecommerce.models.ReviewUgc.ReviewSentimentSummaries import ReviewSentimentSummary
from apps.ecommerce.models.ReviewUgc.VisualUgcMedia import VisualUgcMedia
from apps.ecommerce.models.SubscriptionCommerce.CustomerSubscriptions import CustomerSubscription
from apps.ecommerce.models.SubscriptionCommerce.SubscriptionBoxCurations import SubscriptionBoxCuration
from apps.ecommerce.models.SubscriptionCommerce.SubscriptionPlans import SubscriptionPlan
from apps.ecommerce.models.SubscriptionCommerce.SubscriptionRetentionActions import SubscriptionRetentionAction
from apps.ecommerce.models.ContentManagement.BlogArticles import BlogArticle
from apps.ecommerce.models.ContentManagement.CmsPages import CmsPage
from apps.ecommerce.models.ContentManagement.ContentBlocks import ContentBlock
from apps.ecommerce.models.ContentManagement.MediaAssets import MediaAsset
from apps.ecommerce.models.AnalyticsBi.DailySalesSnapshots import DailySalesSnapshot
from apps.ecommerce.models.AnalyticsBi.CustomerCohortMetrics import CustomerCohortMetric
from apps.ecommerce.models.AnalyticsBi.ProductMerchandisingMetrics import ProductMerchandisingMetric
from apps.ecommerce.models.AnalyticsBi.AttributionTouchpoints import AttributionTouchpoint
from apps.ecommerce.models.MobileCommerce.MobileAppConfigs import MobileAppConfig
from apps.ecommerce.models.MobileCommerce.MobileDeviceRegistrations import MobileDeviceRegistration
from apps.ecommerce.models.MobileCommerce.MobilePushCampaigns import MobilePushCampaign
from apps.ecommerce.models.MobileCommerce.MobileLocationRules import MobileLocationRule
from apps.ecommerce.models.B2bWholesale.B2bCompanyAccounts import B2bCompanyAccount
from apps.ecommerce.models.B2bWholesale.B2bCompanyUsers import B2bCompanyUser
from apps.ecommerce.models.B2bWholesale.B2bQuoteRequests import B2bQuoteRequest
from apps.ecommerce.models.B2bWholesale.B2bQuickOrderTemplates import B2bQuickOrderTemplate
from apps.ecommerce.models.FraudRisk.FraudRules import FraudRule
from apps.ecommerce.models.FraudRisk.TransactionRiskAssessments import TransactionRiskAssessment
from apps.ecommerce.models.FraudRisk.ChargebackDisputes import ChargebackDispute
from apps.ecommerce.models.FraudRisk.AccountSecurityAlerts import AccountSecurityAlert


@admin.register(StoreCategory)
class StoreCategoryAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "slug", "parent", "display_order", "is_active", "include_in_menu"]
    list_filter = ["is_active", "include_in_menu", "tenant"]
    search_fields = ["name", "slug", "number", "description"]
    ordering = ["tenant", "display_order", "name"]


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ["sku", "name", "price", "compare_at_price", "is_active", "sort_order"]


@admin.register(CatalogProduct)
class CatalogProductAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "brand", "primary_category", "status", "visibility", "pim_completeness", "is_featured", "created_at"]
    list_filter = ["status", "visibility", "is_featured", "is_digital", "tenant"]
    search_fields = ["name", "slug", "number", "brand", "short_description"]
    ordering = ["-created_at"]
    inlines = [ProductVariantInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ["number", "sku", "product", "name", "price", "compare_at_price", "is_active", "sort_order"]
    list_filter = ["is_active", "tenant"]
    search_fields = ["sku", "name", "number", "barcode", "product__name"]
    ordering = ["product", "sort_order", "sku"]


@admin.register(ProductRelationship)
class ProductRelationshipAdmin(admin.ModelAdmin):
    list_display = ["number", "source_product", "relationship_type", "target_product", "discount_pct", "is_active", "sort_order"]
    list_filter = ["relationship_type", "is_active", "tenant"]
    search_fields = ["number", "source_product__name", "target_product__name", "notes"]
    ordering = ["source_product", "sort_order"]


@admin.register(FulfillmentCenter)
class FulfillmentCenterAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "code", "center_type", "priority", "city", "state", "is_active"]
    list_filter = ["center_type", "is_active", "tenant"]
    search_fields = ["name", "code", "city", "state", "number"]
    ordering = ["priority", "name"]


@admin.register(InventoryAllocation)
class InventoryAllocationAdmin(admin.ModelAdmin):
    list_display = ["number", "variant", "fulfillment_center", "zone_bin", "quantity_on_hand", "quantity_allocated", "safety_stock_buffer", "available_to_promise", "is_low_stock_alert"]
    list_filter = ["is_low_stock_alert", "fulfillment_center", "tenant"]
    search_fields = ["number", "variant__sku", "variant__name", "fulfillment_center__name", "zone_bin"]
    ordering = ["variant__sku", "fulfillment_center"]


@admin.register(BackorderPolicy)
class BackorderPolicyAdmin(admin.ModelAdmin):
    list_display = ["number", "variant", "policy_type", "expected_availability_date", "current_backorder_count", "max_backorder_quantity", "is_active"]
    list_filter = ["policy_type", "is_active", "tenant"]
    search_fields = ["number", "variant__sku", "variant__name", "storefront_message"]
    ordering = ["variant__sku"]


@admin.register(ChannelInventorySync)
class ChannelInventorySyncAdmin(admin.ModelAdmin):
    list_display = ["number", "channel_name", "channel_type", "variant", "fulfillment_center", "last_synced_quantity", "sync_status", "last_synced_at"]
    list_filter = ["channel_type", "sync_status", "sync_mode", "tenant"]
    search_fields = ["number", "channel_name", "variant__sku", "variant__name"]
    ordering = ["variant__sku", "channel_type"]


@admin.register(DynamicPriceRule)
class DynamicPriceRuleAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "rule_type", "adjustment_value", "scope", "customer_segment", "priority", "is_active", "valid_from", "valid_to"]
    list_filter = ["rule_type", "scope", "customer_segment", "loyalty_tier", "is_active", "tenant"]
    search_fields = ["name", "number", "description"]
    ordering = ["-priority", "-created_at"]


@admin.register(CouponPromotion)
class CouponPromotionAdmin(admin.ModelAdmin):
    list_display = ["number", "code", "name", "discount_type", "discount_value", "min_spend", "used_count", "usage_limit_total", "is_active"]
    list_filter = ["discount_type", "is_stackable", "loyalty_tier_required", "is_active", "tenant"]
    search_fields = ["code", "name", "number"]
    ordering = ["-created_at"]


@admin.register(FlashSale)
class FlashSaleAdmin(admin.ModelAdmin):
    list_display = ["number", "title", "status", "discount_percentage", "flash_price", "inventory_cap", "units_sold", "start_time", "end_time"]
    list_filter = ["status", "tenant"]
    search_fields = ["title", "number", "badge_label"]
    ordering = ["-start_time"]


@admin.register(CompetitorPriceMonitor)
class CompetitorPriceMonitorAdmin(admin.ModelAdmin):
    list_display = ["number", "competitor_name", "variant", "competitor_price", "match_strategy", "min_margin_pct", "is_in_stock", "status", "last_scraped_at"]
    list_filter = ["match_strategy", "status", "is_in_stock", "tenant"]
    search_fields = ["competitor_name", "number", "variant__sku"]
    ordering = ["-last_scraped_at", "-created_at"]


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    fields = ["product", "variant", "quantity", "unit_price", "total_price"]


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ["number", "customer", "email", "status", "currency", "subtotal", "grand_total", "coupon_code", "last_activity_at"]
    list_filter = ["status", "currency", "tenant"]
    search_fields = ["number", "email", "session_key", "coupon_code"]
    ordering = ["-last_activity_at"]
    inlines = [CartItemInline]


@admin.register(CheckoutSession)
class CheckoutSessionAdmin(admin.ModelAdmin):
    list_display = ["number", "cart", "email", "shipping_name", "flow_type", "current_step", "status", "payment_status", "total_amount", "created_at"]
    list_filter = ["status", "flow_type", "current_step", "payment_status", "tenant"]
    search_fields = ["number", "email", "shipping_name", "cart__number"]
    ordering = ["-created_at"]


@admin.register(ShippingMethodConfig)
class ShippingMethodConfigAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "code", "carrier", "calculation_type", "base_rate", "cost_per_kg", "is_active", "sort_order"]
    list_filter = ["carrier", "calculation_type", "is_active", "tenant"]
    search_fields = ["name", "code", "description"]
    ordering = ["sort_order", "name"]


@admin.register(PaymentMethodConfig)
class PaymentMethodConfigAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "provider", "method_category", "environment", "fee_type", "fee_amount", "is_active", "display_order"]
    list_filter = ["provider", "method_category", "environment", "is_active", "tenant"]
    search_fields = ["name", "instructions"]
    ordering = ["display_order", "name"]


class EcommerceOrderLineInline(admin.TabularInline):
    model = EcommerceOrderLine
    extra = 0
    fields = ["product", "variant", "sku", "product_name", "quantity", "unit_price", "unit_discount", "line_total", "status"]


@admin.register(EcommerceOrder)
class EcommerceOrderAdmin(admin.ModelAdmin):
    list_display = ["number", "customer", "currency", "status", "payment_status", "fulfillment_status", "total_amount", "fraud_risk_level", "created_at"]
    list_filter = ["status", "payment_status", "fulfillment_status", "fraud_risk_level", "tenant"]
    search_fields = ["number", "customer__name", "guest_email", "shipping_name"]
    ordering = ["-created_at"]
    inlines = [EcommerceOrderLineInline]


@admin.register(OrderRoutingRule)
class OrderRoutingRuleAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "strategy", "priority", "destination_country", "preferred_fulfillment_center", "allow_split_shipment", "is_active"]
    list_filter = ["strategy", "allow_split_shipment", "enable_dropship", "is_active", "tenant"]
    search_fields = ["number", "name", "destination_country", "destination_region"]
    ordering = ["priority", "name"]


@admin.register(OrderFulfillment)
class OrderFulfillmentAdmin(admin.ModelAdmin):
    list_display = ["number", "order", "fulfillment_center", "carrier_name", "tracking_number", "status", "shipping_cost", "shipped_at"]
    list_filter = ["status", "carrier_name", "fulfillment_center", "tenant"]
    search_fields = ["number", "order__number", "carrier_name", "tracking_number"]
    ordering = ["-created_at"]


@admin.register(ReturnMerchandiseAuthorization)
class ReturnMerchandiseAuthorizationAdmin(admin.ModelAdmin):
    list_display = ["number", "order", "customer", "return_type", "status", "reason", "refund_amount", "refund_status", "restocking_status"]
    list_filter = ["return_type", "status", "reason", "refund_status", "restocking_status", "tenant"]
    search_fields = ["number", "order__number", "customer__name", "return_tracking_number"]
    ordering = ["-created_at"]


@admin.register(CustomerAccountProfile)
class CustomerAccountProfileAdmin(admin.ModelAdmin):
    list_display = ["number", "customer", "user", "tier", "status", "auth_mode", "phone_number", "phone_verified", "total_spent", "order_count"]
    list_filter = ["tier", "status", "auth_mode", "phone_verified", "tenant"]
    search_fields = ["number", "customer__name", "user__username", "phone_number"]
    list_select_related = ["customer", "user"]
    ordering = ["-created_at"]


@admin.register(CustomerAddressPreference)
class CustomerAddressPreferenceAdmin(admin.ModelAdmin):
    list_display = ["number", "customer", "label", "is_default_shipping", "is_default_billing", "preferred_delivery_window", "requires_signature"]
    list_filter = ["is_default_shipping", "is_default_billing", "preferred_delivery_window", "requires_signature", "tenant"]
    search_fields = ["number", "customer__name", "label", "recipient_name"]
    list_select_related = ["customer", "address"]
    ordering = ["-created_at"]


class CustomerWishlistItemInline(admin.TabularInline):
    model = CustomerWishlistItem
    extra = 1
    fields = ["product", "variant", "desired_quantity", "priority", "comment"]


@admin.register(CustomerWishlist)
class CustomerWishlistAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "customer", "visibility", "is_default", "share_token"]
    list_filter = ["visibility", "is_default", "tenant"]
    search_fields = ["number", "name", "customer__name", "share_token"]
    list_select_related = ["customer"]
    ordering = ["-created_at"]
    inlines = [CustomerWishlistItemInline]


@admin.register(CustomerWishlistItem)
class CustomerWishlistItemAdmin(admin.ModelAdmin):
    list_display = ["wishlist", "product", "variant", "desired_quantity", "priority"]
    list_filter = ["priority", "tenant"]
    search_fields = ["wishlist__name", "product__name", "comment"]
    list_select_related = ["wishlist", "product", "variant"]
    ordering = ["-created_at"]


@admin.register(CustomerPrivacyRequest)
class CustomerPrivacyRequestAdmin(admin.ModelAdmin):
    list_display = ["number", "customer", "request_type", "status", "statutory_deadline", "completed_at", "requested_by_email"]
    list_filter = ["request_type", "status", "tenant"]
    search_fields = ["number", "customer__name", "requested_by_email", "resolution_notes"]
    list_select_related = ["customer"]
    ordering = ["-created_at"]


@admin.register(SearchSynonym)
class SearchSynonymAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "synonym_type", "root_term", "hit_count", "is_active", "created_at"]
    list_filter = ["synonym_type", "is_active", "tenant"]
    search_fields = ["number", "name", "root_term", "synonyms", "notes"]
    ordering = ["root_term", "-created_at"]


@admin.register(SearchFacetConfig)
class SearchFacetConfigAdmin(admin.ModelAdmin):
    list_display = ["display_order", "name", "code", "source_type", "widget_type", "filter_logic", "category_scope", "is_active"]
    list_filter = ["source_type", "widget_type", "filter_logic", "is_active", "tenant"]
    search_fields = ["name", "code", "option_key", "category_scope__name"]
    list_select_related = ["category_scope"]
    ordering = ["display_order", "name"]


@admin.register(SearchMerchandisingRule)
class SearchMerchandisingRuleAdmin(admin.ModelAdmin):
    list_display = ["priority", "name", "rule_type", "trigger_query", "action_type", "boosted_product", "is_active"]
    list_filter = ["rule_type", "action_type", "match_type", "is_active", "tenant"]
    search_fields = ["name", "trigger_query", "redirect_url", "banner_title", "boosted_product__name"]
    list_select_related = ["target_category", "boosted_product"]
    ordering = ["-priority", "-created_at"]


@admin.register(SearchQueryLog)
class SearchQueryLogAdmin(admin.ModelAdmin):
    list_display = ["number", "query_text", "results_count", "execution_time_ms", "is_zero_result", "sort_order", "customer", "created_at"]
    list_filter = ["is_zero_result", "sort_order", "tenant"]
    search_fields = ["number", "query_text", "normalized_query", "redirected_to", "session_key", "customer__name"]
    list_select_related = ["customer", "clicked_product"]
    ordering = ["-created_at"]


@admin.register(AudienceSegment)
class AudienceSegmentAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "code", "lifecycle_stage", "cached_member_count", "is_active", "last_evaluated_at"]
    list_filter = ["lifecycle_stage", "is_active", "tenant"]
    search_fields = ["number", "name", "code", "description"]
    list_select_related = ["target_category"]
    ordering = ["name"]


@admin.register(RecommendationStrategy)
class RecommendationStrategyAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "code", "algorithm", "placement", "fallback_strategy", "max_items", "is_active"]
    list_filter = ["algorithm", "placement", "fallback_strategy", "is_active", "tenant"]
    search_fields = ["number", "name", "code", "description"]
    list_select_related = ["target_category", "target_segment"]
    ordering = ["placement", "name"]


@admin.register(PersonalizedExperience)
class PersonalizedExperienceAdmin(admin.ModelAdmin):
    list_display = ["priority", "name", "experience_type", "target_segment", "impression_count", "click_count", "is_active"]
    list_filter = ["experience_type", "is_active", "tenant"]
    search_fields = ["number", "name", "headline", "cta_label"]
    list_select_related = ["target_segment", "target_category", "target_product"]
    ordering = ["-priority", "-created_at"]


@admin.register(ShopperBehaviorEvent)
class ShopperBehaviorEventAdmin(admin.ModelAdmin):
    list_display = ["number", "event_type", "session_key", "product", "intent_score_delta", "created_at"]
    list_filter = ["event_type", "tenant"]
    search_fields = ["number", "session_key", "referrer_url", "product__name"]
    list_select_related = ["product", "category", "customer_profile", "party", "user"]
    ordering = ["-created_at"]


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "code", "plan_type", "frequency", "discount_type", "discount_value", "is_active"]
    list_filter = ["plan_type", "frequency", "discount_type", "is_active", "tenant"]
    search_fields = ["number", "name", "code", "description"]
    list_select_related = ["target_product"]
    ordering = ["name"]


@admin.register(CustomerSubscription)
class CustomerSubscriptionAdmin(admin.ModelAdmin):
    list_display = ["number", "customer_profile", "plan", "product", "status", "next_billing_date", "completed_cycles_count"]
    list_filter = ["status", "plan", "tenant"]
    search_fields = ["number", "customer_profile__customer__name", "customer_profile__user__email", "product__name"]
    list_select_related = ["customer_profile__customer", "customer_profile__user", "plan", "product", "variant"]
    ordering = ["-started_at"]


@admin.register(SubscriptionBoxCuration)
class SubscriptionBoxCurationAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "cycle_identifier", "plan", "primary_product", "has_surprise_item", "start_date", "end_date", "is_active"]
    list_filter = ["is_active", "has_surprise_item", "plan", "tenant"]
    search_fields = ["number", "name", "code", "cycle_identifier", "theme_title", "preference_tag"]
    list_select_related = ["plan", "primary_product"]
    ordering = ["-start_date"]


@admin.register(SubscriptionRetentionAction)
class SubscriptionRetentionActionAdmin(admin.ModelAdmin):
    list_display = ["number", "subscription", "trigger_type", "cancellation_reason", "offered_action", "outcome", "churn_risk_score", "created_at"]
    list_filter = ["trigger_type", "outcome", "cancellation_reason", "tenant"]
    search_fields = ["number", "subscription__number", "customer_profile__user__email", "notes"]
    list_select_related = ["subscription__customer_profile__customer", "subscription__product", "customer_profile__customer"]
    ordering = ["-created_at"]


# ---------------------------------------------------------------------------
# 9.11 Marketplace & Multi-Vendor
# ---------------------------------------------------------------------------


@admin.register(MarketplaceVendor)
class MarketplaceVendorAdmin(admin.ModelAdmin):
    list_display = ["number", "store_name", "party", "status", "kyc_status", "commission_rate", "rating_average", "is_featured"]
    list_filter = ["status", "kyc_status", "commission_type", "is_featured", "tenant"]
    search_fields = ["number", "store_name", "slug", "party__name", "support_email", "tax_id"]
    list_select_related = ["party", "owner_user", "suspended_by"]
    ordering = ["store_name"]


@admin.register(VendorProductListing)
class VendorProductListingAdmin(admin.ModelAdmin):
    list_display = ["number", "product", "vendor", "seller_sku", "asking_price", "available_quantity", "moderation_status", "compliance_status", "is_active"]
    list_filter = ["moderation_status", "compliance_status", "condition", "is_active", "tenant"]
    search_fields = ["number", "seller_sku", "barcode", "product__name", "vendor__store_name"]
    list_select_related = ["product", "variant", "vendor", "reviewed_by"]
    ordering = ["-created_at"]


@admin.register(VendorSubOrder)
class VendorSubOrderAdmin(admin.ModelAdmin):
    list_display = ["number", "order", "vendor", "fulfillment_status", "sla_status", "subtotal_amount", "net_vendor_amount", "payout_status", "dispute_status"]
    list_filter = ["fulfillment_status", "sla_status", "payout_status", "dispute_status", "tenant"]
    search_fields = ["number", "order__number", "vendor__store_name", "tracking_number", "carrier_name"]
    list_select_related = ["order", "vendor", "payout"]
    ordering = ["-created_at"]


@admin.register(VendorPayout)
class VendorPayoutAdmin(admin.ModelAdmin):
    list_display = ["number", "vendor", "period_start", "period_end", "gross_sales_amount", "commission_deducted", "net_payout_amount", "payout_status", "is_1099_reported"]
    list_filter = ["payout_status", "payout_method", "is_1099_reported", "tenant"]
    search_fields = ["number", "vendor__store_name", "reference_code", "notes"]
    list_select_related = ["vendor", "approved_by"]
    ordering = ["-period_end"]


# ---------------------------------------------------------------------------
# 9.10 Marketing & Campaign Management
# ---------------------------------------------------------------------------


@admin.register(MarketingCampaign)
class MarketingCampaignAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "channel", "campaign_type", "status", "scheduled_at", "recipient_count", "delivered_count", "revenue_attributed"]
    list_filter = ["channel", "campaign_type", "status", "tenant"]
    search_fields = ["number", "name", "code", "subject"]
    readonly_fields = [
        "number",
        "sent_at",
        "recipient_count",
        "delivered_count",
        "opened_count",
        "clicked_count",
        "bounced_count",
        "unsubscribed_count",
        "revenue_attributed",
        "created_at",
        "updated_at",
    ]
    list_select_related = ["target_segment", "target_product"]
    ordering = ["-created_at"]


@admin.register(AffiliatePartner)
class AffiliatePartnerAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "partner_type", "referral_code", "status", "commission_type", "commission_rate", "total_orders_referred", "total_revenue_generated"]
    list_filter = ["partner_type", "status", "commission_type", "tenant"]
    search_fields = ["number", "name", "referral_code", "referral_link_slug", "party__name"]
    readonly_fields = [
        "number",
        "total_orders_referred",
        "total_revenue_generated",
        "total_commission_earned",
        "total_commission_paid",
        "created_at",
        "updated_at",
    ]
    list_select_related = ["party", "customer_profile"]
    ordering = ["name"]


@admin.register(AffiliateReferralConversion)
class AffiliateReferralConversionAdmin(admin.ModelAdmin):
    list_display = ["number", "affiliate", "order", "attribution_type", "order_amount", "commission_amount", "status", "paid_at"]
    list_filter = ["status", "attribution_type", "tenant"]
    search_fields = ["number", "affiliate__name", "order__number", "payout_reference"]
    readonly_fields = [
        "number",
        "commission_amount",
        "paid_at",
        "created_at",
        "updated_at",
    ]
    list_select_related = ["affiliate", "order", "referred_customer"]
    ordering = ["-created_at"]


@admin.register(SeoMetadataRule)
class SeoMetadataRuleAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "rule_type", "json_ld_schema_type", "robots_directive", "sitemap_included", "target_keyword", "tracked_rank_position", "is_active"]
    list_filter = ["rule_type", "json_ld_schema_type", "robots_directive", "sitemap_included", "is_active", "tenant"]
    search_fields = ["number", "name", "target_keyword", "url_path_pattern"]
    readonly_fields = [
        "number",
        "tracked_rank_position",
        "rank_tracked_at",
        "created_at",
        "updated_at",
    ]
    list_select_related = ["target_category", "target_product"]
    ordering = ["-created_at"]


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "product",
        "reviewer_name",
        "rating",
        "status",
        "sentiment",
        "is_verified_purchase",
        "is_featured",
        "created_at",
    ]
    list_filter = ["status", "rating", "sentiment", "is_verified_purchase", "is_featured", "tenant"]
    search_fields = ["number", "title", "body", "reviewer_name", "reviewer_email", "product__name"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["product", "variant", "customer", "order", "moderated_by"]
    ordering = ["-is_featured", "-created_at"]


@admin.register(ProductQuestionAnswer)
class ProductQuestionAnswerAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "product",
        "author_name",
        "status",
        "is_staff_answer",
        "is_pinned",
        "created_at",
    ]
    list_filter = ["status", "is_staff_answer", "is_pinned", "tenant"]
    search_fields = ["number", "question_text", "answer_text", "author_name", "product__name"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["product", "customer", "answered_by_user"]
    ordering = ["-is_pinned", "-created_at"]


@admin.register(VisualUgcMedia)
class VisualUgcMediaAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "tagged_product",
        "media_type",
        "uploader_name",
        "rights_status",
        "is_published",
        "is_shoppable",
        "display_order",
    ]
    list_filter = ["media_type", "rights_status", "is_published", "is_shoppable", "tenant"]
    search_fields = ["number", "caption", "uploader_name", "uploader_handle", "tagged_product__name"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["tagged_product", "tagged_variant"]
    ordering = ["display_order", "-created_at"]


@admin.register(ReviewSentimentSummary)
class ReviewSentimentSummaryAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "product",
        "total_reviews",
        "average_rating",
        "positive_sentiment_pct",
        "negative_sentiment_pct",
        "last_calculated_at",
    ]
    list_filter = ["tenant"]
    search_fields = ["number", "product__name", "improvement_recommendation"]
    readonly_fields = ["number", "last_calculated_at", "created_at", "updated_at"]
    list_select_related = ["product"]
    ordering = ["-total_reviews", "-average_rating"]


@admin.register(CustomerSupportTicket)
class CustomerSupportTicketAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "subject",
        "customer_name",
        "channel",
        "category",
        "priority",
        "status",
        "assigned_agent",
        "is_sla_breached",
        "created_at",
    ]
    list_filter = ["status", "priority", "channel", "category", "is_sla_breached", "tenant"]
    search_fields = ["number", "subject", "customer_name", "customer_email", "initial_message"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["customer", "order", "assigned_agent"]
    ordering = ["-created_at"]


@admin.register(KnowledgeBaseArticle)
class KnowledgeBaseArticleAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "title",
        "category",
        "target_audience",
        "status",
        "is_featured",
        "view_count",
        "helpful_votes",
        "author",
    ]
    list_filter = ["status", "category", "target_audience", "is_featured", "tenant"]
    search_fields = ["number", "title", "slug", "summary", "keywords"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["author"]
    ordering = ["-is_featured", "-created_at"]


@admin.register(OrderIssueClaim)
class OrderIssueClaimAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "order",
        "claim_type",
        "status",
        "claimed_amount",
        "approved_amount",
        "resolution_action",
        "reviewed_by",
        "created_at",
    ]
    list_filter = ["status", "claim_type", "resolution_action", "tenant"]
    search_fields = ["number", "order__number", "carrier_tracking_number", "customer_notes"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["order", "customer", "ticket", "reviewed_by"]
    ordering = ["-created_at"]


@admin.register(CustomerSatisfactionSurvey)
class CustomerSatisfactionSurveyAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "survey_type",
        "rating_score",
        "sentiment",
        "follow_up_status",
        "agent_rated",
        "reviewed_by",
        "created_at",
    ]
    list_filter = ["survey_type", "sentiment", "follow_up_status", "tenant"]
    search_fields = ["number", "feedback_comment", "follow_up_notes"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["ticket", "order", "customer", "agent_rated", "reviewed_by"]
    ordering = ["-created_at"]


# 9.9 Content Management System (CMS)
@admin.register(CmsPage)
class CmsPageAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "title",
        "slug",
        "page_type",
        "status",
        "template_layout",
        "view_count",
        "is_ab_test_active",
        "updated_at",
    ]
    list_filter = ["page_type", "status", "template_layout", "is_ab_test_active", "is_indexable", "tenant"]
    search_fields = ["title", "slug", "number", "meta_title"]
    readonly_fields = ["number", "created_at", "updated_at"]
    ordering = ["-created_at"]


@admin.register(BlogArticle)
class BlogArticleAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "title",
        "slug",
        "author",
        "category",
        "status",
        "reading_time_minutes",
        "is_featured",
        "view_count",
        "published_at",
    ]
    list_filter = ["category", "status", "is_featured", "allow_comments", "tenant"]
    search_fields = ["title", "slug", "number", "tags", "excerpt"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["author", "featured_media"]
    ordering = ["-created_at"]


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "title",
        "media_type",
        "folder_category",
        "mime_type",
        "width_px",
        "height_px",
        "uploaded_by",
        "created_at",
    ]
    list_filter = ["media_type", "folder_category", "tenant"]
    search_fields = ["title", "alt_text", "caption", "number"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["uploaded_by"]
    ordering = ["-created_at"]


@admin.register(ContentBlock)
class ContentBlockAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "name",
        "block_type",
        "sort_order",
        "is_active",
        "bg_color_class",
        "created_at",
    ]
    list_filter = ["block_type", "is_active", "tenant"]
    search_fields = ["name", "headline", "subheadline", "number"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["media_asset", "target_category", "target_product"]
    ordering = ["sort_order", "-created_at"]


@admin.register(DailySalesSnapshot)
class DailySalesSnapshotAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "snapshot_date",
        "currency",
        "orders_count",
        "gross_sales",
        "net_sales",
        "average_order_value",
        "conversion_rate_pct",
        "is_finalized",
    ]
    list_filter = ["currency", "is_finalized", "tenant"]
    search_fields = ["number", "notes"]
    readonly_fields = ["number", "created_at", "updated_at"]
    ordering = ["-snapshot_date"]


@admin.register(CustomerCohortMetric)
class CustomerCohortMetricAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "cohort_month",
        "period_offset_months",
        "initial_cohort_size",
        "active_customers",
        "retention_rate_pct",
        "cumulative_ltv_per_customer",
        "acquisition_channel_tag",
    ]
    list_filter = ["cohort_month", "acquisition_channel_tag", "tenant"]
    search_fields = ["number", "acquisition_channel_tag"]
    readonly_fields = ["number", "created_at", "updated_at"]
    ordering = ["-cohort_month", "period_offset_months"]


@admin.register(ProductMerchandisingMetric)
class ProductMerchandisingMetricAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "product",
        "velocity_tier",
        "units_sold",
        "gross_revenue",
        "gross_margin_pct",
        "return_rate_pct",
        "conversion_rate_pct",
    ]
    list_filter = ["velocity_tier", "tenant"]
    search_fields = ["number", "product__name", "variant__sku"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["product", "variant"]
    ordering = ["-period_end", "-gross_revenue"]


@admin.register(AttributionTouchpoint)
class AttributionTouchpointAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "channel_type",
        "attribution_model",
        "attributed_revenue",
        "order",
        "utm_source",
        "touchpoint_timestamp",
    ]
    list_filter = ["channel_type", "attribution_model", "tenant"]
    search_fields = ["number", "utm_source", "utm_campaign", "order__number"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["order", "cart", "campaign", "affiliate"]
    ordering = ["-touchpoint_timestamp"]


@admin.register(MobileAppConfig)
class MobileAppConfigAdmin(admin.ModelAdmin):
    list_display = ["number", "app_name", "short_name", "display_mode", "enable_pwa", "enable_apple_pay", "enable_google_pay", "is_active"]
    list_filter = ["is_active", "enable_pwa", "enable_apple_pay", "enable_google_pay", "display_mode", "tenant"]
    search_fields = ["number", "app_name", "short_name"]
    readonly_fields = ["number", "created_at", "updated_at"]
    ordering = ["-is_active", "-created_at"]


@admin.register(MobileDeviceRegistration)
class MobileDeviceRegistrationAdmin(admin.ModelAdmin):
    list_display = ["number", "device_platform", "device_model", "customer_profile", "push_enabled", "biometric_enrolled", "is_active", "last_active_at"]
    list_filter = ["device_platform", "push_provider", "push_enabled", "biometric_enrolled", "is_active", "tenant"]
    search_fields = ["number", "device_uuid", "device_model", "customer_profile__number"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["customer_profile", "party"]
    ordering = ["-last_active_at", "-created_at"]


@admin.register(MobilePushCampaign)
class MobilePushCampaignAdmin(admin.ModelAdmin):
    list_display = ["number", "campaign_name", "campaign_type", "target_platform", "status", "sent_count", "opened_count", "converted_revenue", "scheduled_for"]
    list_filter = ["status", "campaign_type", "target_platform", "tenant"]
    search_fields = ["number", "campaign_name", "notification_title"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["target_product", "target_category", "target_coupon", "created_by"]
    ordering = ["-scheduled_for", "-created_at"]


@admin.register(MobileLocationRule)
class MobileLocationRuleAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "store_name", "rule_type", "radius_meters", "trigger_action", "enable_instore_mode", "is_active"]
    list_filter = ["rule_type", "trigger_action", "is_active", "enable_instore_mode", "tenant"]
    search_fields = ["number", "name", "store_name"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["fulfillment_center", "linked_promotion"]
    ordering = ["store_name", "-created_at"]


@admin.register(B2bCompanyAccount)
class B2bCompanyAccountAdmin(admin.ModelAdmin):
    list_display = ["number", "company_name", "credit_limit", "available_credit", "payment_terms", "credit_status", "status", "punchout_enabled"]
    list_filter = ["status", "credit_status", "payment_terms", "punchout_enabled", "tenant"]
    search_fields = ["number", "company_name", "company_tax_id", "business_registration_number"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["company_party", "primary_contact", "preferred_currency"]
    ordering = ["-created_at"]


@admin.register(B2bCompanyUser)
class B2bCompanyUserAdmin(admin.ModelAdmin):
    list_display = ["number", "user", "company", "role", "order_spend_limit", "monthly_spend_limit", "status"]
    list_filter = ["role", "status", "tenant"]
    search_fields = ["number", "user__username", "user__email", "company__company_name"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["company", "user", "party"]
    ordering = ["company", "user__username"]


@admin.register(B2bQuoteRequest)
class B2bQuoteRequestAdmin(admin.ModelAdmin):
    list_display = ["number", "company", "requested_by", "original_subtotal", "quoted_discount_percent", "quoted_total", "status", "valid_until"]
    list_filter = ["status", "tenant"]
    search_fields = ["number", "company__company_name", "requested_by__username"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["company", "requested_by", "assigned_sales_rep", "currency", "converted_order"]
    ordering = ["-created_at"]


@admin.register(B2bQuickOrderTemplate)
class B2bQuickOrderTemplateAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "company", "scope", "cadence", "total_items_count", "times_ordered", "is_active"]
    list_filter = ["scope", "cadence", "is_active", "tenant"]
    search_fields = ["number", "name", "company__company_name"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["company", "created_by"]
    ordering = ["company", "name"]


@admin.register(FraudRule)
class FraudRuleAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "rule_code", "rule_scope", "rule_type", "action_to_take", "priority", "is_active"]
    list_filter = ["rule_scope", "rule_type", "action_to_take", "is_active", "tenant"]
    search_fields = ["number", "name", "rule_code", "threshold_value"]
    readonly_fields = ["number", "created_at", "updated_at"]
    ordering = ["priority", "name"]


@admin.register(TransactionRiskAssessment)
class TransactionRiskAssessmentAdmin(admin.ModelAdmin):
    list_display = ["number", "order", "risk_score", "risk_tier", "recommended_action", "actual_decision", "avs_result_code", "cvv_result_code", "created_at"]
    list_filter = ["risk_tier", "recommended_action", "actual_decision", "is_proxy_or_vpn", "is_geo_mismatch", "tenant"]
    search_fields = ["number", "order__number", "ip_address", "device_fingerprint"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["order", "customer_party", "currency", "user", "analyst_user"]
    ordering = ["-created_at"]


@admin.register(ChargebackDispute)
class ChargebackDisputeAdmin(admin.ModelAdmin):
    list_display = ["number", "order", "dispute_amount", "currency", "reason_category", "stage", "evidence_due_date", "created_at"]
    list_filter = ["stage", "reason_category", "payment_method_type", "tenant"]
    search_fields = ["number", "order__number", "gateway_dispute_id", "reason_code"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["order", "customer_party", "currency"]
    ordering = ["-created_at"]


@admin.register(AccountSecurityAlert)
class AccountSecurityAlertAdmin(admin.ModelAdmin):
    list_display = ["number", "user", "alert_type", "severity", "automated_action_taken", "status", "created_at"]
    list_filter = ["alert_type", "severity", "status", "automated_action_taken", "tenant"]
    search_fields = ["number", "user__username", "ip_address", "location_info"]
    readonly_fields = ["number", "created_at", "updated_at"]
    list_select_related = ["user", "party", "assigned_investigator", "resolved_by"]
    ordering = ["-created_at"]














